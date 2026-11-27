# data_access/schedule_store.py
import copy
import json
import os
import tempfile
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from time import time_ns
from typing import Any

from .paths import (
    BASE_SCHEDULE_BACKUPS_DIR,
    BASE_SCHEDULE_PATH,
    WEEK_SCHEDULES_DIR,
)

BASE_SCHEDULE_BACKUP_LIMIT = 10


class ScheduleStore:
    """Двухуровневое расписание: база (эталон) + недельные оверрайды.

    - base:   DATA_DIR/base/schedule.json       — эталон, меняется редко
    - week:   DATA_DIR/weeks/YYYY-Www/schedule.json — создаётся как копия базы
              при первом запросе недели и дальше изменяется независимо.
    """

    def _read(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ValueError(f"Файл расписания не найден: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("meta"), dict):
            raise ValueError(f"Некорректная структура расписания в {path}")
        if not isinstance(data.get("schedule"), list):
            raise ValueError(f"В {path} поле schedule должно быть списком")
        return data

    def _write(self, path: Path, schedule: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(schedule, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            tmp = None
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)

    @staticmethod
    def _week_path(week: int | None = None, year: int | None = None) -> Path:
        if week is None and year is None:
            year, week, _ = date.today().isocalendar()
        if week is None or year is None:
            raise ValueError("week и year нужно указывать вместе")
        if (
            isinstance(week, bool)
            or not isinstance(week, int)
            or isinstance(year, bool)
            or not isinstance(year, int)
        ):
            raise ValueError("week и year должны быть целыми числами")
        try:
            date.fromisocalendar(year, week, 1)
        except ValueError as error:
            raise ValueError(
                "year и week должны обозначать существующую ISO-неделю"
            ) from error
        return WEEK_SCHEDULES_DIR / f"{year}-W{week:02d}" / "schedule.json"

    @staticmethod
    def _filter_day(
        schedule: dict[str, Any], day: int | None
    ) -> dict[str, Any]:
        if day is None:
            return schedule
        return {
            **schedule,
            "schedule": [
                lesson for lesson in schedule["schedule"] if lesson.get("day") == day
            ],
        }

    @staticmethod
    def _validate_day(day: int | None) -> None:
        if day is not None and (
            isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 7
        ):
            raise ValueError("day должен быть целым числом от 1 до 7")

    def _schedule_from_base(
        self, week_path: Path, source: str, include_base_version: bool = False
    ) -> dict[str, Any]:
        base = self._read(BASE_SCHEDULE_PATH)
        meta = {
            **base["meta"],
            "week": week_path.parent.name,
            "source": source,
        }
        if include_base_version:
            meta["basedOnBaseVersion"] = base["meta"].get("version")
        return {"meta": meta, "schedule": base["schedule"]}

    # ---- чтение ----

    def get_base(self, day: int | None = None) -> dict[str, Any]:
        self._validate_day(day)
        return self._filter_day(self._read(BASE_SCHEDULE_PATH), day)

    def get_week(
        self,
        week: int | None = None,
        year: int | None = None,
        day: int | None = None,
    ) -> dict[str, Any]:
        """Вернуть неделю, при первом запросе создав её копию из базы."""
        self._validate_day(day)
        week_path = self._week_path(week, year)
        if week_path.exists():
            schedule = self._read(week_path)
        else:
            schedule = self._schedule_from_base(
                week_path, "base", include_base_version=True
            )
            self._write(week_path, schedule)
        return self._filter_day(schedule, day)

    def get(
        self,
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
        day: int | None = None,
    ) -> dict[str, Any]:
        return self.get_base(day) if is_base else self.get_week(week, year, day)

    @staticmethod
    def _find_lesson(
        schedule: dict[str, Any], lesson_id: str
    ) -> dict[str, Any] | None:
        return next(
            (lesson for lesson in schedule["schedule"] if lesson.get("id") == lesson_id),
            None,
        )

    def get_lesson_by_id(
        self,
        lesson_id: str,
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
    ) -> dict[str, Any] | None:
        """Вернуть урок из базы или выбранной недели; если не найден, вернуть None."""
        schedule = (
            self.get_base()
            if is_base
            else self.get_week(week=week, year=year)
        )
        return self._find_lesson(schedule, lesson_id)

    @staticmethod
    def _lesson_resources(lesson: dict[str, Any], key: str) -> set[str]:
        parts = lesson.get("parts", [])
        if not isinstance(parts, list):
            raise ValueError(f"Урок {lesson.get('id')}: parts должен быть списком")

        resources = set()
        for part in parts:
            if not isinstance(part, dict):
                raise ValueError(
                    f"Урок {lesson.get('id')}: элемент parts должен быть объектом"
                )
            value = part.get(key)
            if value is not None and value != "":
                if not isinstance(value, str):
                    raise ValueError(
                        f"Урок {lesson.get('id')}: {key} должен быть строкой или null"
                    )
                resources.add(value)
        return resources

    @classmethod
    def _conflicts_between(
        cls, first: dict[str, Any], second: dict[str, Any]
    ) -> list[dict[str, Any]]:
        if (first.get("day"), first.get("slot")) != (
            second.get("day"),
            second.get("slot"),
        ):
            return []

        conflicts = []
        for resource_type, key in (("teacher", "teacherId"), ("room", "roomId")):
            shared_resources = cls._lesson_resources(
                first, key
            ) & cls._lesson_resources(second, key)
            conflicts.extend(
                {
                    "type": resource_type,
                    "resourceId": resource_id,
                    "day": first.get("day"),
                    "slot": first.get("slot"),
                    "lessonIds": [first.get("id"), second.get("id")],
                }
                for resource_id in sorted(shared_resources)
            )
        return conflicts

    @classmethod
    def find_conflicts(
        cls, schedule: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return simultaneous teacher and room conflicts."""
        lessons_by_slot: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
        conflicts = []
        for lesson in schedule:
            slot = (lesson.get("day"), lesson.get("slot"))
            for existing in lessons_by_slot.get(slot, []):
                conflicts.extend(cls._conflicts_between(existing, lesson))
            lessons_by_slot.setdefault(slot, []).append(lesson)
        return conflicts

    @classmethod
    def _ensure_no_new_conflicts(
        cls,
        schedule: list[dict[str, Any]],
        lesson: dict[str, Any],
        ignored_lesson_id: str | None = None,
    ) -> None:
        conflicts = []
        for existing in schedule:
            if existing.get("id") == ignored_lesson_id:
                continue
            conflicts.extend(cls._conflicts_between(existing, lesson))
        if conflicts:
            raise ValueError(
                "Изменение создаёт конфликт занятости: "
                + json.dumps(conflicts, ensure_ascii=False)
            )

    @staticmethod
    def _raise_on_conflicts(schedule: list[dict[str, Any]]) -> None:
        conflicts = ScheduleStore.find_conflicts(schedule)
        if conflicts:
            raise ValueError(
                "Расписание содержит конфликт занятости: "
                + json.dumps(conflicts, ensure_ascii=False)
            )

    # ---- запись ----

    def _materialize_week(
        self, week: int | None = None, year: int | None = None
    ) -> tuple[Path, dict[str, Any]]:
        """Вернуть (путь_недели, содержимое). Если недели нет — берём базу
        и готовим meta недели (файл НЕ пишем здесь)."""
        week_path = self._week_path(week, year)
        if week_path.exists():
            return week_path, self._read(week_path)
        return week_path, self._schedule_from_base(
            week_path, "base", include_base_version=True
        )

    def delete_week(self, week: int, year: int) -> Path:
        """Удалить только файл выбранной недельной копии, не затрагивая базу."""
        week_path = self._week_path(week, year)
        if not week_path.is_file():
            raise ValueError(f"Файл недельного расписания не найден: {week_path}")
        week_path.unlink()
        return week_path

    def replace_schedule(
        self,
        schedule_items: list[dict[str, Any]],
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
    ) -> dict[str, Any]:
        self._raise_on_conflicts(schedule_items)

        def mut(schedule: dict[str, Any]) -> dict[str, Any]:
            schedule["schedule"] = schedule_items
            return schedule

        return self._mutate_schedule(week, year, is_base, mut)

    # ---- точечные операции (для недели) ----

    def _mutate_week(
        self,
        week: int | None,
        year: int | None,
        mutator: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        week_path, schedule = self._materialize_week(week, year)
        schedule = mutator(schedule)
        schedule["meta"]["source"] = "manual"
        self._write(week_path, schedule)
        return schedule

    def _backup_base(self, schedule: dict[str, Any]) -> None:
        BASE_SCHEDULE_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_path = (
            BASE_SCHEDULE_BACKUPS_DIR
            / f"schedule-{timestamp}-{time_ns()}.json"
        )
        self._write(backup_path, schedule)

        backups = sorted(
            BASE_SCHEDULE_BACKUPS_DIR.glob("schedule-*.json"),
            key=lambda path: path.name,
            reverse=True,
        )
        for old_backup in backups[BASE_SCHEDULE_BACKUP_LIMIT:]:
            old_backup.unlink()

    def rollback_base_schedule(self) -> tuple[dict[str, Any], str]:
        """Restore the newest saved backup without creating another backup."""
        current_schedule = self._read(BASE_SCHEDULE_PATH)
        backups = sorted(
            BASE_SCHEDULE_BACKUPS_DIR.glob("schedule-*.json"),
            key=lambda path: path.name,
            reverse=True,
        )
        if not backups:
            raise ValueError("Резервные копии базового расписания отсутствуют")

        backup_path = backups[0]
        backup = self._read(backup_path)
        if backup == current_schedule:
            raise ValueError(
                "Текущее базовое расписание уже совпадает с последней резервной копией"
            )
        self._write(BASE_SCHEDULE_PATH, backup)
        return backup, backup_path.name

    def _mutate_base(
        self, mutator: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> dict[str, Any]:
        schedule = self._read(BASE_SCHEDULE_PATH)
        backup_snapshot = copy.deepcopy(schedule)
        updated_schedule = mutator(schedule)
        self._backup_base(backup_snapshot)
        self._write(BASE_SCHEDULE_PATH, updated_schedule)
        return updated_schedule

    def _mutate_schedule(
        self,
        week: int | None,
        year: int | None,
        is_base: bool,
        mutator: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        if is_base:
            return self._mutate_base(mutator)
        return self._mutate_week(week, year, mutator)

    def add_lesson(
        self,
        lesson: dict[str, Any],
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
    ) -> dict[str, Any]:
        lesson_id = lesson.get("id")

        def mut(schedule: dict[str, Any]) -> dict[str, Any]:
            if self._find_lesson(schedule, lesson_id) is not None:
                raise ValueError(f"Урок с id='{lesson_id}' уже есть в неделе")
            self._ensure_no_new_conflicts(schedule["schedule"], lesson)
            schedule["schedule"].append(lesson)
            return schedule

        return self._mutate_schedule(week, year, is_base, mut)

    def update_lesson(
        self,
        lesson_id: str,
        changes: dict[str, Any],
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
    ) -> dict[str, Any]:
        def mut(schedule: dict[str, Any]) -> dict[str, Any]:
            lesson = self._find_lesson(schedule, lesson_id)
            if lesson is None:
                raise ValueError(f"Урок с id='{lesson_id}' не найден в неделе")
            updated_lesson = {**lesson, **changes}
            self._ensure_no_new_conflicts(
                schedule["schedule"],
                updated_lesson,
                ignored_lesson_id=lesson_id,
            )
            lesson.update(changes)
            return schedule

        return self._mutate_schedule(week, year, is_base, mut)

    def delete_lesson(
        self,
        lesson_id: str,
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
    ) -> dict[str, Any]:
        def mut(schedule: dict[str, Any]) -> dict[str, Any]:
            lesson = self._find_lesson(schedule, lesson_id)
            if lesson is None:
                raise ValueError(f"Урок с id='{lesson_id}' не найден в неделе")
            schedule["schedule"].remove(lesson)
            return schedule

        return self._mutate_schedule(week, year, is_base, mut)
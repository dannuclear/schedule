# data_access/schedule_store.py
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from .paths import BASE_SCHEDULE_PATH, WEEK_SCHEDULES_DIR


class ScheduleStore:
    """Двухуровневое расписание: база (эталон) + недельные оверрайды.

    - base:   DATA_DIR/base/schedule.json       — эталон, меняется редко
    - week:   DATA_DIR/weeks/YYYY-Www/schedule.json — наследует базу,
              пока неделя не изменена явно.
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
    def _week_path(schedule_date: str | None) -> Path:
        if schedule_date is None:
            requested = date.today()
        else:
            requested = date.fromisoformat(schedule_date)  # ValueError сам по себе
        iso_year, iso_week, _ = requested.isocalendar()
        return WEEK_SCHEDULES_DIR / f"{iso_year}-W{iso_week:02d}" / "schedule.json"

    # ---- чтение ----

    def get_base(self) -> dict[str, Any]:
        return self._read(BASE_SCHEDULE_PATH)

    def get_week(self, schedule_date: str | None = None) -> dict[str, Any]:
        """Вернуть неделю. Если файла недели нет — вернуть базу
        с пометкой source='base_fallback', НЕ создавая файл."""
        week_path = self._week_path(schedule_date)
        if week_path.exists():
            return self._read(week_path)
        base = self._read(BASE_SCHEDULE_PATH)
        return {
            "meta": {**base["meta"], "week": week_path.parent.name, "source": "base_fallback"},
            "schedule": base["schedule"],
        }

    def get(self, schedule_date: str | None = None, is_base: bool = False) -> dict[str, Any]:
        return self.get_base() if is_base else self.get_week(schedule_date)

    # ---- запись ----

    def _materialize_week(self, schedule_date: str | None) -> tuple[Path, dict[str, Any]]:
        """Вернуть (путь_недели, содержимое). Если недели нет — берём базу
        и готовим meta недели (файл НЕ пишем здесь)."""
        week_path = self._week_path(schedule_date)
        if week_path.exists():
            return week_path, self._read(week_path)
        base = self._read(BASE_SCHEDULE_PATH)
        week_schedule = {
            "meta": {
                **base["meta"],
                "week": week_path.parent.name,
                "basedOnBaseVersion": base["meta"].get("version"),
                "source": "base",
            },
            "schedule": base["schedule"],
        }
        return week_path, week_schedule

    def replace_schedule(
        self,
        schedule_items: list[dict[str, Any]],
        schedule_date: str | None = None,
        is_base: bool = False,
    ) -> dict[str, Any]:
        if is_base:
            schedule = self._read(BASE_SCHEDULE_PATH)
            schedule["schedule"] = schedule_items
            self._write(BASE_SCHEDULE_PATH, schedule)
            return schedule
        week_path, schedule = self._materialize_week(schedule_date)
        schedule["schedule"] = schedule_items
        schedule["meta"]["source"] = "manual"
        self._write(week_path, schedule)
        return schedule

    # ---- точечные операции (для недели) ----

    def _mutate_week(self, schedule_date, mutator) -> dict[str, Any]:
        week_path, schedule = self._materialize_week(schedule_date)
        schedule = mutator(schedule)
        schedule["meta"]["source"] = "manual"
        self._write(week_path, schedule)
        return schedule

    def add_lesson(self, lesson: dict[str, Any], schedule_date=None) -> dict[str, Any]:
        def mut(s):
            if any(l.get("id") == lesson.get("id") for l in s["schedule"]):
                raise ValueError(f"Урок с id='{lesson.get('id')}' уже есть в неделе")
            s["schedule"].append(lesson)
            return s
        return self._mutate_week(schedule_date, mut)

    def update_lesson(self, lesson_id: str, changes: dict[str, Any], schedule_date=None) -> dict[str, Any]:
        def mut(s):
            for lesson in s["schedule"]:
                if lesson.get("id") == lesson_id:
                    lesson.update(changes)
                    return s
            raise ValueError(f"Урок с id='{lesson_id}' не найден в неделе")
        return self._mutate_week(schedule_date, mut)

    def delete_lesson(self, lesson_id: str, schedule_date=None) -> dict[str, Any]:
        def mut(s):
            for i, lesson in enumerate(s["schedule"]):
                if lesson.get("id") == lesson_id:
                    s["schedule"].pop(i)
                    return s
            raise ValueError(f"Урок с id='{lesson_id}' не найден в неделе")
        return self._mutate_week(schedule_date, mut)
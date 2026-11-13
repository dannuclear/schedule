import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

DATA_DIR = Path(__file__).resolve().parent / "data"
BASE_SCHEDULE_PATH = DATA_DIR / "base" / "schedule.json"
WEEK_SCHEDULES_DIR = DATA_DIR / "weeks"
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
LESSON_REQUIRED_FIELDS = {
    "id",
    "day",
    "slot",
    "classes",
    "subjectId",
    "kind",
    "level",
    "parts",
}


def _read_schedule(path: Path) -> dict[str, Any]:
    schedule = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(schedule, dict) or not isinstance(schedule.get("meta"), dict):
        raise ValueError(f"Некорректная структура расписания в {path}")
    if not isinstance(schedule.get("lessons"), list):
        raise ValueError(f"В {path} поле lessons должно быть списком")
    return schedule


def _write_schedule(path: Path, schedule: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(schedule, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _week_path(schedule_date: str | None) -> Path:
    if schedule_date is None:
        requested_date = date.today()
    else:
        if not DATE_PATTERN.fullmatch(schedule_date):
            raise ValueError("date должен быть в формате YYYY-MM-DD")
        try:
            requested_date = date.fromisoformat(schedule_date)
        except ValueError as error:
            raise ValueError("date должен быть корректной датой в формате YYYY-MM-DD") from error
    iso_year, iso_week, _ = requested_date.isocalendar()
    week_folder = f"{iso_year}-W{iso_week:02d}"
    return WEEK_SCHEDULES_DIR / week_folder / "schedule.json"


def _get_schedule(schedule_date: str | None, is_base: bool) -> dict[str, Any]:
    if is_base:
        return _read_schedule(BASE_SCHEDULE_PATH)

    weekly_path = _week_path(schedule_date)
    if not weekly_path.exists():
        base_schedule = _read_schedule(BASE_SCHEDULE_PATH)
        _write_schedule(weekly_path, base_schedule)
    return _read_schedule(weekly_path)


def _validate_lessons(lessons: list[dict[str, Any]]) -> None:
    seen_ids = set()
    for index, lesson in enumerate(lessons):
        if not isinstance(lesson, dict):
            raise ValueError(f"Урок с индексом {index} должен быть объектом")
        missing_fields = LESSON_REQUIRED_FIELDS - lesson.keys()
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"У урока с индексом {index} отсутствуют поля: {missing}")
        lesson_id = lesson["id"]
        if not isinstance(lesson_id, str) or not lesson_id.strip():
            raise ValueError(f"id урока с индексом {index} должен быть непустой строкой")
        if lesson_id in seen_ids:
            raise ValueError(f"Повторяется id урока: {lesson_id}")
        seen_ids.add(lesson_id)


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def get_schedule(date: str | None = None, is_base: bool = False) -> dict:
        """Получить базовое или недельное расписание.

        Args:
            date: любая дата недели в формате YYYY-MM-DD. Если пропущена,
                используется текущая дата сервера.
            is_base: если true, вернуть базовое расписание из data/base/schedule.json.
                Иначе загрузить расписание ISO-недели из data/weeks/YYYY-Www;
                если файла недели нет, создать его копией базового расписания.

        Результат содержит meta и полный массив lessons. Предмет в lesson.subjectId
        означает урок-дисциплину, а не отдельный объект занятия по дате и времени.
        """
        return _get_schedule(date, is_base)

    @server.tool()
    def update_schedule(
        lessons: list[dict[str, Any]],
        date: str | None = None,
        is_base: bool = False,
    ) -> dict:
        """Заменить весь массив lessons в базовом или недельном расписании.

        Args:
            lessons: полный новый массив уроков; каждый объект должен содержать
                id, day, slot, classes, subjectId, kind, level и parts. id должны
                быть непустыми и уникальными.
            date: любая дата нужной недели в формате YYYY-MM-DD. Если пропущена,
                используется текущая дата сервера.
            is_base: если true, изменить базовое data/base/schedule.json.
                Иначе изменить расписание ISO-недели; при отсутствии файла недели
                он сначала создаётся как копия базы.

        Метаданные meta сохраняются. Операция полностью заменяет список lessons
        в выбранном файле и записывает файл атомарно.
        """
        _validate_lessons(lessons)
        schedule = _get_schedule(date, is_base)
        schedule["lessons"] = lessons
        target_path = BASE_SCHEDULE_PATH if is_base else _week_path(date)
        _write_schedule(target_path, schedule)
        return schedule

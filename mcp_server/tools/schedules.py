from typing import Any

from mcp.server import MCPServer

from data_access import rooms_store, subjects_store, teachers_store
from data_access.schedule_store import ScheduleStore

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
PART_REQUIRED_FIELDS = {"teacherId"}

schedule_store = ScheduleStore()


# --------------------------------------------------------------------------- #
# Валидация (ссылки на справочники — на уровне инструментов)
# --------------------------------------------------------------------------- #

def _known_ids(store) -> set[str]:
    return {item.get("id") for item in store.load() if item.get("id")}


def _validate_lessons(lessons: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()

    known_subjects = _known_ids(subjects_store)
    known_teachers = _known_ids(teachers_store)
    known_rooms = _known_ids(rooms_store)

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

        if not isinstance(lesson["day"], int) or not (1 <= lesson["day"] <= 7):
            raise ValueError(f"Урок {lesson_id}: day должен быть целым числом 1..7")
        if not isinstance(lesson["slot"], int) or lesson["slot"] < 1:
            raise ValueError(f"Урок {lesson_id}: slot должен быть целым числом >= 1")
        if not isinstance(lesson["classes"], list) or not lesson["classes"]:
            raise ValueError(f"Урок {lesson_id}: classes должен быть непустым списком")
        for class_id in lesson["classes"]:
            if not isinstance(class_id, str) or not class_id.strip():
                raise ValueError(
                    f"Урок {lesson_id}: элементы classes должны быть непустыми строками"
                )

        subject_id = lesson["subjectId"]
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise ValueError(f"Урок {lesson_id}: subjectId должен быть непустой строкой")
        if known_subjects and subject_id not in known_subjects:
            raise ValueError(
                f"Урок {lesson_id}: subjectId='{subject_id}' не найден в subjects.json"
            )

        if not isinstance(lesson["parts"], list) or not lesson["parts"]:
            raise ValueError(f"Урок {lesson_id}: parts должен быть непустым списком")
        for part_index, part in enumerate(lesson["parts"]):
            if not isinstance(part, dict):
                raise ValueError(
                    f"Урок {lesson_id}: parts[{part_index}] должен быть объектом"
                )
            missing_part = PART_REQUIRED_FIELDS - part.keys()
            if missing_part:
                missing = ", ".join(sorted(missing_part))
                raise ValueError(
                    f"Урок {lesson_id}: parts[{part_index}] отсутствуют поля: {missing}"
                )
            teacher_id = part["teacherId"]
            if not isinstance(teacher_id, str) or not teacher_id.strip():
                raise ValueError(
                    f"Урок {lesson_id}: parts[{part_index}].teacherId должен быть непустой строкой"
                )
            if known_teachers and teacher_id not in known_teachers:
                raise ValueError(
                    f"Урок {lesson_id}: teacherId='{teacher_id}' не найден в teachers.json"
                )
            room_id = part.get("roomId")
            if room_id is not None:
                if not isinstance(room_id, str) or not room_id.strip():
                    raise ValueError(
                        f"Урок {lesson_id}: parts[{part_index}].roomId "
                        f"должен быть null или непустой строкой"
                    )
                if known_rooms and room_id not in known_rooms:
                    raise ValueError(
                        f"Урок {lesson_id}: roomId='{room_id}' не найден в rooms.json"
                    )


# --------------------------------------------------------------------------- #
# Инструменты
# --------------------------------------------------------------------------- #

def register_tools(server: MCPServer) -> None:
    @server.tool()
    def get_schedule(date: str | None = None, is_base: bool = False) -> dict:
        """Получить базовое или недельное расписание.

        Args:
            date: любая дата недели в формате YYYY-MM-DD. Если пропущена,
                используется текущая дата сервера.
            is_base: если true, вернуть базовое расписание.
                Иначе вернуть расписание ISO-недели. Если файла недели нет,
                вернуть базовое расписание с meta.source="base_fallback";
                файл недели при этом не создаётся.

        Результат содержит meta и полный массив lessons.
        """
        return schedule_store.get(date, is_base)

    @server.tool()
    def update_schedule(
        lessons: list[dict[str, Any]],
        date: str | None = None,
        is_base: bool = False,
    ) -> dict:
        """Заменить весь массив lessons в базовом или недельном расписании.

        Args:
            lessons: полный новый массив уроков; каждый объект должен содержать
                id, day, slot, classes, subjectId, kind, level и parts.
                Ссылки subjectId/teacherId/roomId проверяются по справочникам.
            date: любая дата нужной недели в формате YYYY-MM-DD. Если пропущена,
                используется текущая дата сервера.
            is_base: если true, изменить базовое расписание.
                Иначе изменить расписание ISO-недели; при отсутствии файла недели
                он создаётся один раз в момент записи.

        Операция полностью заменяет список lessons и записывает файл атомарно.
        """
        _validate_lessons(lessons)
        return schedule_store.replace_lessons(lessons, date, is_base)

    @server.tool()
    def add_lesson(lesson: dict[str, Any], date: str | None = None) -> dict:
        """Добавить один урок в недельное расписание.

        Args:
            lesson: объект урока (id, day, slot, classes, subjectId, kind, level, parts).
            date: любая дата нужной недели в формате YYYY-MM-DD.

        Если файла недели нет, он создаётся на основе базы, затем урок добавляется.
        id урока должен быть уникальным в пределах недели.
        """
        _validate_lessons([lesson])
        return schedule_store.add_lesson(lesson, date)

    @server.tool()
    def update_lesson(
        id: str,
        changes: dict[str, Any],
        date: str | None = None,
    ) -> dict:
        """Изменить один урок в недельном расписании по id.

        Args:
            id: идентификатор урока.
            changes: поля для изменения (например, slot, day, parts).
                id менять нельзя — поле будет проигнорировано.
            date: любая дата нужной недели в формате YYYY-MM-DD.

        Неделя должна уже существовать (быть изменённой ранее).
        """
        changes = {k: v for k, v in changes.items() if k != "id"}

        # Проверяем «слитое» состояние: существующий урок + изменения,
        # чтобы update_lesson не мог записать невалидный урок.
        current = schedule_store.get_week(date)
        target = next(
            (l for l in current["lessons"] if l.get("id") == id),
            None,
        )
        if target is None:
            raise ValueError(f"Урок с id='{id}' не найден в неделе")
        _validate_lessons([{**target, **changes}])

        return schedule_store.update_lesson(id, changes, date)

    @server.tool()
    def delete_lesson(id: str, date: str | None = None) -> dict:
        """Удалить один урок из недельного расписания по id.

        Args:
            id: идентификатор урока.
            date: любая дата нужной недели в формате YYYY-MM-DD.

        Неделя должна уже существовать (быть изменённой ранее).
        """
        return schedule_store.delete_lesson(id, date)
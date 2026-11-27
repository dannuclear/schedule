from typing import Any

from mcp.server import MCPServer

from ..data_access import rooms_store, subjects_store, teachers_store
from ..data_access.schedule_store import ScheduleStore

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


def _validate_schedule(schedule: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()

    known_subjects = _known_ids(subjects_store)
    known_teachers = _known_ids(teachers_store)
    known_rooms = _known_ids(rooms_store)

    for index, lesson in enumerate(schedule):
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

        if (
            isinstance(lesson["day"], bool)
            or not isinstance(lesson["day"], int)
            or not 1 <= lesson["day"] <= 7
        ):
            raise ValueError(f"Урок {lesson_id}: day должен быть целым числом 1..7")
        if (
            isinstance(lesson["slot"], bool)
            or not isinstance(lesson["slot"], int)
            or lesson["slot"] < 1
        ):
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


def _schedule_change_summary(
    schedule: dict[str, Any], is_base: bool
) -> dict[str, Any]:
    return {
        "meta": schedule["meta"],
        "lessonCount": len(schedule["schedule"]),
        "scope": "base" if is_base else "week",
        "backupCreated": is_base,
    }


# --------------------------------------------------------------------------- #
# Инструменты
# --------------------------------------------------------------------------- #

def register_tools(server: MCPServer) -> None:
    @server.tool()
    def get_schedule(
        week: int | None = None,
        year: int | None = None,
        day: int | None = None,
        is_base: bool = False,
    ) -> dict:
        """Получить базовое или недельное расписание.

        Args:
            week: номер ISO-недели (1–53). Указывается вместе с year.
                Если week и year пропущены, используется текущая ISO-неделя.
            year: ISO-год недели. Указывается вместе с week.
            day: необязательный день недели (1 — понедельник, 7 — воскресенье).
                Если задан, вернуть только уроки этого дня.
            is_base: если true, вернуть базовое расписание.
                Иначе вернуть расписание ISO-недели. Если файла недели нет,
                вернуть базовое расписание с meta.source="base_fallback";
                файл недели при этом не создаётся.

        Результат содержит meta и массив schedule; без day возвращаются все дни.
        """
        return schedule_store.get(
            week=week,
            year=year,
            is_base=is_base,
            day=day,
        )

    @server.tool()
    def check_schedule_conflicts(
        week: int | None = None,
        year: int | None = None,
        day: int | None = None,
        is_base: bool = False,
    ) -> dict[str, Any]:
        """Проверить занятость учителей и кабинетов в базе или выбранной неделе."""
        schedule = schedule_store.get(
            week=week,
            year=year,
            is_base=is_base,
            day=day,
        )
        conflicts = schedule_store.find_conflicts(schedule["schedule"])
        return {
            "meta": schedule["meta"],
            "hasConflicts": bool(conflicts),
            "conflicts": conflicts,
        }

    @server.tool()
    def update_schedule(
        schedule: list[dict[str, Any]],
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
    ) -> dict:
        """Заменить весь массив schedule в базовом или недельном расписании.

        Args:
            schedule: полный новый массив уроков; каждый объект должен содержать
                id, day, slot, classes, subjectId, kind, level и parts.
                Ссылки subjectId/teacherId/roomId проверяются по справочникам.
            week: номер ISO-недели. Указывается вместе с year; если оба пропущены,
                используется текущая ISO-неделя.
            year: ISO-год недели.
            is_base: если true, изменить базовое расписание.
                Иначе изменить расписание ISO-недели; при отсутствии файла недели
                он создаётся один раз в момент записи.

        Операция полностью заменяет список schedule и записывает файл атомарно.
        """
        _validate_schedule(schedule)
        updated = schedule_store.replace_schedule(
            schedule,
            week=week,
            year=year,
            is_base=is_base,
        )
        return _schedule_change_summary(updated, is_base)

    @server.tool()
    def rollback_base_schedule() -> dict[str, Any]:
        """Откатить базовое расписание к предыдущей резервной копии.

        Текущее содержимое базы будет заменено и его изменения будут потеряны.
        Для отката выбирается самая новая резервная копия.
        """
        schedule, backup_name = schedule_store.rollback_base_schedule()
        return {
            "restoredFrom": backup_name,
            "meta": schedule["meta"],
            "lessonCount": len(schedule["schedule"]),
        }

    @server.tool()
    def add_lesson(
        lesson: dict[str, Any],
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
    ) -> dict:
        """Добавить один урок в недельное расписание.

        Args:
            lesson: объект урока (id, day, slot, classes, subjectId, kind, level, parts).
            week: номер ISO-недели. Указывается вместе с year; если оба пропущены,
                используется текущая ISO-неделя.
            year: ISO-год недели.
            is_base: если true, добавить урок в базовое расписание.
                Для этого действия будет сохранена резервная копия базы.

        Для недельной записи отсутствующая неделя сначала копируется из базы.
        При is_base=true урок добавляется непосредственно в базу с резервной копией.
        id урока должен быть уникальным в выбранном расписании.
        """
        _validate_schedule([lesson])
        updated = schedule_store.add_lesson(
            lesson,
            week=week,
            year=year,
            is_base=is_base,
        )
        return {
            **_schedule_change_summary(updated, is_base),
            "lesson": lesson,
        }

    @server.tool()
    def update_lesson(
        id: str,
        changes: dict[str, Any],
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
    ) -> dict:
        """Изменить один урок в недельном расписании по id.

        Args:
            id: идентификатор урока.
            changes: поля для изменения (например, slot, day, parts).
                id менять нельзя — поле будет проигнорировано.
            week: номер ISO-недели. Указывается вместе с year; если оба пропущены,
                используется текущая ISO-неделя.
            year: ISO-год недели.
            is_base: если true, изменить базовое расписание и создать его резервную копию.

        Если недельного файла ещё нет, он создаётся на основе базы.
        """
        changes = {k: v for k, v in changes.items() if k != "id"}

        # Проверяем «слитое» состояние: существующий урок + изменения,
        # чтобы update_lesson не мог записать невалидный урок.
        target = schedule_store.get_lesson_by_id(
            id,
            week=week,
            year=year,
            is_base=is_base,
        )
        if target is None:
            source = "базовом расписании" if is_base else "неделе"
            raise ValueError(f"Урок с id='{id}' не найден в {source}")
        _validate_schedule([{**target, **changes}])

        updated = schedule_store.update_lesson(
            id,
            changes,
            week=week,
            year=year,
            is_base=is_base,
        )
        return {
            **_schedule_change_summary(updated, is_base),
            "updatedLessonId": id,
            "changes": changes,
        }

    @server.tool()
    def delete_lesson(
        id: str,
        week: int | None = None,
        year: int | None = None,
        is_base: bool = False,
    ) -> dict:
        """Удалить один урок из недельного расписания по id.

        Args:
            id: идентификатор урока.
            week: номер ISO-недели. Указывается вместе с year; если оба пропущены,
                используется текущая ISO-неделя.
            year: ISO-год недели.
            is_base: если true, удалить урок из базового расписания и создать его
                резервную копию.

        Если недельного файла ещё нет, он создаётся на основе базы.
        """
        updated = schedule_store.delete_lesson(
            id,
            week=week,
            year=year,
            is_base=is_base,
        )
        return {
            **_schedule_change_summary(updated, is_base),
            "deletedLessonId": id,
        }
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ..data_access import teachers_store
from ..data_access.schedule_store import ScheduleStore


schedule_store = ScheduleStore()


def _base_schedule_teacher_usage(teacher_id: str) -> list[dict]:
    usage = []
    for lesson in schedule_store.get_base()["schedule"]:
        matching_parts = [
            part
            for part in lesson.get("parts", [])
            if isinstance(part, dict) and part.get("teacherId") == teacher_id
        ]
        if matching_parts:
            usage.append(
                {
                    "lessonId": lesson.get("id"),
                    "day": lesson.get("day"),
                    "slot": lesson.get("slot"),
                    "classes": lesson.get("classes", []),
                }
            )
    return usage


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def list_teachers() -> list[dict]:
        """Вернуть все записи преподавателей из справочника teachers.json.

        Каждый объект содержит id, имя, полное ФИО, сокращённое имя и кабинеты
        по умолчанию.
        """
        return teachers_store.load()

    @server.tool()
    def add_teacher(
        id: str,
        name: str,
        short: str | None = None,
        full_name: str | None = None,
        default_room_ids: list[str] | None = None,
    ) -> dict:
        """Добавить преподавателя в справочник.

        Args:
            id: уникальный идентификатор преподавателя.
            name: отображаемое имя, например "Иванова А.А.".
            short: фамилия или краткое имя; если не задано, берётся первое слово name.
            full_name: полное ФИО; сохраняется в поле fullName.
            default_room_ids: список id кабинетов по умолчанию.

        Возвращает добавленную запись. Если id уже есть, операция завершится ошибкой.
        """
        teacher = {
            "id": id,
            "name": name,
            "fullName": full_name,
            "short": short or (name.split()[0] if name else None),
            "defaultRoomIds": default_room_ids or [],
        }
        return teachers_store.add(teacher)

    @server.tool()
    def update_teacher(
        id: str,
        name: str | None = None,
        short: str | None = None,
        full_name: str | None = None,
        default_room_ids: list[str] | None = None,
    ) -> dict:
        """Изменить запись преподавателя по id.

        Args:
            id: идентификатор записи для изменения.
            name: новое отображаемое имя, если нужно изменить.
            short: новое сокращённое имя.
            full_name: новое полное ФИО, сохраняется в поле fullName.
            default_room_ids: новый список кабинетов по умолчанию.

        Передавайте только поля, которые требуется изменить. Неизвестный id вызывает ошибку.
        """
        changes = {
            key: value
            for key, value in {
                "name": name,
                "short": short,
                "fullName": full_name,
                "defaultRoomIds": default_room_ids,
            }.items()
            if value is not None
        }
        return teachers_store.update(
            id,
            changes,
        )

    @server.tool()
    def delete_teacher(id: str) -> dict:
        """Удалить преподавателя из справочника, если он не используется в базовом расписании.

        Args:
            id: идентификатор преподавателя.

        Сначала проверяется базовое расписание. Если преподаватель встречается хотя бы
        в одном уроке, удаление отклоняется и возвращается описание использующих уроков.
        """
        teacher_id = id.strip()
        if not teacher_id:
            raise ToolError("id должен быть непустой строкой")

        try:
            teachers_store.require_by_id(teacher_id)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        usage = _base_schedule_teacher_usage(teacher_id)
        if usage:
            lesson_ids = ", ".join(
                str(item["lessonId"]) for item in usage if item["lessonId"]
            )
            raise ToolError(
                f"Преподаватель '{teacher_id}' используется в базовом расписании "
                f"в уроках: {lesson_ids or 'без указания id'}"
            )

        try:
            return teachers_store.delete(teacher_id)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
from mcp.server import MCPServer

from ..data_access import teachers_store


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
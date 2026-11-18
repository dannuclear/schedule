from mcp.server import MCPServer

from data_access import rooms_store


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def list_rooms(room_type: str | None = None) -> list[dict]:
        """Вернуть кабинеты и мастерские из справочника rooms.json.

        Args:
            room_type: необязательный точный фильтр по типу, например "classroom"
                или "workshop".
        """
        rooms = rooms_store.load()
        if room_type is not None:
            rooms = [room for room in rooms if room.get("type") == room_type]
        return rooms

    @server.tool()
    def get_room(id: str) -> dict:
        """Вернуть один кабинет или мастерскую по идентификатору.

        Args:
            id: id помещения, например "102" или "ТР".
        """
        return rooms_store.require_by_id(id)

    @server.tool()
    def add_room(id: str, name: str, type: str) -> dict:
        """Добавить кабинет или мастерскую в справочник.

        Args:
            id: уникальный идентификатор помещения.
            name: отображаемое название.
            type: тип помещения, например "classroom" или "workshop".

        Все поля обязательны и не должны быть пустыми.
        """
        room_id = id.strip()
        room_name = name.strip()
        room_type = type.strip()
        if not room_id or not room_name or not room_type:
            raise ValueError("id, name и type должны быть непустыми")
        return rooms_store.add(
            {"id": room_id, "name": room_name, "type": room_type}
        )

    @server.tool()
    def update_room(
        id: str,
        name: str | None = None,
        type: str | None = None,
    ) -> dict:
        """Изменить название или тип кабинета/мастерской по id.

        Args:
            id: идентификатор существующего помещения.
            name: новое отображаемое название.
            type: новый тип помещения, например "classroom" или "workshop".

        Укажите хотя бы одно изменяемое поле; пустые значения не допускаются.
        """
        changes = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("name не должен быть пустым")
            changes["name"] = name
        if type is not None:
            type = type.strip()
            if not type:
                raise ValueError("type не должен быть пустым")
            changes["type"] = type
        if not changes:
            raise ValueError("Укажите name или type для изменения")
        return rooms_store.update(id, changes)

from mcp.server import MCPServer

from JsonStore import JsonStore

teachers_store = JsonStore("teachers.json")


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def list_teachers() -> list[dict]:
        """Вернуть полный список учителей."""
        return teachers_store.load()

    @server.tool()
    def add_teacher(
        id: str,
        name: str,
        short: str | None = None,
        full_name: str | None = None,
        default_room_ids: list[str] | None = None,
    ) -> dict:
        """Добавить нового учителя. id должен быть уникальным."""
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
        """Изменить поля учителя по id. Передавайте только изменяемые поля."""
        return teachers_store.update(
            id,
            {
                "name": name,
                "short": short,
                "fullName": full_name,
                "defaultRoomIds": default_room_ids,
            },
        )
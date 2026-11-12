from mcp.server.mcpserver import MCPServer


def register_tools(
    mcp: MCPServer,
    teachers: dict[str, dict],
    classes: dict[str, dict],
) -> None:
    def teacher_view(teacher: dict) -> dict:
        """Учитель + классы, где он классный руководитель."""
        return {
            "id": teacher["id"],
            "name": teacher["name"],
            "full_name": teacher["fullName"],
            "default_rooms": teacher["defaultRoomIds"],
            "homeroom_classes": [
                c["id"]
                for c in classes.values()
                if c.get("homeroomTeacherId") == teacher["id"]
            ],
        }

    @mcp.tool()
    def list_teachers(query: str | None = None) -> list[dict]:
        """Вернуть список учителей школы или найти учителей по фрагменту ФИО.

        Используйте этот инструмент, чтобы получить список учителей или найти учителя
        перед вызовом get_teacher. Поиск по query не учитывает регистр и проверяет
        краткое и полное имя.

        Каждый результат содержит id, краткое имя, полное ФИО (может быть null),
        кабинеты по умолчанию и классы, где учитель является классным руководителем.

        Args:
            query: необязательный фрагмент фамилии или ФИО. Если не задан, вернутся все учителя.
        """
        q = query.strip().lower() if query else None
        return [
            teacher_view(teacher)
            for teacher in teachers.values()
            if not q
            or q in teacher["name"].lower()
            or q in (teacher["fullName"] or "").lower()
        ]

    @mcp.tool()
    def get_teacher(teacher_id: str) -> dict:
        """Данные одного учителя по id (например "kabanova-mg"). Id берите из list_teachers."""
        teacher = teachers.get(teacher_id)
        if not teacher:
            raise ValueError(f"Учитель {teacher_id} не найден, используйте list_teachers")
        return teacher_view(teacher)

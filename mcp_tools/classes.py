from mcp.server.mcpserver import MCPServer


def register_tools(
    mcp: MCPServer,
    teachers: dict[str, dict],
    classes: dict[str, dict],
) -> None:
    def class_view(schedule_class: dict) -> dict:
        """Класс с классным руководителем, развёрнутым из id."""
        teacher = teachers.get(schedule_class.get("homeroomTeacherId"))
        return {
            "id": schedule_class["id"],
            "grade": schedule_class["grade"],
            "letter": schedule_class["letter"],
            "stage": schedule_class["stage"],
            "student_count": schedule_class.get("studentCount"),
            "homeroom_teacher": (
                {
                    "id": teacher["id"],
                    "name": teacher["name"],
                    "full_name": teacher["fullName"],
                }
                if teacher
                else None
            ),
        }

    @mcp.tool()
    def list_classes(grade: int | None = None, stage: str | None = None) -> list[dict]:
        """Список классов. Фильтры: grade (параллель 1-11), stage (primary, basic, senior)."""
        return [
            class_view(schedule_class)
            for schedule_class in classes.values()
            if (grade is None or schedule_class["grade"] == grade)
            and (stage is None or schedule_class["stage"] == stage)
        ]

    @mcp.tool()
    def get_class(class_id: str) -> dict:
        """Данные одного класса по id (например "5а", "10б": кириллица, строчные)."""
        schedule_class = classes.get(class_id.strip().lower())
        if not schedule_class:
            raise ValueError(
                f"Класс {class_id} не найден. Доступны: {', '.join(classes)}"
            )
        return class_view(schedule_class)

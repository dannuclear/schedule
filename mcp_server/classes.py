from mcp.server import MCPServer

from JsonStore import classes_store, teachers_store

STAGES = {"primary", "basic", "senior"}


def register_tools(server: MCPServer) -> None:
    def class_view(schedule_class: dict) -> dict:
        teacher_id = schedule_class.get("homeroomTeacherId")
        teacher = teachers_store.get_by_id(teacher_id) if teacher_id else None
        return {
            **schedule_class,
            "homeroomTeacher": (
                {
                    "id": teacher["id"],
                    "name": teacher["name"],
                    "fullName": teacher.get("fullName"),
                }
                if teacher
                else None
            ),
        }

    @server.tool()
    def list_classes(grade: int | None = None, stage: str | None = None) -> list[dict]:
        """Вернуть школьные классы; в записи руководитель раскрывается в ФИО.

        Args:
            grade: необязательная параллель от 1 до 11.
            stage: необязательная ступень: "primary", "basic" или "senior".
        """
        if stage is not None and stage not in STAGES:
            raise ValueError(f"stage должен быть одним из: {', '.join(sorted(STAGES))}")
        return [
            class_view(schedule_class)
            for schedule_class in classes_store.load()
            if (grade is None or schedule_class["grade"] == grade)
            and (stage is None or schedule_class["stage"] == stage)
        ]

    @server.tool()
    def get_class(id: str) -> dict:
        """Вернуть класс по id с данными классного руководителя, если он задан.

        Args:
            id: id класса, например "5а" или "10б"; регистр буквы не важен.
        """
        return class_view(classes_store.require_by_id(id.strip().lower()))

    @server.tool()
    def add_class(
        id: str,
        grade: int,
        letter: str,
        stage: str,
        homeroom_teacher_id: str | None = None,
        student_count: int | None = None,
    ) -> dict:
        """Добавить класс в справочник.

        Args:
            id: уникальный id в формате параллель+буква, например "5а".
            grade: параллель от 1 до 11.
            letter: кириллическая буква класса, например "а".
            stage: ступень обучения: "primary", "basic" или "senior".
            homeroom_teacher_id: необязательный id существующего классного руководителя.
            student_count: необязательное число учеников, неотрицательное.

        Возвращает новую запись с раскрытыми данными классного руководителя.
        """
        class_id = id.strip().lower()
        class_letter = letter.strip().lower()
        if not class_id or not class_letter or class_id != f"{grade}{class_letter}":
            raise ValueError("id класса должен соответствовать grade и letter, например 5а")
        if not 1 <= grade <= 11:
            raise ValueError("grade должен быть от 1 до 11")
        if stage not in STAGES:
            raise ValueError(f"stage должен быть одним из: {', '.join(sorted(STAGES))}")
        if student_count is not None and student_count < 0:
            raise ValueError("student_count не может быть отрицательным")
        if homeroom_teacher_id and not teachers_store.exists(homeroom_teacher_id):
            raise ValueError(f"Учитель {homeroom_teacher_id} не найден")

        schedule_class = {
            "id": class_id,
            "grade": grade,
            "letter": class_letter,
            "stage": stage,
            "homeroomTeacherId": homeroom_teacher_id,
            "studentCount": student_count,
        }
        return class_view(classes_store.add(schedule_class))

    @server.tool()
    def update_class(
        id: str,
        stage: str | None = None,
        homeroom_teacher_id: str | None = None,
        student_count: int | None = None,
    ) -> dict:
        """Изменить ступень обучения, классного руководителя или численность класса.

        Args:
            id: id существующего класса, например "5а".
            stage: новая ступень: "primary", "basic" или "senior".
            homeroom_teacher_id: id существующего преподавателя; пустая строка
                сбрасывает классного руководителя.
            student_count: новое неотрицательное число учеников.

        Передайте хотя бы одно поле для изменения. Возвращает обновлённый класс
        с раскрытыми данными руководителя.
        """
        class_id = id.strip().lower()
        schedule_class = classes_store.require_by_id(class_id)
        changes = {}
        if stage is not None:
            if stage not in STAGES:
                raise ValueError(f"stage должен быть одним из: {', '.join(sorted(STAGES))}")
            changes["stage"] = stage
        if homeroom_teacher_id is not None:
            if homeroom_teacher_id and not teachers_store.exists(homeroom_teacher_id):
                raise ValueError(f"Учитель {homeroom_teacher_id} не найден")
            changes["homeroomTeacherId"] = homeroom_teacher_id or None
        if student_count is not None:
            if student_count < 0:
                raise ValueError("student_count не может быть отрицательным")
            changes["studentCount"] = student_count
        if not changes:
            raise ValueError("Укажите хотя бы одно поле для изменения")

        return class_view(classes_store.update(class_id, changes))

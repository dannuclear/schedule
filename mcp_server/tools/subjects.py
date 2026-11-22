from mcp.server import MCPServer

from ..data_access import subjects_store


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def list_subjects(query: str | None = None) -> list[dict]:
        """Вернуть уроки-предметы из справочника subjects.json.

        Здесь перечислены учебные дисциплины (например, математика и русский язык),
        а не отдельные занятия расписания с датой, временем и классом.

        Args:
            query: необязательный фрагмент id, названия или сокращения предмета.
                Поиск не зависит от регистра.
        """
        subjects = subjects_store.load()
        if query is None or not query.strip():
            return subjects

        search = query.strip().casefold()
        return [
            subject
            for subject in subjects
            if search in subject["id"].casefold()
            or search in subject["name"].casefold()
            or search in (subject.get("short") or "").casefold()
        ]

    @server.tool()
    def get_subject(id: str) -> dict:
        """Вернуть учебный предмет (урок-дисциплину) по id.

        Args:
            id: идентификатор предмета, например "rus" или "x-geomuprmat".
        """
        return subjects_store.require_by_id(id)

    @server.tool()
    def add_subject(id: str, name: str, short: str | None = None) -> dict:
        """Добавить урок-предмет в справочник учебных дисциплин.

        Args:
            id: уникальный идентификатор предмета.
            name: полное отображаемое название дисциплины.
            short: необязательное сокращение для расписания.

        Возвращает добавленную запись; если id занят, операция завершится ошибкой.
        """
        subject_id = id.strip()
        subject_name = name.strip()
        if not subject_id or not subject_name:
            raise ValueError("id и name должны быть непустыми")

        subject = {"id": subject_id, "name": subject_name}
        if short is not None:
            short = short.strip()
            if short:
                subject["short"] = short
        return subjects_store.add(subject)

    @server.tool()
    def update_subject(
        id: str,
        name: str | None = None,
        short: str | None = None,
    ) -> dict:
        """Изменить название или сокращение учебного предмета.

        Args:
            id: идентификатор существующего предмета.
            name: новое отображаемое название.
            short: новое сокращение для расписания.

        Укажите хотя бы одно непустое изменяемое поле.
        """
        changes = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("name не должен быть пустым")
            changes["name"] = name
        if short is not None:
            short = short.strip()
            if not short:
                raise ValueError("short не должен быть пустым")
            changes["short"] = short
        if not changes:
            raise ValueError("Укажите name или short для изменения")
        return subjects_store.update(id, changes)

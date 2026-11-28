"""MCP tools for schedule rules."""

from typing import Any

from mcp.server import MCPServer

from ..data_access import rules_store


def _validated_rules() -> list[dict[str, Any]]:
    rules = rules_store.load()
    if not isinstance(rules, list):
        raise ValueError("rules.json должен содержать JSON-массив")

    for index, rule in enumerate(rules):
        if (
            not isinstance(rule, dict)
            or not isinstance(rule.get("id"), str)
            or not rule["id"].strip()
            or not isinstance(rule.get("rule"), str)
            or not rule["rule"].strip()
        ):
            raise ValueError(
                f"Запись rules.json с индексом {index} должна содержать "
                "непустые строковые поля id и rule"
            )
    return rules


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def list_rules() -> list[dict[str, Any]]:
        """Вернуть все правила расписания из rules.json."""
        return _validated_rules()

    @server.tool()
    def add_rule(id: str, rule: str) -> dict[str, str]:
        """Добавить правило расписания.

        Args:
            id: уникальный непустой идентификатор правила.
            rule: непустой текст правила.
        """
        rule_id = id.strip()
        rule_text = rule.strip()
        if not rule_id or not rule_text:
            raise ValueError("id и rule должны быть непустыми")

        _validated_rules()
        return rules_store.add({"id": rule_id, "rule": rule_text})

    @server.tool()
    def update_rule(id: str, rule: str) -> dict[str, str]:
        """Изменить текст существующего правила по id.

        Args:
            id: идентификатор существующего правила; сам id не изменяется.
            rule: новый непустой текст правила.

        Вызывайте инструмент только после отдельного подтверждения пользователя.
        """
        rule_id = id.strip()
        rule_text = rule.strip()
        if not rule_id or not rule_text:
            raise ValueError("id и rule должны быть непустыми")

        rules = _validated_rules()
        if not any(item["id"] == rule_id for item in rules):
            raise ValueError(f"Правило с id='{rule_id}' не найдено")
        return rules_store.update(rule_id, {"rule": rule_text})

    @server.tool()
    def delete_rule(id: str) -> dict[str, Any]:
        """Удалить правило по id только после отдельного подтверждения пользователя.

        Args:
            id: идентификатор существующего правила.

        Перед вызовом спросите пользователя, подтверждает ли он удаление этого правила,
        и дождитесь отдельного явного ответа.
        """
        rule_id = id.strip()
        if not rule_id:
            raise ValueError("id должен быть непустой строкой")

        rules = _validated_rules()
        if not any(item["id"] == rule_id for item in rules):
            raise ValueError(f"Правило с id='{rule_id}' не найдено")
        return rules_store.delete(rule_id)

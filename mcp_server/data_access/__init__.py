"""Data access for the school schedule MCP server."""

from .json_store import (
    JsonStore,
    classes_store,
    rooms_store,
    rules_store,
    subjects_store,
    teachers_store,
)

__all__ = [
    "JsonStore",
    "classes_store",
    "rooms_store",
    "rules_store",
    "subjects_store",
    "teachers_store",
]

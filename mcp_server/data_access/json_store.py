import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .paths import DATA_DIR


class JsonStore:
    """Хранилище списка записей в JSON-файле с атомарной записью."""

    def __init__(self, filename: str, id_field: str = "id"):
        self.path = DATA_DIR / filename
        self.id_field = id_field

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, prefix=f".{self.path.name}-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
            tmp_path = None
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def get_by_id(self, item_id: str) -> dict[str, Any] | None:
        for item in self.load():
            if item.get(self.id_field) == item_id:
                return item
        return None

    def require_by_id(self, item_id: str) -> dict[str, Any]:
        item = self.get_by_id(item_id)
        if item is None:
            raise ValueError(f"Запись с {self.id_field}='{item_id}' не найдена в {self.path.name}")
        return item

    def exists(self, item_id: str) -> bool:
        return self.get_by_id(item_id) is not None

    def add(self, item: dict[str, Any]) -> dict[str, Any]:
        items = self.load()
        if any(i.get(self.id_field) == item.get(self.id_field) for i in items):
            raise ValueError(
                f"Запись с {self.id_field}='{item.get(self.id_field)}' уже существует"
            )
        items.append(item)
        self.save(items)
        return item

    def update(self, item_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        items = self.load()
        for item in items:
            if item.get(self.id_field) == item_id:
                for key, value in changes.items():
                    item[key] = value
                self.save(items)
                return item
        raise ValueError(f"Запись с {self.id_field}='{item_id}' не найдена")
    
    def delete(self, item_id: str) -> dict[str, Any]:
        items = self.load()
        for index, item in enumerate(items):
            if item.get(self.id_field) == item_id:
                removed = items.pop(index)
                self.save(items)
                return removed
        raise ValueError(f"Запись с {self.id_field}='{item_id}' не найдена")

teachers_store = JsonStore("teachers.json")
subjects_store = JsonStore("subjects.json")
classes_store = JsonStore("classes.json")
rooms_store = JsonStore("rooms.json")
rules_store = JsonStore("rules.json")

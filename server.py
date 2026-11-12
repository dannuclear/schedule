"""Простой MCP-сервер (HTTP): данные учителей и классов из Расписание_структура.json."""
import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from mcp_tools.classes import register_tools as register_class_tools
from mcp_tools.teachers import register_tools as register_teacher_tools

DATA_DIR = Path(__file__).parent / "data" / "base"
DATA_PATH = os.environ.get("SCHEDULE_JSON")

if DATA_PATH:
    _data = json.loads(Path(DATA_PATH).read_text(encoding="utf-8"))
    _teachers = _data["teachers"]
    _classes = _data["classes"]
else:
    _teachers = json.loads((DATA_DIR / "teachers.json").read_text(encoding="utf-8"))
    _classes = json.loads((DATA_DIR / "classes.json").read_text(encoding="utf-8"))

TEACHERS = {t["id"]: t for t in _teachers}
CLASSES = {c["id"]: c for c in _classes}  # порядок как в файле: параллель, буква

HOST = os.environ.get("MCP_HOST", "0.0.0.0")  # слушать на всех интерфейсах машины
PORT = int(os.environ.get("MCP_PORT", "8200"))

mcp = MCPServer("school-schedule", version="0.1.0")

register_teacher_tools(mcp, TEACHERS, CLASSES)
register_class_tools(mcp, TEACHERS, CLASSES)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=HOST, port=PORT)  # endpoint: http://<host>:8200/mcp
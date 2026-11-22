import logging
import os
from pathlib import Path
from time import perf_counter

from mcp.server import MCPServer
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings

# Импорт ваших инструментов
from tools.classes import register_tools as register_class_tools
from tools.rooms import register_tools as register_room_tools
from tools.schedules import register_tools as register_schedule_tools
from tools.subjects import register_tools as register_subject_tools
from tools.teachers import register_tools as register_teachers_tools
from tools.schedule_pdf import EXPORTS_DIR, register_tools as register_pdf_tools

# Импорт для работы со Starlette
from starlette.routing import Route
from starlette.responses import FileResponse
from starlette.requests import Request
from starlette.applications import Starlette

from urllib.parse import quote

# --- Ваши настройки ---
HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "8200"))
logger = logging.getLogger("school_schedule.mcp")


# --- Middleware для логирования (без изменений) ---
async def log_tool_calls(ctx: ServerRequestContext, call_next: CallNext) -> HandlerResult:
    # ... ваш код логирования ...
    return await call_next(ctx)


# --- Создаем MCP сервер ---
mcp_server = MCPServer(
    "school-schedule",
    version="0.1.0",
    description=(
            "MCP-сервер справочников школьного расписания. Предоставляет инструменты "
            "для поиска, просмотра, добавления и редактирования преподавателей, "
            "классов, кабинетов и предметов учебной программы. Предметы в этом "
            "сервере — это уроки-дисциплины из справочника subjects, а не отдельные "
            "занятия расписания с датой и временем. Предоставляет базовое расписание "
            "и отдельные копии расписания для ISO-недель."
    ),
    instructions=(
        "Используйте list_teachers для поиска и просмотра преподавателей; "
        "add_teacher требует уникальный id и имя, update_teacher изменяет "
        "переданные поля по id. Для кабинетов используйте list_rooms с "
        "необязательным фильтром room_type, get_room, add_room и update_room. "
        "Для уроков-предметов из справочника subjects используйте list_subjects "
        "(поиск по id, названию или сокращению), get_subject, add_subject и "
        "update_subject. Эти инструменты работают со справочником предметов, "
        "а не с отдельными уроками расписания. Для классов используйте "
        "list_classes с фильтрами grade и stage (primary, basic, senior), "
        "get_class, add_class и update_class. Класс может ссылаться на "
        "классного руководителя по homeroom_teacher_id; добавление проверяет, "
        "что такой преподаватель существует. Инструменты добавления требуют "
        "уникальный id. При обновлении передавайте только изменяемые поля. "
        "Для расписания используйте get_schedule с date в формате YYYY-MM-DD; "
        "без даты выбирается текущая неделя. Если недельного файла ещё нет, он "
        "создаётся копированием базового расписания. is_base=true выбирает "
        "базовое расписание. update_schedule заменяет весь массив lessons "
        "в выбранном базовом или недельном файле, сохраняя meta."
    ),
)
mcp_server.middleware.append(log_tool_calls)

# Регистрация инструментов
register_teachers_tools(mcp_server)
register_room_tools(mcp_server)
register_subject_tools(mcp_server)
register_class_tools(mcp_server)
register_schedule_tools(mcp_server)
register_pdf_tools(mcp_server)

security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

# --- Создаем ASGI приложение на основе MCP ---
# Это приложение уже содержит маршрут /mcp
app = mcp_server.streamable_http_app(transport_security=security)

def _content_disposition(filename: str) -> str:
    # ASCII fallback: заменяем не-ASCII на подчёркивания
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "download.pdf"
    # RFC 5987/6266: процентное кодирование UTF-8
    encoded_name = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"

# --- Добавляем свой маршрут для скачивания PDF ---
async def download_pdf(request: Request):
    """Отдает сгенерированный PDF-файл по имени."""
    filename = request.path_params["filename"]
    # Простая защита от path traversal
    file_path = EXPORTS_DIR / filename
    if not file_path.is_file():
        return FileResponse(status_code=404, content="File not found")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(filename)},
    )

# Добавляем маршрут в приложение.
# Важно: он добавляется ПОСЛЕ того, как streamable_http_app() установил свой /mcp
app.router.routes.append(Route("/download/{filename:path}", download_pdf))


if __name__ == "__main__":
    import uvicorn
    # Запускаем через uvicorn, а не server.run()
    uvicorn.run(app, host=HOST, port=PORT)

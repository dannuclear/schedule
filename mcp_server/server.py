import logging
import os
from time import perf_counter

from mcp.server import MCPServer
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext

from classes import register_tools as register_class_tools
from rooms import register_tools as register_room_tools
from schedules import register_tools as register_schedule_tools
from subjects import register_tools as register_subject_tools
from teachers import register_tools as register_teachers_tools

HOST = os.environ.get("MCP_HOST", "0.0.0.0")  # слушать на всех интерфейсах машины
PORT = int(os.environ.get("MCP_PORT", "8200"))
logger = logging.getLogger("school_schedule.mcp")


async def log_tool_calls(
    ctx: ServerRequestContext,
    call_next: CallNext,
) -> HandlerResult:
    if ctx.method != "tools/call":
        return await call_next(ctx)

    params = ctx.params or {}
    tool_name = params.get("name")
    if not isinstance(tool_name, str):
        tool_name = "<unknown>"
    tool_name = tool_name.replace("\r", "\\r").replace("\n", "\\n")
    started_at = perf_counter()
    logger.info("MCP tool called: %s", tool_name)

    try:
        result = await call_next(ctx)
    except Exception as error:
        elapsed = perf_counter() - started_at
        logger.error(
            "MCP tool failed: %s (%.3fs, %s)",
            tool_name,
            elapsed,
            type(error).__name__,
        )
        raise

    logger.info("MCP tool completed: %s (%.3fs)", tool_name, perf_counter() - started_at)
    return result

server = MCPServer(
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
server.middleware.append(log_tool_calls)
register_teachers_tools(server)
register_room_tools(server)
register_subject_tools(server)
register_class_tools(server)
register_schedule_tools(server)

if __name__ == "__main__":
    server.run(transport="streamable-http", host=HOST, port=PORT)
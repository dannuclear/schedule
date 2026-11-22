import logging
from time import perf_counter

from mcp.server import MCPServer
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Route

from .tools.classes import register_tools as register_class_tools
from .tools.rooms import register_tools as register_room_tools
from .tools.schedules import register_tools as register_schedule_tools
from .tools.subjects import register_tools as register_subject_tools
from .tools.teachers import register_tools as register_teachers_tools
from .tools.schedule_pdf import register_tools as register_pdf_tools
from .routes import download_pdf

logger = logging.getLogger("school_schedule.mcp")


async def log_tool_calls(ctx: ServerRequestContext, call_next: CallNext) -> HandlerResult:
    if ctx.method != "tools/call":
        return await call_next(ctx)
    params = ctx.params or {}
    tool_name = params.get("name")
    tool_name = tool_name.replace("\r", "\\r").replace("\n", "\\n") if isinstance(tool_name, str) else "<unknown>"
    started = perf_counter()
    logger.info("MCP tool called: %s", tool_name)
    try:
        result = await call_next(ctx)
    except Exception as error:
        logger.error("MCP tool failed: %s (%.3fs, %s)", tool_name, perf_counter() - started, type(error).__name__)
        raise
    logger.info("MCP tool completed: %s (%.3fs)", tool_name, perf_counter() - started)
    return result


mcp_server = MCPServer(
    "school-schedule",
    version="0.1.0",
    description=(
        "MCP-сервер для управления школьным расписанием. Предоставляет справочники "
        "преподавателей, предметов, классов и кабинетов, чтение и изменение базового "
        "расписания и отдельных недельных расписаний, а также генерацию PDF: "
        "расписания одного класса и сводных таблиц по классам, преподавателям или кабинетам."
    ),
    instructions=(
        "Используйте инструменты list/get/add/update для работы со справочниками. "
        "Для расписания используйте get_schedule с date в формате YYYY-MM-DD: если date "
        "не задана, выбирается текущая ISO-неделя; is_base=true выбирает базовое расписание. "
        "update_schedule полностью заменяет schedule, add_lesson добавляет один урок в неделю, "
        "update_lesson и delete_lesson изменяют или удаляют урок в недельном расписании. "
        "Уроки ссылаются на существующие subjectId, teacherId, roomId и classes. "
        "Для PDF используйте generate_schedule_pdf для одного класса или "
        "generate_summary_schedule_pdf для сводной таблицы с фильтрами part и day и видом view "
        "classes, teachers или rooms. Результат содержит filename, url и size готового PDF."
    ),
)
mcp_server.middleware.append(log_tool_calls)

register_teachers_tools(mcp_server)
register_room_tools(mcp_server)
register_subject_tools(mcp_server)
register_class_tools(mcp_server)
register_schedule_tools(mcp_server)
register_pdf_tools(mcp_server)

security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
app: Starlette = mcp_server.streamable_http_app(transport_security=security)
app.router.routes.append(Route("/download/{filename:path}", download_pdf))

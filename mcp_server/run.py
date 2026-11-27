import logging
import mimetypes
import os
import sys
from pathlib import Path
from time import perf_counter

from mcp.server import MCPServer
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse

if __package__ is None:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

from mcp_server.data_access.paths import EXPORTS_DIR
from mcp_server.tools.classes import register_tools as register_class_tools
from mcp_server.tools.rooms import register_tools as register_room_tools
from mcp_server.tools.rules import register_tools as register_rule_tools
from mcp_server.tools.schedules import register_tools as register_schedule_tools
from mcp_server.tools.subjects import register_tools as register_subject_tools
from mcp_server.tools.teachers import register_tools as register_teachers_tools
from mcp_server.tools.schedule_pdf import register_tools as register_pdf_tools
from mcp_server.tools.schedule_docx import register_tools as register_docx_tools

HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "8200"))
logger = logging.getLogger("school_schedule.mcp")


async def log_tool_calls(ctx: ServerRequestContext, call_next: CallNext) -> HandlerResult:
    if ctx.method != "tools/call":
        return await call_next(ctx)
    params = ctx.params or {}
    tool_name = params.get("name")
    tool_name = tool_name.replace("\r", "\\r").replace(
        "\n", "\\n") if isinstance(tool_name, str) else "<unknown>"
    started = perf_counter()
    logger.info("MCP tool called: %s", tool_name)
    try:
        result = await call_next(ctx)
    except Exception as error:
        logger.error("MCP tool failed: %s (%.3fs, %s)", tool_name,
                     perf_counter() - started, type(error).__name__)
        raise
    logger.info("MCP tool completed: %s (%.3fs)",
                tool_name, perf_counter() - started)
    return result

mcp_server = MCPServer(
    "school-schedule",
    version="0.1.0",
    description=(
        "MCP-сервер для управления школьным расписанием. Предоставляет справочники "
        "преподавателей, предметов, классов и кабинетов, чтение и изменение базового "
        "расписания и отдельных недельных расписаний, справочник правил, а также генерацию PDF и DOCX: "
        "расписания одного класса и сводных таблиц по классам, преподавателям или кабинетам. "
        "Перед любой модификацией проверяйте правила через list_rules."
    ),
    instructions=(
        "Перед планированием расписания и непосредственно перед каждой модификацией "
        "расписания или любого справочника, включая правила, вызывайте list_rules и "
        "соблюдайте сохранённые в справочнике правила. Для управления правилами используйте "
        "list_rules, add_rule и delete_rule. "
        "Используйте инструменты list/get/add/update для работы с другими справочниками. "
        "Запрос «дай расписание» означает подготовку файла, а не текстовый вывод. "
        "Если формат не указан, сначала предложите пользователю выбрать PDF или DOCX; "
        "не выбирайте формат самостоятельно и дождитесь ответа. "
        "Перед любой модификацией справочников или базового/недельного расписания "
        "получите явное подтверждение пользователя. Сам запрос на изменение подтверждением "
        "не считается; до подтверждения не вызывайте инструменты добавления, обновления, "
        "удаления или отката. "
        "Для расписания используйте get_schedule с ISO-годом year и номером недели week; "
        "если оба не заданы, выбирается текущая ISO-неделя. Необязательный day (1–7) "
        "возвращает только этот день; is_base=true выбирает базовое расписание. "
        "По умолчанию любые изменения add_lesson, update_lesson, delete_lesson и "
        "update_schedule относятся к недельному расписанию; меняйте базу только при "
        "явном указании пользователя через is_base=true. Перед добавлением или переносом "
        "проверяйте check_schedule_conflicts; изменения с занятым учителем или кабинетом "
        "отклоняются, параллельность классов не блокируется как возможная работа по группам. "
        "Изменение базы автоматически создаёт резервную копию, хранится не более 10 копий. "
        "rollback_base_schedule заменяет базу последней резервной копией "
        "и удаляет текущие изменения; вызывайте его только по явной просьбе пользователя. "
        "Инструменты изменения возвращают краткую сводку; для проверки результата "
        "запрашивайте get_schedule с нужной неделей и, по возможности, day. "
        "При изменении недели указывайте year и week; если оба не заданы, используется "
        "текущая ISO-неделя. update_schedule полностью заменяет schedule, "
        "add_lesson добавляет один урок, update_lesson и delete_lesson изменяют расписание. "
        "Уроки ссылаются на существующие subjectId, teacherId, roomId и classes. "
        "Для PDF используйте generate_schedule_pdf для одного класса или "
        "generate_summary_schedule_pdf для сводной таблицы с фильтрами part и day и видом view "
        "classes, teachers или rooms. Результат содержит filename, path, url и size готового PDF. "
        "Для таблицы Word используйте generate_day_schedule_docx с day, списком classes, "
        "year и week; дата заголовка вычисляется по ISO-неделе даже для базового расписания. "
        "Для базового расписания дополнительно передайте is_base=true. "
        "После выбора формата используйте соответствующий инструмент генерации. "
        "Для скачивания любого созданного файла сформируйте пользователю абсолютную ссылку, "
        "добавив к возвращённому url базовый адрес http://nuclearius.ru:8200."
    ),
)
mcp_server.middleware.append(log_tool_calls)


@mcp_server.custom_route("/download/{filename:path}", methods=["GET"])
async def download_pdf(request: Request):
    filename = request.path_params["filename"]
    exports_dir = EXPORTS_DIR.resolve()
    file_path = (exports_dir / filename).resolve()
    try:
        file_path.relative_to(exports_dir)
    except ValueError:
        return PlainTextResponse("File not found", status_code=404)
    if not file_path.is_file():
        return PlainTextResponse("File not found", status_code=404)
    return FileResponse(
        path=file_path,
        media_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
        filename=filename,
        content_disposition_type="inline"
    )


register_teachers_tools(mcp_server)
register_room_tools(mcp_server)
register_rule_tools(mcp_server)
register_subject_tools(mcp_server)
register_class_tools(mcp_server)
register_schedule_tools(mcp_server)
register_pdf_tools(mcp_server)
register_docx_tools(mcp_server)

security = TransportSecuritySettings(enable_dns_rebinding_protection=False)


if __name__ == "__main__":
    mcp_server.run(
        transport="streamable-http",
        host=HOST,
        port=PORT,
        transport_security=security,
    )

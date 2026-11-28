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
        "MCP для школьного расписания: базовое и недельное расписания, справочники и "
        "правила, экспорт PDF/DOCX. По умолчанию используется текущая ISO-неделя, "
        "а для запроса на один день без даты — текущая дата. Неделя при первом запросе "
        "сохраняется как копия базы."
    ),
    instructions=(
        "ЧТЕНИЕ И ЭКСПОРТ. Запрос «дай расписание» означает файл. Если формат не указан, "
        "спросите PDF или DOCX; после выбора сразу вызовите нужный инструмент генерации. "
        "Для обычного чтения/экспорта не вызывайте list_rules и check_schedule_conflicts. "
        "get_schedule: year и week указывайте вместе; если оба не заданы, используется "
        "текущая ISO-неделя. Если запрошена неделя без уточнения — берите текущую; "
        "если запрошен один день («сегодня») без даты — берите текущую дату. Названный "
        "день недели без даты относится к текущей неделе. По заданной дате вычисляйте "
        "ISO year/week и день недели; период не уточняйте. day=1..7 возвращает один день, "
        "is_base=true выбирает базу. "
        "Первый запрос недели создаёт её полную копию из текущей базы; последующие "
        "запросы и изменения работают с этой копией. "
        "PDF: generate_schedule_pdf — один класс; generate_summary_schedule_pdf — "
        "сводка по классам, учителям или кабинетам с фильтрами part/day. "
        "DOCX: generate_day_schedule_docx требует day, classes, year и week; для базы "
        "добавьте is_base=true, year/week задают дату заголовка. Ссылку на файл верните "
        "как http://nuclearius.ru:8200 + url из результата. "
        "ПЛАНИРОВАНИЕ ИЗМЕНЕНИЙ. До подбора замены или поиска свободного учителя вызовите "
        "list_rules и применяйте правила к вариантам. Для доступности используйте "
        "list_teachers и get_schedule только по затрагиваемому дню; при переносе проверьте "
        "исходный и целевой дни. Непосредственно перед каждой модификацией расписания или "
        "справочника снова проверьте list_rules. Правилами управляйте через list_rules, "
        "add_rule, update_rule и delete_rule. Для добавления/переноса проверяйте занятость "
        "через check_schedule_conflicts с day; конфликт учителя или кабинета запрещён, "
        "параллельность классов допустима для групп. Не загружайте всю неделю для точечной "
        "операции. add_lesson добавляет урок, update_lesson/delete_lesson меняют один урок; "
        "update_schedule полностью заменяет расписание. По умолчанию изменения недельные; "
        "базу меняйте только при явном is_base=true. "
        "ПОДТВЕРЖДЕНИЯ И ОТКАТ. До любой модификации получите отдельное явное подтверждение; "
        "сама просьба изменить данные подтверждением не считается. Перед любым удалением "
        "задайте отдельный вопрос и дождитесь «да»/«подтверждаю». delete_week_schedule "
        "удаляет только существующий файл указанной year/week, не базу; следующий запрос "
        "создаст неделю из текущей базы. Изменения базы автоматически сохраняются в "
        "резервной копии (максимум 10); rollback_base_schedule восстанавливает последнюю "
        "копию с потерей текущих изменений и требует явной просьбы пользователя."
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

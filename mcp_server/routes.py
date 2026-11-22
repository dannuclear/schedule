from pathlib import Path
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse

from .data_access.paths import EXPORTS_DIR


def content_disposition(filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "download.pdf"
    encoded_name = quote(filename, safe="")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}'


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
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition(filename)},
    )

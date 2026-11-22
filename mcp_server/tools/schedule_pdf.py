"""MCP tool registration for PDF generation."""

from mcp.server import MCPServer

from ..data_access import classes_store, rooms_store, subjects_store, teachers_store
from ..data_access.schedule_store import ScheduleStore
from ..data_access.paths import EXPORTS_DIR
from ..pdf.class_pdf import save_class_pdf
from ..pdf.summary_pdf import generate_summary_pdf_for_mcp

schedule_store = ScheduleStore()
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def generate_summary_schedule_pdf(
        date: str | None = None,
        is_base: bool = False,
        part: str = "all",
        day: str = "all",
        view: str = "classes",
        cell_info: str = "full",
        canvas: str = "a3",
        canvas_orientation: str = "landscape",
        size: str = "a3",
        orientation: str = "landscape",
        cell_width: float = 1.0,
        cell_height: float = 1.0,
        font_subj: float | None = None,
        font_info: float | None = None,
        line_density: float = 0.85,
    ) -> dict:
        """Сформировать сводный PDF расписания школы.

        part: beginners (1–4), basic (5–11) или all.
        day: день 1..5, название дня или all.
        view: classes, teachers или rooms.
        cell_info: full, teachers, rooms или classes.
        """
        if part not in ("beginners", "basic", "all"):
            raise ValueError("part должен быть beginners, basic или all")
        if view not in ("classes", "teachers", "rooms"):
            raise ValueError("view должен быть classes, teachers или rooms")
        if cell_info not in ("full", "teachers", "rooms", "classes"):
            raise ValueError("cell_info должен быть full, teachers, rooms или classes")

        schedule = schedule_store.get(date, is_base)
        return generate_summary_pdf_for_mcp(
            schedule,
            classes_store.load(),
            teachers_store.load(),
            rooms_store.load(),
            subjects_store.load(),
            is_base=is_base,
            part=part,
            day=day,
            view=view,
            cell_info=cell_info,
            canvas=canvas,
            canvas_orientation=canvas_orientation,
            size=size,
            orientation=orientation,
            cell_width=cell_width,
            cell_height=cell_height,
            font_subj=font_subj,
            font_info=font_info,
            line_density=line_density,
        )

    @server.tool()
    def generate_schedule_pdf(
        class_id: str,
        date: str | None = None,
        is_base: bool = False,
    ) -> dict:
        """Сформировать PDF расписания одного класса и сохранить его на сервере."""
        schedule = schedule_store.get(date, is_base)
        return save_class_pdf(
            schedule,
            class_id,
            {item["id"]: item for item in subjects_store.load()},
            {item["id"]: item for item in teachers_store.load()},
            {item["id"]: item for item in rooms_store.load()},
            is_base,
        )

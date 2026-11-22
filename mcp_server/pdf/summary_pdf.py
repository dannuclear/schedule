from ..schedule_pdf.config import DAY_ALIASES, DAY_NAMES, PART_LABEL
from ..schedule_pdf.fonts import register_cyrillic_font, resolve_bold
from ..schedule_pdf.metrics import compute_layout_metrics, resolve_pagesize
from ..schedule_pdf.model import ScheduleData
from ..schedule_pdf.render import generate_summary_pdf, output_filename

from ..data_access.paths import EXPORTS_DIR


def build_schedule_data(schedule: dict, classes: list[dict], teachers: list[dict], rooms: list[dict], subjects: list[dict]) -> ScheduleData:
    schedule_items = schedule.get("schedule", [])
    data = ScheduleData(
        meta=schedule.get("meta", {}),
        classes=classes, teachers=teachers, rooms=rooms,
        subjects=subjects, schedule=schedule_items,
    )
    data.build_indexes()
    return data


def generate_summary_pdf_for_mcp(
    schedule: dict,
    classes: list[dict], teachers: list[dict], rooms: list[dict], subjects: list[dict],
    *, is_base: bool, part: str, day: str, view: str, cell_info: str,
    canvas: str, canvas_orientation: str, size: str, orientation: str,
    cell_width: float, cell_height: float, font_subj: float | None,
    font_info: float | None, line_density: float,
) -> dict:
    day_key = day.lower().strip()
    if day_key not in DAY_ALIASES:
        raise ValueError(f"Неизвестный день: {day!r}")
    day_number = DAY_ALIASES[day_key]

    data = build_schedule_data(schedule, classes, teachers, rooms, subjects)
    data.filter_by_part(part)
    data.filter_by_day(day_number)
    days = [day_number] if day_number else [1, 2, 3, 4, 5]

    cell_width = max(0.1, float(cell_width))
    cell_height = max(0.1, float(cell_height))
    line_density = max(0.5, min(1.5, float(line_density)))

    font, _ = register_cyrillic_font()
    font_bold = resolve_bold(font)
    pagesize_pdf = resolve_pagesize(size, orientation)
    metrics = compute_layout_metrics(
        data, canvas, canvas_orientation, view, days,
        cell_width, cell_height, cell_info=cell_info,
        line_density=line_density, font=font, font_bold=font_bold,
    )
    resolved_font_subj = font_subj if font_subj is not None else metrics["font_subj"]
    resolved_font_info = font_info if font_info is not None else metrics["font_info"]

    meta = schedule.get("meta", {})
    week = meta.get("week")
    day_short = DAY_NAMES[day_number].lower() if day_number else None
    filename = output_filename(view, cell_info, part, day_short)
    if is_base:
        filename = f"{filename[:-4]}-base.pdf"
    elif week:
        filename = f"{filename[:-4]}-{week}.pdf"

    target = EXPORTS_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    generate_summary_pdf(
        data, str(target), pagesize_pdf, canvas, canvas_orientation,
        PART_LABEL[part], days, view, cell_info,
        resolved_font_subj, resolved_font_info, font, font_bold,
        line_density, cell_width, cell_height, metrics,
    )

    return {
        "filename": filename,
        "url": f"/download/{filename}",
        "size": target.stat().st_size,
        "source": meta.get("source") or ("base" if is_base else "unknown"),
        "week": week,
        "view": view,
        "part": part,
        "day": day,
    }

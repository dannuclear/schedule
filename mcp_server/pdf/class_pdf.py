import io
import os
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..data_access.paths import EXPORTS_DIR

FONT_NAME = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
DAY_NAMES = {
    1: "Понедельник", 2: "Вторник", 3: "Среда",
    4: "Четверг", 5: "Пятница", 6: "Суббота", 7: "Воскресенье",
}


def register_fonts() -> None:
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/DejaVuSans.ttf",
         "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
    ]
    for regular, bold in candidates:
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, regular))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold))
            return
        except Exception:
            continue
    raise RuntimeError("Не найден TTF-шрифт с кириллицей (DejaVuSans)")


def resolve_lesson(
    lesson: dict[str, Any],
    subjects: dict[str, dict],
    teachers: dict[str, dict],
    rooms: dict[str, dict],
) -> list[str]:
    subject = subjects.get(lesson.get("subjectId"), {})
    subject_label = subject.get("short") or subject.get("name") or lesson.get("subjectId") or "?"

    lines: list[str] = []
    for part in lesson.get("parts") or []:
        teacher = teachers.get(part.get("teacherId"), {})
        teacher_label = teacher.get("short") or teacher.get("name") or part.get("teacherId") or "?"
        room_label = ""
        if part.get("roomId") is not None:
            room = rooms.get(part["roomId"], {})
            room_label = room.get("name") or part["roomId"]
        prefix = f"гр.{part['group']}: " if len(lesson.get("parts") or []) > 1 and part.get("group") is not None else ""
        lines.append(f"{prefix}{subject_label} / {teacher_label}" + (f" / {room_label}" if room_label else ""))
    return lines or [subject_label]


def build_grid(
    schedule: list[dict[str, Any]],
    class_id: str,
    subjects: dict[str, dict],
    teachers: dict[str, dict],
    rooms: dict[str, dict],
) -> tuple[list[int], list[int], dict[tuple[int, int], list[str]]]:
    class_schedule = [lesson for lesson in schedule if class_id in (lesson.get("classes") or [])]
    if not class_schedule:
        available = sorted({item for lesson in schedule for item in (lesson.get("classes") or [])})
        raise ValueError(f"В расписании нет уроков для класса '{class_id}'. Доступные классы: {available}")

    days = sorted({lesson["day"] for lesson in class_schedule})
    slots = sorted({lesson["slot"] for lesson in class_schedule})
    cells: dict[tuple[int, int], list[str]] = {}
    for lesson in class_schedule:
        key = (lesson["day"], lesson["slot"])
        cells.setdefault(key, []).extend(resolve_lesson(lesson, subjects, teachers, rooms))
    return days, slots, cells


def render_pdf(title: str, subtitle: str, days: list[int], slots: list[int], cells: dict) -> bytes:
    register_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm, title=title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCyr", parent=styles["Title"], fontName=FONT_BOLD, fontSize=16, leading=20)
    subtitle_style = ParagraphStyle("SubtitleCyr", parent=styles["Normal"], fontName=FONT_NAME, fontSize=11, leading=14, textColor=colors.HexColor("#444444"))
    cell_style = ParagraphStyle("CellCyr", parent=styles["Normal"], fontName=FONT_NAME, fontSize=8, leading=10)
    cell_style_multi = ParagraphStyle("CellCyrMulti", parent=cell_style, fontSize=7, leading=9)

    story = [Paragraph(title, title_style), Paragraph(subtitle, subtitle_style), Spacer(1, 6 * mm)]
    data: list[list[Any]] = [["Урок"] + [DAY_NAMES.get(day, str(day)) for day in days]]
    for slot in slots:
        row: list[Any] = [str(slot)]
        for day in days:
            lines = cells.get((day, slot))
            if not lines:
                row.append("")
            else:
                style = cell_style_multi if len(lines) > 1 else cell_style
                row.append("<br/>".join(Paragraph(line, style).text for line in lines))
        data.append(row)

    for row in range(1, len(data)):
        for column in range(1, len(data[row])):
            value = data[row][column]
            if isinstance(value, str) and value:
                style = cell_style_multi if "<br/>" in value else cell_style
                data[row][column] = Paragraph(value, style)

    page_width = doc.width
    first_col = 14 * mm
    other = (page_width - first_col) / max(len(days), 1)
    table = Table(data, colWidths=[first_col] + [other] * len(days), repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f5f5f5")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def save_class_pdf(schedule: dict, class_id: str, subjects: dict, teachers: dict, rooms: dict, is_base: bool) -> dict:
    meta = schedule.get("meta", {})
    days, slots, cells = build_grid(schedule.get("schedule", []), class_id, subjects, teachers, rooms)
    title = f"Расписание · {class_id}"
    subtitle_parts = [meta.get("term") or ""]
    if meta.get("week"):
        subtitle_parts.append(f"неделя {meta['week']}")
    subtitle = " · ".join(part for part in subtitle_parts if part)

    pdf_bytes = render_pdf(title=title, subtitle=subtitle, days=days, slots=slots, cells=cells)
    week = meta.get("week")
    filename = f"schedule-{class_id}-base.pdf" if is_base else (
        f"schedule-{class_id}-{week}.pdf" if week else f"schedule-{class_id}-{date_cls.today().isoformat()}.pdf"
    )
    target = EXPORTS_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(pdf_bytes)
    return {"filename": filename, "url": f"/download/{filename}", "size": len(pdf_bytes), "source": meta.get("source") or ("base" if is_base else "unknown"), "week": week}

"""Сборка таблицы: строки — преподаватели, колонки — (день, урок)."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle

from .cell import escape
from .config import (
    DAY_NAMES, HEADER_BG, HEADER_FG, SLOT_BG, GRID, DAY_BG,
)
from .metrics import teacher_rows
from .model import ScheduleData


def _fmt_slot_number(n: int, data: ScheduleData, lesson_time: str) -> str:
    if lesson_time == "none":
        return str(n)
    s = data.slots_by_n.get(n) or {}
    start = s.get("start")
    end = s.get("end")
    if not start and not end:
        return str(n)
    if start and end:
        time_str = f"{start}–{end}"
    else:
        time_str = start or end
    if lesson_time == "short":
        return time_str
    if lesson_time == "both":
        return f"{n}\n{time_str}"
    return str(n)


def _classes_text(lessons: list[dict]) -> str:
    """Уникальные классы через ' / ', в порядке появления."""
    out: list[str] = []
    for les in lessons:
        for cc in les["classes"]:
            if cc not in out:
                out.append(cc)
    return " / ".join(out)


def _classes_paragraph(text: str, font: str, size: float) -> Paragraph:
    st = ParagraphStyle(
        "cls", fontName=font, fontSize=size,
        leading=max(1.0, size * 1.05),
        alignment=TA_CENTER,
        spaceBefore=0, spaceAfter=0,
    )
    return Paragraph(escape(text), st)


def build_teachers_table(data: ScheduleData,
                         days: list[int],
                         font_subj: float,
                         font: str, font_bold: str,
                         lesson_time: str,
                         metrics: dict) -> Table:
    """
    Шапка двухуровневая:
      верх: [Преподаватель (SPAN по вертикали)] + [Пн (SPAN по N слотов)] + …
      низ:  пусто + [1..N] + [1..N] + …
    Тело: одна строка на преподавателя; в ячейке — только классы.
    """
    slot_numbers = metrics.get("slots") or [s["n"] for s in data.slots]
    n_slots = len(slot_numbers)
    n_days = len(days)

    n_cols = 1 + n_days * n_slots

    name_col_w = metrics["name_col_w"]
    day_col_w = metrics["day_col_w"]
    row_h = metrics["row_h"]
    header_row_h = metrics["row_h"]

    teachers = teacher_rows(data)

    # ---------- шапка ----------
    header_top: list = ["Преподаватель"]
    for day in days:
        header_top.append(DAY_NAMES[day])
        header_top.extend([""] * (n_slots - 1))

    header_bottom: list = [""]
    for _ in days:
        header_bottom.extend([str(n) for n in slot_numbers])

    rows: list[list] = [header_top, header_bottom]
    row_heights: list[float] = [header_row_h, header_row_h]

    # ---------- тело ----------
    for tid in teachers:
        t = data.teachers_by_id[tid]
        teacher_name = t.get("name") or tid

        row: list = [Paragraph(
            f"<b>{teacher_name}</b>",
            ParagraphStyle("tn", fontName=font_bold,
                           fontSize=max(6, font_subj + 1),
                           alignment=TA_CENTER,
                           textColor=colors.HexColor("#2c3e50")),
        )]
        for day in days:
            for n in slot_numbers:
                lessons = data.by_teacher.get((tid, day, n), [])
                if not lessons:
                    row.append("")
                    continue
                text = _classes_text(lessons)
                row.append(_classes_paragraph(text, font, font_subj))
        rows.append(row)
        row_heights.append(row_h)

    # ---------- ширины ----------
    col_widths = [name_col_w] + [day_col_w] * (n_days * n_slots)

    # ---------- стиль ----------
    style_cmds = [
        ("FONT", (0, 0), (-1, -1), font, font_subj),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, GRID),

        ("BACKGROUND", (0, 0), (-1, 1), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 1), HEADER_FG),
        ("FONT", (0, 0), (-1, 1), font_bold, font_subj + 1),
        ("SPAN", (0, 0), (0, 1)),

        ("BACKGROUND", (0, 2), (0, -1), SLOT_BG),
        ("FONT", (0, 2), (0, -1), font_bold, font_subj + 1),

        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
    ]

    col = 1
    for _day in days:
        if n_slots > 1:
            style_cmds.append(("SPAN", (col, 0), (col + n_slots - 1, 0)))
        style_cmds.append(("BACKGROUND", (col, 0), (col + n_slots - 1, 0),
                           DAY_BG))
        style_cmds.append(("TEXTCOLOR", (col, 0), (col + n_slots - 1, 0),
                           colors.white))
        col += n_slots

    t = Table(rows, colWidths=col_widths,
              rowHeights=row_heights, repeatRows=2)
    t.setStyle(TableStyle(style_cmds))
    return t
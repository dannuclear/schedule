"""Генерация PDF-документа."""

from __future__ import annotations

import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer,
)

from .config import DAY_FULL, MARGIN_X, MARGIN_Y
from .model import ScheduleData
from .summary import build_summary


# --- заголовки и подзаголовки ---

def _title_style(font: str, size: float) -> ParagraphStyle:
    return ParagraphStyle(
        "title", fontName=font, fontSize=size, leading=size + 4,
        alignment=TA_CENTER, textColor=colors.HexColor("#2c3e50"),
        spaceAfter=6,
    )


def _subtitle_style(font: str, size: float) -> ParagraphStyle:
    return ParagraphStyle(
        "sub", fontName=font, fontSize=size, alignment=TA_CENTER,
        textColor=colors.HexColor("#7f8c8d"), spaceAfter=6,
    )


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\u0400-\u04FF\-]+", "_", s)
    return s or "file"


def make_doc(path: str, title: str, subtitle: str,
             font: str, pagesize=None) -> BaseDocTemplate:
    if pagesize is None:
        pagesize = landscape(A3)
    doc = BaseDocTemplate(
        path, pagesize=pagesize,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_Y, bottomMargin=MARGIN_Y, title=title,
    )
    # padding=0: поля страницы уже заданы через MARGIN_X/MARGIN_Y,
    # а дефолтные 6 pt Frame съедали 12 pt высоты и выталкивали
    # последние строки таблицы на второй лист.
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main",
                  leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)

    def on_page(canvas, d):
        canvas.saveState()
        canvas.setFont(font, 9)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(doc.leftMargin, 6 * mm, title)
        if subtitle:
            canvas.drawRightString(
                pagesize[0] - doc.rightMargin, 6 * mm, subtitle)
        canvas.drawCentredString(pagesize[0] / 2, 6 * mm, f"— {d.page} —")
        canvas.restoreState()

    doc.addPageTemplates(
        [PageTemplate(id="main", frames=[frame], onPage=on_page)])
    return doc


# --- имя выходного файла ---

def output_filename(view: str, cell_info: str, part: str,
                    day_short: str | None) -> str:
    parts = [f"summary_{view}"]
    if cell_info != "full":
        parts.append(cell_info)
    if part != "all":
        parts.append(part)
    if day_short:
        parts.append(day_short)
    return "_".join(parts) + ".pdf"


# --- основной вызов ---

def generate_summary_pdf(data: ScheduleData, out_path: str,
                         pagesize_pdf,
                         canvas_name: str, canvas_orient: str,
                         part_label: str | None, days: list[int],
                         view: str, cell_info: str,
                         font_subj: float, font_info: float,
                         font: str, font_bold: str,
                         line_density: float,
                         lesson_time: str,
                         cell_width_factor: float,
                         cell_height_factor: float,
                         metrics: dict) -> str:
    view_label = {"classes": "по классам",
                  "teachers": "по учителям",
                  "rooms": "по кабинетам"}[view]
    day_label = f" · {DAY_FULL[days[0]]}" if len(days) == 1 else ""
    title = (f"Сводное расписание {view_label} · "
             f"{data.meta.get('title', 'Расписание')}{day_label}")

    subtitle_parts = []
    if data.meta.get("term"):
        subtitle_parts.append(data.meta["term"])
    if part_label:
        subtitle_parts.append(part_label)
    subtitle = " · ".join(subtitle_parts)

    doc = make_doc(out_path, title, subtitle, font=font,
                   pagesize=pagesize_pdf)

    k = metrics["canvas_k"]
    t_size = max(11.0, min(24.0, 12.0 * k))
    s_size = max(8.0, min(16.0, 9.0 * k))

    story = [Paragraph(title, _title_style(font_bold, t_size))]
    if subtitle:
        story.append(Paragraph(subtitle, _subtitle_style(font, s_size)))
    story.append(Spacer(1, 4))

    table = build_summary(
        data, canvas_name, canvas_orient, view, days, cell_info,
        font_subj, font_info, font, font_bold, line_density,
        lesson_time,
        cell_width_factor, cell_height_factor,
        metrics=metrics,
    )
    story.append(table)
    doc.build(story)
    return out_path

from .teachers import build_teachers_table

def generate_teachers_pdf(data: ScheduleData, out_path: str,
                          pagesize_pdf,
                          part_label: str | None, days: list[int],
                          font_subj: float,
                          font: str, font_bold: str,
                          lesson_time: str,
                          metrics: dict) -> str:
    day_label = f" · {DAY_FULL[days[0]]}" if len(days) == 1 else ""
    title = (f"Расписание по преподавателям · "
             f"{data.meta.get('title', 'Расписание')}{day_label}")

    subtitle_parts = []
    if data.meta.get("term"):
        subtitle_parts.append(data.meta["term"])
    if part_label:
        subtitle_parts.append(part_label)
    subtitle = " · ".join(subtitle_parts)

    doc = make_doc(out_path, title, subtitle, font=font,
                   pagesize=pagesize_pdf)

    k = metrics["canvas_k"]
    t_size = max(11.0, min(24.0, 12.0 * k))
    s_size = max(8.0, min(16.0, 9.0 * k))

    story = [Paragraph(title, _title_style(font_bold, t_size))]
    if subtitle:
        story.append(Paragraph(subtitle, _subtitle_style(font, s_size)))
    story.append(Spacer(1, 4))

    table = build_teachers_table(
        data, days,
        font_subj, font, font_bold,
        lesson_time, metrics,
    )
    story.append(table)
    doc.build(story)
    return out_path
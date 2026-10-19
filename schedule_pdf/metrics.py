"""Холст, метрики ячейки, авторазмеры шрифта.

Метрики считаются один раз и используются и для PDF, и для диагностики.
Три правила, из которых всё выводится:

1. таблица обязана влезть на лист — из высоты холста вычитается место
   под заголовок (HEADER_ALLOW_MM), а Frame в render.py рисуется без
   собственных padding;
2. печатаются только занятые уроки (used_slots), а не всегда 9;
3. кегль вписывается и по ширине колонки, и по высоте строки — ширина
   берётся из реальных строк через pdfmetrics.stringWidth, поэтому
   длинные подписи («Прохорова(205) / Бакшаев(221)») не переносятся.
"""

from __future__ import annotations

from typing import Callable

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics

from .cell import cell_lines_for_lesson_group
from .config import (
    ASPECT,
    CANVAS_REF_W_MM, CANVAS_REF_H_MM,
    CELL_FILL_RATIO, CELL_PADDING, CELL_WIDTH_SAFETY,
    HEADER_ALLOW_MM, MIN_FONT_INFO, MIN_FONT_SUBJ,
    MARGIN_X, MARGIN_Y,
    ORIENTATIONS, PAGE_SIZES, ROW_HEIGHT_FACTOR,
)
from .model import ScheduleData

MAX_FONT = 18.0


# --- Холст ---

def resolve_pagesize(size_name: str, orient_name: str):
    ks = size_name.lower().strip()
    ko = orient_name.lower().strip()
    if ks not in PAGE_SIZES:
        raise ValueError(f"Неизвестный размер: {size_name!r}")
    if ko not in ORIENTATIONS:
        raise ValueError(f"Неизвестная ориентация: {orient_name!r}")
    return ORIENTATIONS[ko](PAGE_SIZES[ks])


def canvas_inner_size(canvas_name: str, orient_name: str):
    pw, ph = resolve_pagesize(canvas_name, orient_name)
    return pw - 2 * MARGIN_X, ph - 2 * MARGIN_Y


def canvas_scale(canvas_name: str, orient_name: str) -> float:
    W, H = canvas_inner_size(canvas_name, orient_name)
    area = (W / mm) * (H / mm)
    ref = CANVAS_REF_W_MM * CANVAS_REF_H_MM
    return max(0.5, min(4.0, (area / ref) ** 0.5))


# --- Колонки и строки ---

def used_slots(data: ScheduleData) -> list[int]:
    """Номера уроков, которые реально заняты в отфильтрованном наборе."""
    slots = sorted({les["slot"] for les in data.lessons})
    return slots or [s["n"] for s in data.slots[:1]] or [1]


def summary_columns(data: ScheduleData, view: str) -> list[dict]:
    import re
    if view == "classes":
        return [{"id": c["id"], "label": c["id"],
                 "stage": c["stage"]} for c in data.classes]
    if view == "teachers":
        used = {k[0] for k in data.by_teacher}
        return [{"id": t["id"], "label": t.get("short") or t["id"],
                 "stage": ""}
                for t in data.teachers if t["id"] in used]
    if view == "rooms":
        used = {k[0] for k in data.by_room}

        def key(r):
            m = re.match(r"^(\d+)$", r["id"])
            return (0, int(m.group(1))) if m else (1, r["id"])

        return [{"id": r["id"], "label": r["name"], "stage": ""}
                for r in sorted(data.rooms, key=key) if r["id"] in used]
    raise ValueError(f"Неизвестный view: {view}")


def summary_lookup(data: ScheduleData, view: str) -> Callable:
    if view == "classes":
        return lambda cid, d, s: data.by_class.get((cid, d, s), [])
    if view == "teachers":
        return lambda tid, d, s: data.by_teacher.get((tid, d, s), [])
    if view == "rooms":
        return lambda rid, d, s: data.by_room.get((rid, d, s), [])
    raise ValueError(view)


# --- Измерение содержимого ---

def text_width_per_pt(text: str, font: str) -> float:
    """Ширина строки при кегле 1 pt (в точках)."""
    if not text:
        return 0.0
    try:
        return pdfmetrics.stringWidth(text, font, 1.0)
    except Exception:                     # шрифт не зарегистрирован
        return 0.55 * len(text)


def content_extents(data: ScheduleData, view: str,
                    days: list[int], slots: list[int],
                    cell_info: str, font: str = "Helvetica",
                    font_bold: str | None = None) -> tuple[float, float]:
    """(ширина при 1 pt для первой строки, для второй) по всей таблице."""
    lookup = summary_lookup(data, view)
    head_w = 0.0
    info_w = 0.0
    for col in summary_columns(data, view):
        for day in days:
            for slot in slots:
                lessons = lookup(col["id"], day, slot)
                if not lessons:
                    continue
                lines = cell_lines_for_lesson_group(
                    lessons, data, view, cell_info)
                for i, line in enumerate(lines):
                    if not line:
                        continue
                    if i == 0:
                        head_w = max(
                            head_w, text_width_per_pt(line, font_bold or font))
                    else:
                        info_w = max(info_w, text_width_per_pt(line, font))
    return head_w, info_w


def fit_fonts(col_w: float, row_h: float,
              head_w: float, info_w: float,
              line_density: float = 0.85) -> tuple[float, float]:
    """Кегли (предмет, вторая строка), вписанные в ячейку.

    head_w/info_w — ширина самых длинных строк при кегле 1 pt.
    Учитываются и ширина колонки (строка не переносится), и высота строки:
    абзац в ячейке один, поэтому leading общий и равен
    subj_size × line_density, а две строки занимают 2 × subj_size × ld.
    """
    usable_w = max(4.0, col_w - CELL_PADDING) * CELL_WIDTH_SAFETY
    ld = max(0.5, line_density)
    budget = (row_h * CELL_FILL_RATIO) / ld      # суммарная высота в кеглях

    subj = MAX_FONT
    if head_w > 0:
        subj = min(subj, usable_w / head_w)

    info = MAX_FONT
    if info_w > 0:
        info = min(info, usable_w / info_w)
    info = min(info, 0.75 * subj)

    subj = min(subj, budget / 2.0)               # две строки по subj

    subj = max(MIN_FONT_SUBJ, subj)
    info = max(MIN_FONT_INFO, min(info, 0.75 * subj))
    return subj, info


# --- Метрики макета: сводная таблица ---

def compute_layout_metrics(data: ScheduleData,
                           canvas_name: str, canvas_orient: str,
                           view: str, days: list[int],
                           cell_width_factor: float,
                           cell_height_factor: float,
                           cell_info: str = "full",
                           line_density: float = 0.85,
                           font: str = "Helvetica",
                           font_bold: str | None = None) -> dict:
    """Считает метрики один раз — и для PDF, и для диагностики."""
    cols = summary_columns(data, view)
    n_cols = 1 + len(cols)
    slots = used_slots(data)

    W, H_canvas = canvas_inner_size(canvas_name, canvas_orient)

    base_col_w = W / n_cols
    base_row_h = base_col_w / ASPECT

    # высота холста, доступная таблице
    avail_h = max(1.0, H_canvas - HEADER_ALLOW_MM * mm)

    n_rows = 2 + len(days) * (1 + len(slots))
    units = 2 + len(days) * (ROW_HEIGHT_FACTOR + len(slots))
    row_h = min(base_row_h, avail_h / units) * cell_height_factor
    if units * row_h > avail_h:                 # cell_height_factor > 1
        row_h = avail_h / units
    day_row_h = row_h * ROW_HEIGHT_FACTOR

    col_w = base_col_w * cell_width_factor

    head_w, info_w = content_extents(
        data, view, days, slots, cell_info, font, font_bold)
    font_subj, font_info = fit_fonts(
        col_w, row_h, head_w, info_w, line_density)

    return {
        "n_cols": n_cols,
        "n_rows": n_rows,
        "slots": slots,
        "base_col_w": base_col_w,
        "base_row_h": base_row_h,
        "col_w": col_w,
        "row_h": row_h,
        "day_row_h": day_row_h,
        "canvas_w": W,
        "canvas_h": H_canvas,
        "canvas_k": canvas_scale(canvas_name, canvas_orient),
        "font_subj": font_subj,
        "font_info": font_info,
        "max_head_w": head_w,
        "max_info_w": info_w,
    }


# --- Совместимость: автошрифт по одной высоте строки ---

def auto_font_sizes(row_h_pt: float, canvas_k: float,
                    line_density: float = 0.85) -> tuple[float, float]:
    """Оценка кеглей по высоте строки, без учёта ширины колонки."""
    budget = (row_h_pt * CELL_FILL_RATIO) / max(0.5, line_density)
    subj = max(MIN_FONT_SUBJ, min(MAX_FONT, budget / 1.75))
    info = max(MIN_FONT_INFO, min(0.75 * subj, budget - subj))
    return subj, info


# --- Метрики для таблицы «по преподавателям» ---

def teacher_rows(data: ScheduleData) -> list[str]:
    """Id преподавателей, у которых есть уроки в отфильтрованном наборе."""
    used = {k[0] for k in data.by_teacher}
    return [t["id"] for t in data.teachers if t["id"] in used]


def _teachers_cell_text(data: ScheduleData, tid: str,
                        day: int, slot: int) -> str:
    lessons = data.by_teacher.get((tid, day, slot), [])
    seen: list[str] = []
    for les in lessons:
        for cls in les["classes"]:
            if cls not in seen:
                seen.append(cls)
    return " / ".join(seen)


def teachers_layout_metrics(data: ScheduleData,
                            canvas_name: str, canvas_orient: str,
                            days: list[int],
                            cell_width_factor: float,
                            cell_height_factor: float,
                            line_density: float = 0.85,
                            font: str = "Helvetica",
                            font_bold: str | None = None) -> dict:
    """Метрики для таблицы «строки — преподаватели»."""
    teachers = teacher_rows(data)
    slots = used_slots(data)
    n_slots = len(slots)
    n_days = len(days)

    W, H_canvas = canvas_inner_size(canvas_name, canvas_orient)

    n_cols = 1 + n_days * n_slots

    name_col_w = W * 0.18 * cell_width_factor
    day_col_w = ((W - name_col_w) / (n_days * n_slots) * cell_width_factor
                 if n_days * n_slots else W)

    avail_h = max(1.0, H_canvas - HEADER_ALLOW_MM * mm)
    n_body = max(1, len(teachers))
    row_h = min(day_col_w / ASPECT * cell_height_factor * 2.0,
                avail_h / (2 + n_body))

    max_w = 0.0
    for tid in teachers:
        for day in days:
            for slot in slots:
                text = _teachers_cell_text(data, tid, day, slot)
                if text:
                    max_w = max(max_w, text_width_per_pt(text, font))
    font_subj, font_info = fit_fonts(
        day_col_w, row_h, max_w, 0.0, line_density)

    return {
        "n_cols": n_cols,
        "n_rows": 2 + n_body,
        "slots": slots,
        "name_col_w": name_col_w,
        "day_col_w": day_col_w,
        "row_h": row_h,
        "day_row_h": row_h,
        "canvas_w": W,
        "canvas_h": H_canvas,
        "canvas_k": canvas_scale(canvas_name, canvas_orient),
        "font_subj": font_subj,
        "font_info": font_info,
        "max_head_w": max_w,
    }

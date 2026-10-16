"""Холст, метрики ячейки, авторазмеры шрифта."""

from __future__ import annotations

from typing import Callable

from reportlab.lib.units import mm

from .config import (
    ASPECT, ROW_HEIGHT_FACTOR,
    MARGIN_X, MARGIN_Y,
    CANVAS_REF_W_MM, CANVAS_REF_H_MM,
    PAGE_SIZES, ORIENTATIONS,
)
from .model import ScheduleData


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


# --- Колонки ---

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


# --- Метрики макета ---

def compute_layout_metrics(data: ScheduleData,
                           canvas_name: str, canvas_orient: str,
                           view: str, days: list[int],
                           cell_width_factor: float,
                           cell_height_factor: float) -> dict:
    """
    Считает все метрики один раз — и для PDF, и для диагностики.

    Высоты:
      * обычная строка урока = base_row_h × cell_height_factor;
      * строка дня недели   = base_row_h × ROW_HEIGHT_FACTOR (0.5).
    """
    cols = summary_columns(data, view)
    n_cols = 1 + len(cols)

    W, H_canvas = canvas_inner_size(canvas_name, canvas_orient)
    k = canvas_scale(canvas_name, canvas_orient)

    base_col_w = W / n_cols
    base_row_h = base_col_w / ASPECT

    # --- число строк ---
    n_rows = 2                 # шапка
    n_day_rows = 0
    n_lesson_rows = 0
    for _day in days:
        n_rows += 1            # строка дня
        n_day_rows += 1
        n_rows += 9            # 9 уроков
        n_lesson_rows += 9

    # --- высоты ---
    row_h = base_row_h * cell_height_factor
    day_row_h = base_row_h * ROW_HEIGHT_FACTOR

    # --- эффективная высота для обрезки ---
    eff_h = 2 * row_h + n_day_rows * day_row_h + n_lesson_rows * row_h
    if eff_h > H_canvas:
        k_row = H_canvas / eff_h
        row_h *= k_row
        day_row_h *= k_row

    col_w = base_col_w * cell_width_factor

    return {
        "n_cols": n_cols,
        "n_rows": n_rows,
        "base_col_w": base_col_w,
        "base_row_h": base_row_h,
        "col_w": col_w,
        "row_h": row_h,
        "day_row_h": day_row_h,
        "canvas_w": W,
        "canvas_h": H_canvas,
        "canvas_k": k,
    }


# --- Автошрифт ---

def auto_font_sizes(row_h_pt: float, canvas_k: float
                    ) -> tuple[float, float]:
    """
    Возвращает (font_subj, font_info) в pt.
    Опирается на фактическую высоту обычной строки.

    info-строка (преподаватели/кабинеты) — 0.75 от шрифта предмета.
    """
    ref_row = 22.0 * mm
    by_row = (row_h_pt / ref_row) ** 0.5
    subj = max(3.5, min(18.0, 3.0 * canvas_k * by_row))
    return subj, subj * 0.75

def teacher_rows(data: ScheduleData) -> list[str]:
    """Id преподавателей, у которых есть уроки в отфильтрованном наборе."""
    used = {k[0] for k in data.by_teacher}
    return [t["id"] for t in data.teachers if t["id"] in used]


def teachers_layout_metrics(data: ScheduleData,
                            canvas_name: str, canvas_orient: str,
                            days: list[int],
                            cell_width_factor: float,
                            cell_height_factor: float) -> dict:
    """
    Метрики для таблицы:
      колонки: 1 (ФИО) + n_days × n_slots
      строки:  2 шапки + по одной на каждого преподавателя

    Высота строк тела ×2 от базовой.
    """
    teachers = teacher_rows(data)
    n_slots = len(data.slots)
    n_days = len(days)

    W, H_canvas = canvas_inner_size(canvas_name, canvas_orient)
    k = canvas_scale(canvas_name, canvas_orient)

    n_cols = 1 + n_days * n_slots

    name_col_share = 0.18
    name_col_w = W * name_col_share * cell_width_factor
    day_col_w = (W - name_col_w) / (n_days * n_slots) * cell_width_factor

    base_row_h = day_col_w / ASPECT
    row_h = base_row_h * cell_height_factor * 2.0   # ← ×2

    n_rows = 2 + max(1, len(teachers))
    eff_h = 2 * row_h + (len(teachers) * row_h)     # шапка + тело
    if eff_h > H_canvas:
        k_row = H_canvas / eff_h
        row_h *= k_row

    return {
        "n_cols": n_cols,
        "name_col_w": name_col_w,
        "day_col_w": day_col_w,
        "row_h": row_h,
        "day_row_h": row_h,
        "canvas_w": W,
        "canvas_h": H_canvas,
        "canvas_k": k,
    }
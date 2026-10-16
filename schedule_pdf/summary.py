"""Сборка таблицы сводного расписания."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle

from .cell import cell_lines_for_lesson_group, cell_paragraph
from .config import (
    DAY_NAMES, HEADER_BG, HEADER_FG, SLOT_BG, GRID, DAY_BG,
)
from .merge import merge_equal_cells_keys
from .metrics import (
    compute_layout_metrics, summary_columns, summary_lookup,
)
from .model import ScheduleData


def format_slot_label(data: ScheduleData, slot_n: int,
                      lesson_time: str) -> str:
    if lesson_time == "none":
        return str(slot_n)
    s = data.slots_by_n.get(slot_n) or {}
    start = s.get("start")
    end = s.get("end")
    if not start and not end:
        return str(slot_n)
    if start and end:
        time_str = f"{start} – {end}"
    elif start:
        time_str = start
    else:
        time_str = end
    if lesson_time == "short":
        return time_str
    if lesson_time == "both":
        return f"{slot_n} · {time_str}"
    return str(slot_n)


def build_summary(data: ScheduleData,
                  canvas_name: str, canvas_orient: str,
                  view: str, days: list[int],
                  cell_info: str,
                  font_subj: float, font_info: float,
                  font: str, font_bold: str,
                  line_density: float,
                  lesson_time: str,
                  cell_width_factor: float,
                  cell_height_factor: float,
                  metrics: dict | None = None
                  ) -> Table:
    if metrics is None:
        metrics = compute_layout_metrics(
            data, canvas_name, canvas_orient, view, days,
            cell_width_factor, cell_height_factor,
        )

    n_cols = metrics["n_cols"]
    col_w = metrics["col_w"]
    row_h = metrics["row_h"]
    day_row_h = metrics["day_row_h"]

    cols = summary_columns(data, view)
    n = len(cols)
    lookup = summary_lookup(data, view)

    # --- шапка ---
    stage_label = {"primary": "Начальная", "basic": "Основная",
                   "senior": "Старшая"}
    if view == "classes":
        header0 = [""]
        i = 0
        while i < n:
            stage = cols[i]["stage"]
            j = i
            while j < n and cols[j]["stage"] == stage:
                j += 1
            header0.append(stage_label.get(stage, ""))
            header0.extend([""] * (j - i - 1))
            i = j
    else:
        header0 = [""] * n_cols

    header1 = ["Урок"] + [c["label"] for c in cols]

    rows: list[list] = [header0, header1]
    rows_keys: list[list] = [[None] * n_cols, [None] * n_cols]
    row_heights: list[float] = [row_h, row_h]

    day_bg_rows: list[int] = []

    # --- тело ---
    for day in days:
        # ---- строка дня недели ----
        day_row = [Paragraph(
            f"<b>{DAY_NAMES[day]}</b>",
            ParagraphStyle("d", fontName=font_bold,
                           fontSize=max(8, font_subj + 1),
                           alignment=TA_CENTER,
                           textColor=colors.white),
        )] + [""] * n
        rows.append(day_row)
        rows_keys.append([None] * n_cols)
        row_heights.append(day_row_h)
        day_bg_rows.append(len(rows) - 1)

        # ---- строки уроков ----
        for slot in range(1, 10):
            row: list = [format_slot_label(data, slot, lesson_time)]
            keys_row: list = [None]
            for c in cols:
                lessons = lookup(c["id"], day, slot)
                if not lessons:
                    row.append("")
                    keys_row.append(None)
                    continue

                lines = cell_lines_for_lesson_group(
                    lessons, data, view, cell_info)
                row.append(cell_paragraph(
                    lines,
                    subj_size=font_subj,
                    info_size=font_info,
                    font=font,
                    line_density=line_density,
                ))

                # multi_class: True, если в клетке задействовано
                # больше одного класса
                total_classes: set[str] = set()
                for les in lessons:
                    total_classes.update(les["classes"])
                keys_row.append((lines, len(total_classes) > 1))

            rows.append(row)
            rows_keys.append(keys_row)
            row_heights.append(row_h)

    # --- стиль ---
    col_widths = [col_w] * n_cols
    style_cmds = [
        ("FONT", (0, 0), (-1, -1), font, font_subj),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, GRID),
        ("BACKGROUND", (0, 0), (-1, 1), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 1), HEADER_FG),
        ("FONT", (0, 0), (-1, 1), font_bold, font_subj + 1),
        ("ALIGN", (0, 0), (-1, 1), "CENTER"),
        ("VALIGN", (0, 0), (-1, 1), "MIDDLE"),
        ("BACKGROUND", (0, 2), (0, -1), SLOT_BG),
        ("FONT", (0, 2), (0, -1), font_bold, font_subj + 1),
        ("ALIGN", (0, 2), (0, -1), "CENTER"),
        ("VALIGN", (0, 2), (0, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]

    if view == "classes":
        i = 0
        col_idx = 1
        while i < n:
            stage = cols[i]["stage"]
            j = i
            while j < n and cols[j]["stage"] == stage:
                j += 1
            if j - i > 1:
                style_cmds.append(("SPAN", (col_idx, 0),
                                   (col_idx + (j - i) - 1, 0)))
            i = j
            col_idx += (j - i)

    for ri in day_bg_rows:
        style_cmds += [
            ("BACKGROUND", (0, ri), (-1, ri), DAY_BG),
            ("SPAN", (0, ri), (-1, ri)),
            ("ALIGN", (0, ri), (-1, ri), "CENTER"),
            ("VALIGN", (0, ri), (-1, ri), "MIDDLE"),
        ]

    style_cmds.extend(merge_equal_cells_keys(rows_keys, header_rows=2))

    t = Table(rows, colWidths=col_widths,
              rowHeights=row_heights, repeatRows=2)
    t.setStyle(TableStyle(style_cmds))
    return t
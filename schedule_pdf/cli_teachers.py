"""CLI для расписания по преподавателям."""

from __future__ import annotations

import argparse
import os

from reportlab.lib.units import mm as _mm

from .config import DAY_ALIASES, DAY_NAMES, PART_LABEL, PAGE_SIZES
from .fonts import register_cyrillic_font, resolve_bold
from .metrics import (
    resolve_pagesize, teacher_rows, teachers_layout_metrics,
)
from .model import load_schedule
from .render import generate_teachers_pdf


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Расписание преподавателей → PDF.")
    ap.add_argument("json_path")
    ap.add_argument("-o", "--out", default="out")
    ap.add_argument("--part", default="all",
                    choices=["beginners", "basic", "all"])
    ap.add_argument("--day", default="all")
    ap.add_argument("--canvas", default="a3",
                    choices=sorted(PAGE_SIZES.keys()))
    ap.add_argument("--canvas-orientation", default="landscape",
                    choices=["landscape", "portrait"])
    ap.add_argument("--size", default="a3",
                    choices=sorted(PAGE_SIZES.keys()))
    ap.add_argument("--orientation", default="landscape",
                    choices=["landscape", "portrait"])
    ap.add_argument("--cell-width", type=float, default=1.0)
    ap.add_argument("--cell-height", type=float, default=1.0)
    ap.add_argument("--font-subj", type=float, default=None)
    ap.add_argument("--line-density", type=float, default=0.85)
    ap.add_argument("--lesson-time", default="none",
                    choices=["none", "short", "both"])
    return ap


def main() -> None:
    ap = build_argparser()
    args = ap.parse_args()

    part = args.part
    part_label = PART_LABEL[part]
    suffix_part = None if part == "all" else part

    day_key = args.day.lower().strip()
    if day_key not in DAY_ALIASES:
        ap.error(f"Неизвестный день: {args.day!r}")
    day_num = DAY_ALIASES[day_key]
    day_short = DAY_NAMES[day_num].lower() if day_num else None
    days = [day_num] if day_num else [1, 2, 3, 4, 5]

    pagesize_pdf = resolve_pagesize(args.size, args.orientation)
    canvas_name = args.canvas
    canvas_orient = args.canvas_orientation

    font, _ = register_cyrillic_font()
    font_bold = resolve_bold(font)

    os.makedirs(args.out, exist_ok=True)
    print(f"Загружаю {args.json_path} ...")
    data = load_schedule(args.json_path)
    print(f"  всего: классов {len(data.classes)}, "
          f"учителей {len(data.teachers)}, "
          f"кабинетов {len(data.rooms)}, уроков {len(data.lessons)}")

    data.filter_by_part(part)
    data.filter_by_day(day_num)
    print(f"  после фильтров (part={part}, day={args.day}): "
          f"классов {len(data.classes)}, уроков {len(data.lessons)}")

    cw = max(0.1, args.cell_width)
    ch = max(0.1, args.cell_height)

    metrics = teachers_layout_metrics(
        data, canvas_name, canvas_orient, days, cw, ch,
        line_density=max(0.5, min(1.5, args.line_density)),
        font=font, font_bold=font_bold,
    )

    font_subj = (args.font_subj if args.font_subj is not None
                 else metrics["font_subj"])

    teachers = teacher_rows(data)
    print(f"  логический холст: {canvas_name} / {canvas_orient} "
          f"— внутренняя область "
          f"{metrics['canvas_w'] / _mm:.1f}×"
          f"{metrics['canvas_h'] / _mm:.1f} мм, "
          f"масштаб ×{metrics['canvas_k']:.2f}")
    print(f"  формат PDF:       {args.size} / {args.orientation}")
    print(f"  преподавателей:   {len(teachers)}")
    print(f"  уроки в таблице:  {metrics['slots']}")
    print(f"  множители:        ширина ×{cw:.2f}, высота ×{ch:.2f}")
    print(f"  колонки:          ФИО {metrics['name_col_w'] / _mm:.2f} мм, "
          f"день-урок {metrics['day_col_w'] / _mm:.2f} мм")
    print(f"  строки:           {metrics['row_h'] / _mm:.2f} мм")
    print(f"  шрифт:            {font_subj:.2f} pt")
    print(f"  lesson-time:      {args.lesson_time}")

    name_parts = ["teachers"]
    if part != "all":
        name_parts.append(part)
    if day_short:
        name_parts.append(day_short)
    out_name = "_".join(name_parts) + ".pdf"
    out_path = os.path.join(args.out, out_name)

    generate_teachers_pdf(
        data, out_path, pagesize_pdf,
        part_label, days,
        font_subj, font, font_bold,
        args.lesson_time, metrics,
    )

    print(f"\nГотово. Создан файл: {out_path}")


if __name__ == "__main__":
    main()
"""CLI: argparse, main()."""

from __future__ import annotations

import argparse
import os

from reportlab.lib.units import mm as _mm

from .config import DAY_ALIASES, DAY_NAMES, PART_LABEL, PAGE_SIZES
from .fonts import register_cyrillic_font, resolve_bold
from .metrics import compute_layout_metrics, resolve_pagesize
from .model import load_schedule
from .render import generate_summary_pdf, output_filename


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Сводное расписание школы → PDF.")
    ap.add_argument("json_path")
    ap.add_argument("-o", "--out", default="out")
    ap.add_argument("--part", default="all",
                    choices=["beginners", "basic", "all"],
                    help="Часть школы: beginners (1–4) | basic (5–11) | all")
    ap.add_argument("--day", default="all",
                    help="День недели: 1..5 | пн..пт | all")
    ap.add_argument("--view", default="classes",
                    choices=["classes", "teachers", "rooms"])
    ap.add_argument("--cell-info", default="full",
                    choices=["full", "teachers", "rooms", "classes"])
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
    ap.add_argument("--font-info", type=float, default=None)
    ap.add_argument("--line-density", type=float, default=0.85)
    ap.add_argument("--lesson-time", default="none",
                    choices=["none", "short", "both"])
    return ap


def main() -> None:
    ap = build_argparser()
    args = ap.parse_args()

    # part
    part = args.part
    part_label = PART_LABEL[part]

    # day
    day_key = args.day.lower().strip()
    if day_key not in DAY_ALIASES:
        ap.error(f"Неизвестный день: {args.day!r}")
    day_num = DAY_ALIASES[day_key]
    day_short = DAY_NAMES[day_num].lower() if day_num else None
    days = [day_num] if day_num else [1, 2, 3, 4, 5]

    pagesize_pdf = resolve_pagesize(args.size, args.orientation)
    canvas_name = args.canvas
    canvas_orient = args.canvas_orientation

    line_density = max(0.5, min(1.5, args.line_density))

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

    metrics = compute_layout_metrics(
        data, canvas_name, canvas_orient, args.view, days,
        cw, ch, cell_info=args.cell_info, line_density=line_density,
        font=font, font_bold=font_bold,
    )

    font_subj = (args.font_subj if args.font_subj is not None
                 else metrics["font_subj"])
    font_info = (args.font_info if args.font_info is not None
                 else metrics["font_info"])

    # диагностика
    print(f"  логический холст: {canvas_name} / {canvas_orient} "
          f"— внутренняя область "
          f"{metrics['canvas_w'] / _mm:.1f}×"
          f"{metrics['canvas_h'] / _mm:.1f} мм, "
          f"масштаб ×{metrics['canvas_k']:.2f}")
    print(f"  формат PDF:       {args.size} / {args.orientation}")
    print(f"  вид:              {args.view}, "
          f"колонок {metrics['n_cols']}, строк {metrics['n_rows']}")
    print(f"  уроки в таблице:  {metrics['slots']}")
    print(f"  множители:        ширина ×{cw:.2f}, высота ×{ch:.2f}")
    print(f"  ячейка:           "
          f"{metrics['col_w'] / _mm:.2f}×{metrics['row_h'] / _mm:.2f} мм "
          f"(день {metrics['day_row_h'] / _mm:.2f} мм)")
    print(f"  текст в ячейке:   до {metrics['max_head_w']:.2f} и "
          f"{metrics['max_info_w']:.2f} pt ширины при 1 pt кегля")
    print(f"  шрифты:           предмет {font_subj:.2f} pt, "
          f"инфо {font_info:.2f} pt")
    print(f"  line-density:     {line_density:.2f}")
    print(f"  cell-info:        {args.cell_info}")
    print(f"  lesson-time:      {args.lesson_time}")

    out_name = output_filename(args.view, args.cell_info, part, day_short)
    out_path = os.path.join(args.out, out_name)

    generate_summary_pdf(
        data, out_path, pagesize_pdf,
        canvas_name, canvas_orient, part_label, days,
        args.view, args.cell_info, font_subj, font_info,
        font, font_bold, line_density,
        args.lesson_time,
        cw, ch, metrics,
    )

    print(f"\nГотово. Создан файл: {out_path}")


if __name__ == "__main__":
    main()
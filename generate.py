#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генерация PDF расписания одним запуском.

Вызывается из .cmd-файлов рядом («Расписание_началка.cmd» и т. п.),
но можно запускать и вручную:

    .venv\\Scripts\\python.exe generate.py beginners
    .venv\\Scripts\\python.exe generate.py basic --no-open
    .venv\\Scripts\\python.exe generate.py all -o out

Код возврата 0 — PDF создан, 1 — ошибка (сообщение печатается).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PART_TITLES = {
    "beginners": "начальная школа (1–4)",
    "basic": "основная и старшая школа (5–11)",
    "all": "вся школа",
}


def setup_console() -> None:
    """Чтобы русский текст не падал на консольной кодировке Windows."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def find_schedule(root: Path) -> Path:
    named = root / "Расписание_структура.json"
    if named.exists():
        return named
    found = sorted(p for p in root.glob("*.json") if p.is_file())
    if len(found) == 1:
        return found[0]
    if not found:
        raise SystemExit("Рядом со скриптом нет JSON с расписанием.")
    raise SystemExit(
        "В папке несколько JSON. Оставьте один или назовите нужный "
        "файл «Расписание_структура.json».")


def pdf_pages(path: Path) -> int:
    try:
        data = path.read_bytes()
    except OSError:
        return 0
    match = re.search(rb"/Count\s+(\d+)", data)
    return int(match.group(1)) if match else 0


def main() -> int:
    setup_console()

    ap = argparse.ArgumentParser(
        description="Сгенерировать PDF расписания (началка / основное / всё).")
    ap.add_argument("part", nargs="?", default="all",
                    choices=sorted(PART_TITLES),
                    help="beginners — 1–4, basic — 5–11, all — вся школа")
    ap.add_argument("-o", "--out", default=None,
                    help="папка для PDF (по умолчанию out или $SCHEDULE_OUT)")
    ap.add_argument("--open", dest="open_pdf", action="store_true",
                    default=True, help="открыть PDF после сборки (по умолчанию)")
    ap.add_argument("--no-open", dest="open_pdf", action="store_false",
                    help="не открывать PDF")
    args = ap.parse_args()

    try:
        import reportlab  # noqa: F401
    except ImportError:
        print("Не найден reportlab — генерация PDF невозможна.")
        print("Установите зависимости:  .venv\\Scripts\\pip install reportlab")
        return 1

    json_path = find_schedule(ROOT)
    out_dir = Path(args.out or os.environ.get("SCHEDULE_OUT") or "out")
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    print(f"=== Расписание: {PART_TITLES[args.part]} ===")
    print(f"Исходные данные: {json_path.name}")
    print(f"Папка результата: {out_dir}")
    print()

    # вызов штатного CLI библиотеки
    sys.argv = ["run.py", str(json_path),
                "--part", args.part, "-o", str(out_dir)]
    try:
        from schedule_pdf.cli import main as cli_main
        cli_main()
    except SystemExit as exc:               # argparse
        return int(exc.code or 0)
    except Exception as exc:                # ошибка генерации
        print()
        print(f"Не удалось собрать PDF: {type(exc).__name__}: {exc}")
        return 1

    pdfs = sorted(out_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
    if not pdfs:
        print("PDF не появился — проверьте сообщения выше.")
        return 1

    result = pdfs[-1]
    size_kb = result.stat().st_size / 1024
    pages = pdf_pages(result)
    print()
    print(f"Готово: {result.name} — {size_kb:.1f} КБ"
          + (f", страниц: {pages}" if pages else ""))

    if args.open_pdf:
        try:
            os.startfile(str(result))       # type: ignore[attr-defined]
        except Exception as exc:
            print(f"(открыть автоматически не удалось: {exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

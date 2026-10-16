#!/usr/bin/env python3
"""
Генератор PDF-расписания из JSON-файла (всё на одной странице).

Использование:
    python generate_pdf.py input.json output.pdf [--pagesize A2|A1|A0]

Формат входного JSON:
{
  "classes": {
    "1А": "Сафронова Е.Л.",
    ...
  },
  "schedule": {
    "Понедельник": {
      "1": {
        "1А": { "предмет": "РоВ", "кабинет": "" },
        ...
      },
      ...
    },
    ...
  }
}
"""

import json
import sys
import os
import argparse
from reportlab.lib.pagesizes import A0, A1, A2, A3, A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER


# ---------- ШРИФТЫ ----------
def register_fonts():
    """Пытается подключить шрифт с поддержкой кириллицы."""
    candidates = [
        ("DejaVuSans", "DejaVuSans-Bold", [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/DejaVuSans.ttf",
            "fonts/DejaVuSans.ttf",
        ], [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/Library/Fonts/DejaVuSans-Bold.ttf",
            "fonts/DejaVuSans-Bold.ttf",
        ]),
        ("Arial", "Arial-Bold", [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/Arial.ttf",
        ], [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/Arial-Bold.ttf",
        ]),
    ]
    for regular_name, bold_name, regular_paths, bold_paths in candidates:
        reg_path = next((p for p in regular_paths if os.path.exists(p)), None)
        bold_path = next((p for p in bold_paths if os.path.exists(p)), None)
        if reg_path and bold_path:
            try:
                pdfmetrics.registerFont(TTFont(regular_name, reg_path))
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                print(f"[OK] Используется шрифт: {regular_name}")
                return regular_name, bold_name
            except Exception as e:
                print(f"[WARN] Не удалось загрузить {regular_name}: {e}")
    print("[WARN] Кириллические шрифты не найдены, используется Helvetica.")
    return "Helvetica", "Helvetica-Bold"


# ---------- РАЗМЕРЫ СТРАНИЦ ----------
PAGESIZES = {
    "A0": A0,
    "A1": A1,
    "A2": A2,
    "A3": A3,
    "A4": A4,
}


# ---------- ГЕНЕРАЦИЯ ----------
def build_pdf(json_path: str, output_path: str, pagesize_name: str = "A2"):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    classes = data.get("classes", {})
    schedule = data.get("schedule", {})

    days_order = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
    days_order = [d for d in days_order if d in schedule]
    classes_order = list(classes.keys())

    # Максимальное количество уроков в любом дне
    max_lesson = 0
    for day_data in schedule.values():
        for key in day_data.keys():
            try:
                max_lesson = max(max_lesson, int(key))
            except ValueError:
                pass
    if max_lesson == 0:
        max_lesson = 9

    font_regular, font_bold = register_fonts()

    # Размер страницы
    base_size = PAGESIZES.get(pagesize_name.upper(), A2)
    pagesize = landscape(base_size)

    # Документ без полей (все поля внутри таблицы)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=pagesize,
        leftMargin=6 * mm,
        rightMargin=6 * mm,
        topMargin=6 * mm,
        bottomMargin=6 * mm,
        title="Расписание уроков",
    )

    # ---------- АВТОПОДБОР РАЗМЕРА ШРИФТА ----------
    # Чем больше классов и уроков — тем меньше шрифт.
    n_classes = len(classes_order)
    n_lessons = max_lesson
    # Верхняя и нижняя границы
    if pagesize_name.upper() == "A0":
        base_font = 11
    elif pagesize_name.upper() == "A1":
        base_font = 10
    elif pagesize_name.upper() == "A2":
        base_font = 9
    elif pagesize_name.upper() == "A3":
        base_font = 8
    else:
        base_font = 7

    cell_font_size = max(6, base_font - max(0, (n_classes - 10) // 3))
    title_font_size = cell_font_size + 8
    head_font_size = cell_font_size
    day_font_size = cell_font_size + 1

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Title"],
        fontName=font_bold, fontSize=title_font_size,
        alignment=TA_CENTER, spaceAfter=4,
    )
    cell_style = ParagraphStyle(
        "CellStyle", parent=styles["Normal"],
        fontName=font_regular, fontSize=cell_font_size,
        leading=cell_font_size + 1.5, alignment=TA_CENTER,
    )
    head_style = ParagraphStyle(
        "HeadStyle", parent=styles["Normal"],
        fontName=font_bold, fontSize=head_font_size,
        leading=head_font_size + 1.5,
        alignment=TA_CENTER, textColor=colors.white,
    )
    day_style = ParagraphStyle(
        "DayStyle", parent=styles["Normal"],
        fontName=font_bold, fontSize=day_font_size,
        leading=day_font_size + 2,
        alignment=TA_CENTER, textColor=colors.white,
    )

    # ---------- СБОРКА ТАБЛИЦЫ ----------
    n_cols = 1 + len(classes_order)
    table_data = []

    # Шапка с классами и ФИО
    header_row = [Paragraph("Урок", head_style)] + [
        Paragraph(f"{cls}<br/><font size={max(5, head_font_size - 2)}>{classes.get(cls, '')}</font>", head_style)
        for cls in classes_order
    ]
    table_data.append(header_row)

    span_styles = []
    current_row = 1

    for day in days_order:
        day_data = schedule.get(day, {})
        # Строка-заголовок дня
        day_row = [Paragraph(day, day_style)] + [""] * len(classes_order)
        table_data.append(day_row)
        span_styles.append(("SPAN", (0, current_row), (-1, current_row)))
        span_styles.append(("BACKGROUND", (0, current_row), (-1, current_row), colors.HexColor("#1F4E79")))
        current_row += 1

        # Уроки
        for lesson_num in range(1, max_lesson + 1):
            lesson_key = str(lesson_num)
            lesson_info = day_data.get(lesson_key, {})
            row = [Paragraph(str(lesson_num), cell_style)]
            for cls in classes_order:
                cell = lesson_info.get(cls)
                if not cell:
                    row.append("")
                    continue
                subject = cell.get("предмет", "")
                room = cell.get("кабинет", "")
                if room:
                    text = f"{subject}<br/><font size={max(5, cell_font_size - 1.5)} color='#555555'>{room}</font>"
                else:
                    text = subject
                row.append(Paragraph(text, cell_style))
            table_data.append(row)
            current_row += 1

    # Ширина столбцов
    usable_width = doc.width
    first_col_w = 10 * mm
    col_w = (usable_width - first_col_w) / len(classes_order)
    col_widths = [first_col_w] + [col_w] * len(classes_order)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    base_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D3B66")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#AAAAAA")),
        ("FONTNAME", (0, 0), (-1, -1), font_regular),
        ("FONTSIZE", (0, 0), (-1, -1), cell_font_size),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
    ]

    # Зебра для строк уроков
    zebra_styles = []
    current_row = 1
    for _day in days_order:
        current_row += 1  # строка дня
        for i in range(max_lesson):
            color = colors.white if i % 2 == 0 else colors.HexColor("#F0F5FA")
            zebra_styles.append(("BACKGROUND", (0, current_row), (-1, current_row), color))
            current_row += 1

    # Выделение первого столбца
    first_col_styles = []
    current_row = 1
    for _day in days_order:
        current_row += 1
        for _ in range(max_lesson):
            first_col_styles.append(
                ("BACKGROUND", (0, current_row), (0, current_row), colors.HexColor("#E6EEF7"))
            )
            current_row += 1

    table.setStyle(TableStyle(base_style + span_styles + zebra_styles + first_col_styles))

    # Титул + таблица
    story = [
        Paragraph("Расписание уроков", title_style),
        Spacer(1, 3),
        table,
    ]

    doc.build(story)
    print(f"[OK] PDF сохранён: {output_path}")
    print(f"     Формат: {pagesize_name.upper()} landscape, шрифт: {cell_font_size}pt")


# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Генератор PDF-расписания из JSON.")
    parser.add_argument("input", help="Путь к входному JSON-файлу")
    parser.add_argument("output", help="Путь к выходному PDF-файлу")
    parser.add_argument(
        "--pagesize", default="A2",
        choices=["A0", "A1", "A2", "A3", "A4"],
        help="Формат страницы (по умолчанию A2)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] Файл не найден: {args.input}")
        sys.exit(1)

    build_pdf(args.input, args.output, args.pagesize)


if __name__ == "__main__":
    main()
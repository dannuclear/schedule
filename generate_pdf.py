#!/usr/bin/env python3
"""
Генератор PDF-расписания из JSON-файла.

Использование:
    python generate_pdf.py input.json output.pdf

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
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
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
        ], [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/Library/Fonts/DejaVuSans-Bold.ttf",
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
                print(f"[OK] Используется шрифт: {regular_name} ({reg_path})")
                return regular_name, bold_name
            except Exception as e:
                print(f"[WARN] Не удалось загрузить {regular_name}: {e}")
    print("[WARN] Кириллические шрифты не найдены, используется Helvetica.")
    return "Helvetica", "Helvetica-Bold"


# ---------- ГЕНЕРАЦИЯ ----------
def build_pdf(json_path: str, output_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    classes = data.get("classes", {})
    schedule = data.get("schedule", {})

    # Порядок дней и классов
    days_order = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
    days_order = [d for d in days_order if d in schedule]
    classes_order = list(classes.keys())
    max_lesson = 9

    font_regular, font_bold = register_fonts()

    # Размеры страницы: A3 landscape, чтобы всё уместилось
    pagesize = landscape(A3)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=pagesize,
        leftMargin=6 * mm,
        rightMargin=6 * mm,
        topMargin=6 * mm,
        bottomMargin=6 * mm,
        title="Расписание уроков",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Title"],
        fontName=font_bold, fontSize=18, alignment=TA_CENTER, spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "CellStyle", parent=styles["Normal"],
        fontName=font_regular, fontSize=7, leading=8.5, alignment=TA_CENTER,
    )
    head_style = ParagraphStyle(
        "HeadStyle", parent=styles["Normal"],
        fontName=font_bold, fontSize=8, leading=9.5,
        alignment=TA_CENTER, textColor=colors.white,
    )
    day_style = ParagraphStyle(
        "DayStyle", parent=styles["Normal"],
        fontName=font_bold, fontSize=9, leading=11,
        alignment=TA_CENTER, textColor=colors.white,
    )

    story = []
    story.append(Paragraph("Расписание уроков", title_style))
    story.append(Spacer(1, 4))

    # Единая таблица: строки = (день × уроки) + заголовки дней
    # Столбцы: 1 (№ урока) + N классов
    n_cols = 1 + len(classes_order)
    table_data = []

    # Верхняя шапка с названиями классов
    header_row = [Paragraph("Класс", head_style)] + [
        Paragraph(
            f"{cls}<br/><font size=6>{classes.get(cls, '')}</font>",
            head_style,
        )
        for cls in classes_order
    ]
    table_data.append(header_row)

    # Стили для тела таблицы
    span_styles = []
    row_styles = []

    current_row = 1
    for day in days_order:
        day_data = schedule.get(day, {})
        # Строка-заголовок дня (объединение по всем столбцам)
        day_row = [Paragraph(day, day_style)] + [""] * len(classes_order)
        table_data.append(day_row)
        span_styles.append(("SPAN", (0, current_row), (-1, current_row)))
        span_styles.append(("BACKGROUND", (0, current_row), (-1, current_row), colors.HexColor("#1F4E79")))
        current_row += 1

        # Строки уроков
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
                    text = f"{subject}<br/><font size=6 color='#555555'>{room}</font>"
                else:
                    text = subject
                row.append(Paragraph(text, cell_style))
            table_data.append(row)
            current_row += 1

    # Ширина столбцов
    usable_width = doc.width
    first_col_w = 9 * mm
    col_w = (usable_width - first_col_w) / len(classes_order)
    col_widths = [first_col_w] + [col_w] * len(classes_order)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    base_style = [
        # Шапка
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D3B66")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#AAAAAA")),
        ("FONTNAME", (0, 0), (-1, -1), font_regular),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
    ]

    # Чередование фона для строк уроков внутри каждого дня
    zebra_styles = []
    current_row = 1
    for _day in days_order:
        current_row += 1  # строка дня
        for i in range(max_lesson):
            if i % 2 == 0:
                zebra_styles.append(
                    ("BACKGROUND", (0, current_row), (-1, current_row), colors.white)
                )
            else:
                zebra_styles.append(
                    ("BACKGROUND", (0, current_row), (-1, current_row), colors.HexColor("#F0F5FA"))
                )
            current_row += 1

    # Выделение первого столбца (номер урока)
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
    story.append(table)

    doc.build(story)
    print(f"[OK] PDF сохранён: {output_path}")


# ---------- CLI ----------
def main():
    if len(sys.argv) < 3:
        print("Использование: python generate_pdf.py input.json output.pdf")
        sys.exit(1)
    json_path = sys.argv[1]
    output_path = sys.argv[2]
    if not os.path.exists(json_path):
        print(f"[ERROR] Файл не найден: {json_path}")
        sys.exit(1)
    build_pdf(json_path, output_path)


if __name__ == "__main__":
    main()
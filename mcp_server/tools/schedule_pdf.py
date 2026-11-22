import base64
import io
from datetime import date as date_cls
import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from data_access import rooms_store, subjects_store, teachers_store
from data_access.schedule_store import ScheduleStore
from data_access.paths import DATA_DIR, EXPORTS_DIR

schedule_store = ScheduleStore()

# Папка для готовых PDF. Лежит рядом с DATA_DIR, чтобы не смешивать
# с исходными JSON. Можно вынести в отдельную переменную окружения.
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Публичный базовый URL, по которому Open WebUI сможет скачать файл.
# Например, "http://192.168.1.10:8200". Если сервер и клиент на одной машине,
# можно оставить пустым и возвращать относительный путь /download/...
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

DAY_NAMES = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье",
}

# Шрифт с кириллицей. DejaVuSans есть в большинстве дистрибутивов Linux.
# Если его нет — замените путь на локальный TTF.
FONT_NAME = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"


def _register_fonts() -> None:
    """Регистрирует TTF с кириллицей. Безопасно вызывать многократно."""
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/DejaVuSans.ttf",
         "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
    ]
    for regular, bold in candidates:
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, regular))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold))
            return
        except Exception:
            continue
    raise RuntimeError(
        "Не найден TTF-шрифт с кириллицей (DejaVuSans). "
        "Установите fonts-dejavu или укажите путь в _register_fonts."
    )


def _load_lookup(store) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in store.load() if item.get("id")}


def _resolve_lesson(lesson: dict[str, Any],
                    subjects: dict[str, dict],
                    teachers: dict[str, dict],
                    rooms: dict[str, dict]) -> list[str]:
    """Вернуть список строк-подписей для ячейки расписания.

    Для обычного урока — одна строка: «Предмет / Учитель / Каб.».
    Для урока с несколькими parts (группы/потоки) — по строке на part.
    """
    subject = subjects.get(lesson.get("subjectId"), {})
    subject_label = subject.get("short") or subject.get("name") or lesson.get("subjectId") or "?"

    lines: list[str] = []
    parts = lesson.get("parts") or []
    multi = len(parts) > 1

    for part in parts:
        teacher = teachers.get(part.get("teacherId"), {})
        teacher_label = teacher.get("short") or teacher.get("name") or part.get("teacherId") or "?"
        room_id = part.get("roomId")
        room_label = ""
        if room_id is not None:
            room = rooms.get(room_id, {})
            room_label = room.get("name") or room_id

        group = part.get("group")
        prefix = f"гр.{group}: " if multi and group is not None else ""
        if room_label:
            lines.append(f"{prefix}{subject_label} / {teacher_label} / {room_label}")
        else:
            lines.append(f"{prefix}{subject_label} / {teacher_label}")

    if not lines:
        lines.append(subject_label)
    return lines


def _build_grid(
    lessons: list[dict[str, Any]],
    class_id: str,
    subjects: dict[str, dict],
    teachers: dict[str, dict],
    rooms: dict[str, dict],
) -> tuple[list[int], list[int], dict[tuple[int, int], list[str]]]:
    """Построить сетку (день, слот) → список подписей для указанного класса."""
    class_lessons = [l for l in lessons if class_id in (l.get("classes") or [])]
    if not class_lessons:
        raise ValueError(
            f"В расписании нет уроков для класса '{class_id}'. "
            f"Доступные классы: {sorted({c for l in lessons for c in (l.get('classes') or [])})}"
        )

    days = sorted({l["day"] for l in class_lessons})
    slots = sorted({l["slot"] for l in class_lessons})

    cells: dict[tuple[int, int], list[str]] = {}
    for lesson in class_lessons:
        key = (lesson["day"], lesson["slot"])
        # Если в одной ячейке несколько уроков (поток/параллель) — склеиваем.
        cells.setdefault(key, []).extend(
            _resolve_lesson(lesson, subjects, teachers, rooms)
        )
    return days, slots, cells


def _render_pdf(
    *,
    title: str,
    subtitle: str,
    days: list[int],
    slots: list[int],
    cells: dict[tuple[int, int], list[str]],
) -> bytes:
    _register_fonts()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCyr",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=16,
        leading=20,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleCyr",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#444444"),
    )
    cell_style = ParagraphStyle(
        "CellCyr",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=8,
        leading=10,
    )
    cell_style_multi = ParagraphStyle(
        "CellCyrMulti",
        parent=cell_style,
        fontSize=7,
        leading=9,
    )

    story = [
        Paragraph(title, title_style),
        Paragraph(subtitle, subtitle_style),
        Spacer(1, 6 * mm),
    ]

    header = ["Урок"] + [DAY_NAMES.get(d, str(d)) for d in days]
    data: list[list[Any]] = [header]

    for slot in slots:
        row: list[Any] = [str(slot)]
        for day in days:
            lines = cells.get((day, slot))
            if not lines:
                row.append("")
            else:
                style = cell_style_multi if len(lines) > 1 else cell_style
                row.append(
                    "<br/>".join(
                        Paragraph(line, style).text for line in lines
                    )
                )
        data.append(row)

    # Заменяем «сырой» текст на Paragraph — иначе не переносится.
    for r in range(1, len(data)):
        for c in range(1, len(data[r])):
            if isinstance(data[r][c], str) and data[r][c]:
                style = cell_style_multi if "<br/>" in data[r][c] else cell_style
                data[r][c] = Paragraph(data[r][c], style)

    # Ширины: первый столбец узкий, остальные равные.
    page_width = doc.width
    first_col = 14 * mm
    other = (page_width - first_col) / max(len(days), 1)
    col_widths = [first_col] + [other] * len(days)

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f5f5f5")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Инструменты
# --------------------------------------------------------------------------- #

def register_tools(server: MCPServer) -> None:
    @server.tool()
    def generate_schedule_pdf(
        class_id: str,
        date: str | None = None,
        is_base: bool = False,
    ) -> dict:
        """Сформировать PDF-расписание для одного класса и сохранить его на сервере.

        Args:
            class_id: идентификатор класса, например "10а" или "5б".
            date: любая дата недели в формате YYYY-MM-DD. Если пропущена,
                используется текущая дата сервера.
            is_base: если true — печатать базовое расписание; иначе недельное
                (с fallback на базу, если неделя ещё не менялась).

        Возвращает объект:
            {
              "filename": "schedule-10а-2026-W36.pdf",
              "url": "http://.../download/schedule-10а-2026-W36.pdf",
              "size": <bytes>,
              "source": "base" | "base_fallback" | "manual",
              "week": "2026-W36" | null,
            }
        По url файл можно скачать напрямую.
        """
        schedule = schedule_store.get(date, is_base)
        meta = schedule.get("meta", {})

        subjects = _load_lookup(subjects_store)
        teachers = _load_lookup(teachers_store)
        rooms = _load_lookup(rooms_store)

        days, slots, cells = _build_grid(
            schedule.get("lessons", []),
            class_id,
            subjects,
            teachers,
            rooms,
        )

        title = f"Расписание · {class_id}"
        subtitle_parts = [meta.get("term") or ""]
        if meta.get("week"):
            subtitle_parts.append(f"неделя {meta['week']}")
        subtitle = " · ".join(p for p in subtitle_parts if p) or ""

        pdf_bytes = _render_pdf(
            title=title,
            subtitle=subtitle,
            days=days,
            slots=slots,
            cells=cells,
        )

        week = meta.get("week")
        if is_base:
            filename = f"schedule-{class_id}-base.pdf"
        elif week:
            filename = f"schedule-{class_id}-{week}.pdf"
        else:
            filename = f"schedule-{class_id}-{date_cls.today().isoformat()}.pdf"

        # Сохраняем PDF на диск
        target_path = EXPORTS_DIR / filename
        target_path.write_bytes(pdf_bytes)

        # Формируем URL для скачивания
        url_path = f"/download/{filename}"
        url = f"{PUBLIC_BASE_URL}{url_path}" if PUBLIC_BASE_URL else url_path

        return {
            "filename": filename,
            "url": url,
            "size": len(pdf_bytes),
            "source": meta.get("source") or ("base" if is_base else "unknown"),
            "week": week,
        }
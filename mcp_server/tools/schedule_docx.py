"""MCP tool for exporting selected classes' daily schedule to DOCX."""

import hashlib
from datetime import date
from io import BytesIO
from typing import Any

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from mcp.server import MCPServer

from ..data_access import classes_store, subjects_store
from ..data_access.paths import EXPORTS_DIR
from ..data_access.schedule_store import ScheduleStore

DAY_NAMES = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье",
}

MONTH_NAMES = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

PAGE_CONTENT_WIDTH_CM = 27.3
LESSON_COLUMN_WIDTH_CM = 1.5

schedule_store = ScheduleStore()


def _label(record: dict[str, Any] | None, fallback: str) -> str:
    if record is None:
        return fallback
    return record.get("short") or record.get("name") or fallback


def _lesson_text(
    lesson: dict[str, Any],
    subjects: dict[str, dict[str, Any]],
) -> str:
    subject_id = lesson.get("subjectId")
    subject = _label(subjects.get(subject_id), subject_id or "—")
    parts = lesson.get("parts") or []
    room_ids = list(
        dict.fromkeys(
            str(part["roomId"])
            for part in parts
            if part.get("roomId") not in (None, "")
        )
    )
    return f"{subject} {'/'.join(room_ids)}".rstrip()


def _shade_cell(cell: Any, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    properties.append(shading)


def build_day_schedule_docx(
    schedule: dict[str, Any],
    year: int,
    week: int,
    day: int,
    class_ids: list[str],
    subjects: dict[str, dict[str, Any]],
) -> bytes:
    if not class_ids:
        raise ValueError("class_ids должен содержать хотя бы один id класса")
    calendar_date = date.fromisocalendar(year, week, day)
    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Cm(29.7)
    section.page_height = Cm(21.0)
    section.top_margin = Cm(1.2)
    section.bottom_margin = Cm(1.2)
    section.left_margin = Cm(1.2)
    section.right_margin = Cm(1.2)

    title = document.add_heading(
        f"РАСПИСАНИЕ НА {calendar_date.day} "
        f"{MONTH_NAMES[calendar_date.month]} ({DAY_NAMES[day].lower()})",
        level=1,
    )
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    table = document.add_table(rows=1, cols=len(class_ids) + 1)
    table.style = "Table Grid"
    table.autofit = False
    class_column_width = (
        PAGE_CONTENT_WIDTH_CM - LESSON_COLUMN_WIDTH_CM
    ) / len(class_ids)
    table.columns[0].width = Cm(LESSON_COLUMN_WIDTH_CM)
    for column_index in range(1, len(class_ids) + 1):
        table.columns[column_index].width = Cm(class_column_width)

    headers = ("Урок", *class_ids)
    for cell, header in zip(table.rows[0].cells, headers):
        cell.text = header
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        _shade_cell(cell, "D9D9D9")
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9)

    header_properties = table.rows[0]._tr.get_or_add_trPr()
    repeated_header = OxmlElement("w:tblHeader")
    repeated_header.set(qn("w:val"), "true")
    header_properties.append(repeated_header)

    lessons = [
        lesson
        for lesson in schedule.get("schedule", [])
        if lesson.get("day") == day
    ]
    for slot in range(1, 10):
        lessons_by_class = {class_id: [] for class_id in class_ids}
        for lesson in lessons:
            if lesson.get("slot") != slot:
                continue
            for class_id in class_ids:
                if class_id in (lesson.get("classes") or []):
                    lessons_by_class[class_id].append(lesson)

        row = table.add_row()
        row.cells[0].text = str(slot)
        _shade_cell(row.cells[0], "D9D9D9")
        for paragraph in row.cells[0].paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

        merge_ranges = []
        class_index = 0
        while class_index < len(class_ids):
            class_lessons = lessons_by_class[class_ids[class_index]]
            signature = tuple(
                sorted(str(lesson.get("id", "")) for lesson in class_lessons)
            )
            end_index = class_index
            while end_index + 1 < len(class_ids):
                next_lessons = lessons_by_class[class_ids[end_index + 1]]
                next_signature = tuple(
                    sorted(str(lesson.get("id", "")) for lesson in next_lessons)
                )
                if next_signature != signature:
                    break
                end_index += 1

            if end_index > class_index and signature and all(
                all(
                    class_id in (lesson.get("classes") or [])
                    for class_id in class_ids[class_index : end_index + 1]
                )
                for lesson in class_lessons
            ):
                merge_ranges.append((class_index, end_index))
            class_index = end_index + 1

        merged_starts = {start: end for start, end in merge_ranges}
        class_index = 0
        while class_index < len(class_ids):
            end_index = merged_starts.get(class_index, class_index)
            cell = row.cells[class_index + 1]
            if end_index > class_index:
                cell = cell.merge(row.cells[end_index + 1])
            cell.text = "\n".join(
                _lesson_text(lesson, subjects)
                for lesson in lessons_by_class[class_ids[class_index]]
            )
            class_index = end_index + 1

    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.paragraph_format.space_after = Pt(0)
                for run in paragraph.runs:
                    run.font.size = Pt(9)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def register_tools(server: MCPServer) -> None:
    @server.tool()
    def generate_day_schedule_docx(
        day: int,
        classes: list[str],
        year: int,
        week: int,
        is_base: bool = False,
    ) -> dict[str, Any]:
        """Создать DOCX-таблицу расписания выбранных классов за один день.

        Args:
            day: день недели от 1 (понедельник) до 7 (воскресенье).
            classes: непустой список id классов, например ["5а", "6б"].
            year: ISO-год, используемый для определения даты в заголовке.
            week: номер ISO-недели от 1 до 53 для определения даты в заголовке.
            is_base: если true, сформировать документ по базовому расписанию;
                year и week при этом нужны только для даты в заголовке.
        """
        if not classes:
            raise ValueError("classes должен содержать хотя бы один id класса")
        if any(
            not isinstance(class_id, str) or not class_id.strip()
            for class_id in classes
        ):
            raise ValueError("каждый элемент classes должен быть непустой строкой")

        selected_classes = [class_id.strip().lower() for class_id in classes]
        if len(set(selected_classes)) != len(selected_classes):
            raise ValueError("classes не должен содержать повторяющиеся id")

        class_records = {
            record["id"]: record for record in classes_store.load()
        }
        unknown_classes = [
            class_id for class_id in selected_classes if class_id not in class_records
        ]
        if unknown_classes:
            raise ValueError(f"Неизвестные классы: {', '.join(unknown_classes)}")

        schedule = schedule_store.get(
            week=week,
            year=year,
            day=day,
            is_base=is_base,
        )
        subjects = {item["id"]: item for item in subjects_store.load()}
        document_bytes = build_day_schedule_docx(
            schedule,
            year,
            week,
            day,
            selected_classes,
            subjects,
        )

        class_hash = hashlib.sha256(
            "\0".join(selected_classes).encode("utf-8")
        ).hexdigest()[:10]
        schedule_label = (
            f"base-{year}-W{week:02d}" if is_base else f"{year}-W{week:02d}"
        )
        filename = f"schedule-{schedule_label}-day-{day}-{class_hash}.docx"
        target = EXPORTS_DIR / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(document_bytes)

        return {
            "filename": filename,
            "path": str(target),
            "url": f"/download/{filename}",
            "size": len(document_bytes),
            "year": year,
            "week": week,
            "day": day,
            "classes": selected_classes,
            "isBase": is_base,
        }

"""MCP tool for exporting selected classes' daily schedule to DOCX."""

import hashlib
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

from ..data_access import classes_store, rooms_store, subjects_store, teachers_store
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

TABLE_WIDTHS_CM = (2.2, 1.4, 5.0, 12.0, 6.0)

schedule_store = ScheduleStore()


def _label(record: dict[str, Any] | None, fallback: str) -> str:
    if record is None:
        return fallback
    return record.get("short") or record.get("name") or fallback


def _lesson_cells(
    lesson: dict[str, Any],
    subjects: dict[str, dict[str, Any]],
    teachers: dict[str, dict[str, Any]],
    rooms: dict[str, dict[str, Any]],
) -> tuple[str, str, str]:
    subject_id = lesson.get("subjectId")
    subject = _label(subjects.get(subject_id), subject_id or "—")
    parts = lesson.get("parts") or []
    teacher_labels = []
    room_labels = []

    for part in parts:
        group_prefix = (
            f"Группа {part['group']}: "
            if len(parts) > 1 and part.get("group") is not None
            else ""
        )
        teacher_id = part.get("teacherId")
        teacher_labels.append(
            group_prefix + _label(teachers.get(teacher_id), teacher_id or "—")
        )

        room_id = part.get("roomId")
        if room_id:
            room_labels.append(
                group_prefix + _label(rooms.get(room_id), room_id)
            )

    return subject, "\n".join(teacher_labels), "\n".join(room_labels)


def build_day_schedule_docx(
    schedule: dict[str, Any],
    year: int | None,
    week: int | None,
    day: int,
    class_ids: list[str],
    class_names: dict[str, str],
    subjects: dict[str, dict[str, Any]],
    teachers: dict[str, dict[str, Any]],
    rooms: dict[str, dict[str, Any]],
    is_base: bool,
) -> bytes:
    if not is_base and (year is None or week is None):
        raise ValueError("Для недельного расписания необходимо указать year и week")

    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Cm(29.7)
    section.page_height = Cm(21.0)
    section.top_margin = Cm(1.2)
    section.bottom_margin = Cm(1.2)
    section.left_margin = Cm(1.2)
    section.right_margin = Cm(1.2)

    title_prefix = "Базовое расписание" if is_base else "Расписание"
    title = document.add_heading(
        f"{title_prefix} — {DAY_NAMES[day]}", level=1
    )
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if is_base:
        document.add_paragraph("Источник: базовое расписание")
    else:
        document.add_paragraph(f"ISO-неделя: {year}-W{week:02d}")
    document.add_paragraph(
        "Классы: " + ", ".join(class_names[class_id] for class_id in class_ids)
    )

    table = document.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    headers = ("Класс", "Урок", "Предмет", "Учитель", "Кабинет")
    for cell, header in zip(table.rows[0].cells, headers):
        cell.text = header
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9)

    header_properties = table.rows[0]._tr.get_or_add_trPr()
    repeated_header = OxmlElement("w:tblHeader")
    repeated_header.set(qn("w:val"), "true")
    header_properties.append(repeated_header)

    lessons = schedule.get("schedule", [])
    for class_id in class_ids:
        class_lessons = sorted(
            (
                lesson for lesson in lessons
                if class_id in (lesson.get("classes") or [])
            ),
            key=lambda lesson: (lesson.get("slot", 0), lesson.get("id", "")),
        )
        if not class_lessons:
            values = [class_names[class_id], "—", "Нет уроков", "", ""]
            row = table.add_row()
            for cell, value in zip(row.cells, values):
                cell.text = value
        else:
            for lesson in class_lessons:
                subject, teacher, room = _lesson_cells(
                    lesson, subjects, teachers, rooms
                )
                values = [
                    class_names[class_id],
                    str(lesson["slot"]),
                    subject,
                    teacher,
                    room,
                ]
                row = table.add_row()
                for cell, value in zip(row.cells, values):
                    cell.text = value

    for row in table.rows:
        for cell, width in zip(row.cells, TABLE_WIDTHS_CM):
            cell.width = Cm(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for paragraph in cell.paragraphs:
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
        year: int | None = None,
        week: int | None = None,
        is_base: bool = False,
    ) -> dict[str, Any]:
        """Создать DOCX-таблицу расписания выбранных классов за один день.

        Args:
            day: день недели от 1 (понедельник) до 7 (воскресенье).
            classes: непустой список id классов, например ["5а", "6б"].
            year: ISO-год расписания; обязателен для недельного режима.
            week: номер ISO-недели от 1 до 53; обязателен для недельного режима.
            is_base: если true, сформировать документ по базовому расписанию;
                в этом режиме year и week не требуются.
        """
        if not is_base and (year is None or week is None):
            raise ValueError("Для недельного расписания необходимо указать year и week")
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
        class_names = {
            class_id: class_records[class_id].get("name") or class_id
            for class_id in selected_classes
        }
        subjects = {item["id"]: item for item in subjects_store.load()}
        teachers = {item["id"]: item for item in teachers_store.load()}
        rooms = {item["id"]: item for item in rooms_store.load()}
        document_bytes = build_day_schedule_docx(
            schedule,
            year,
            week,
            day,
            selected_classes,
            class_names,
            subjects,
            teachers,
            rooms,
            is_base,
        )

        class_hash = hashlib.sha256(
            "\0".join(selected_classes).encode("utf-8")
        ).hexdigest()[:10]
        schedule_label = (
            "base" if is_base else f"{year}-W{week:02d}"
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
            "year": None if is_base else year,
            "week": None if is_base else week,
            "day": day,
            "classes": selected_classes,
            "isBase": is_base,
        }

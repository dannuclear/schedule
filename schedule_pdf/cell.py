"""Содержимое ячейки: предмет(ы) и инфо, всё через ' / '."""

from __future__ import annotations

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

from .config import KIND_MARKS
from .model import ScheduleData


def escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _pair(teacher: str, room: str) -> str:
    if teacher and room:
        return f"{teacher}({room})"
    if teacher:
        return teacher
    if room:
        return f"({room})"
    return ""


def lesson_cell_texts(lesson: dict, data: ScheduleData, mode: str,
                      cell_info: str) -> tuple[str, str]:
    """(head, info) для одного урока."""
    subj = data.subjects_by_id.get(lesson["subjectId"], {})
    subj_short = subj.get("short") or subj.get("name") or lesson["subjectId"]
    level = lesson.get("level")
    kind = lesson.get("kind", "regular")

    head_parts = [subj_short]
    if level:
        head_parts.append(level)
    mark = KIND_MARKS.get(kind, "")
    if mark and kind != "regular":
        head_parts.append(mark)
    head = " ".join(head_parts)

    cls_str = ", ".join(lesson["classes"])

    pairs: list[str] = []
    teachers_only: list[str] = []
    rooms_only: list[str] = []
    for p in lesson.get("parts", []) or []:
        t = data.teachers_by_id.get(p.get("teacherId") or "", {})
        teacher = (t.get("short") or t.get("name", "")) if t else ""
        room = p.get("roomId") or ""
        pr = _pair(teacher, room)
        if pr:
            pairs.append(pr)
        if teacher:
            teachers_only.append(teacher)
        if room:
            rooms_only.append(room)

    pairs_str = " / ".join(pairs)
    teachers_str = " / ".join(teachers_only)
    rooms_str = " / ".join(rooms_only)

    if cell_info == "full":
        if mode in ("teachers", "rooms"):
            bits = []
            if cls_str:
                bits.append(cls_str)
            if pairs_str:
                bits.append(pairs_str)
            info = " / ".join(bits)
        else:
            info = pairs_str
    elif cell_info == "teachers":
        info = teachers_str
    elif cell_info == "rooms":
        info = rooms_str
    elif cell_info == "classes":
        info = cls_str
    else:
        info = ""

    return head, info


def _parallel_key(lesson: dict) -> tuple:
    return (
        lesson.get("day"),
        lesson.get("slot"),
        tuple(sorted(lesson.get("classes", []))),
    )


def cell_lines_for_lesson_group(lessons: list[dict], data: ScheduleData,
                                mode: str, cell_info: str) -> list[str]:
    """
    Две строки: [предметы, инфо].
    Уроки группируются по (day, slot, classes); между группами — ' / ',
    внутри группы — тоже ' / ' (все элементы одной параллели).
    """
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for les in lessons:
        key = _parallel_key(les)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(les)

    subj_parts: list[str] = []
    info_parts: list[str] = []

    for key in order:
        grp = sorted(groups[key], key=lambda l: l["id"])
        for les in grp:
            head, info = lesson_cell_texts(les, data, mode, cell_info)
            subj_parts.append(head)
            if info:
                info_parts.append(info)

    return [" / ".join(subj_parts), " / ".join(info_parts)]


def cell_paragraph(lines: list[str], *,
                   subj_size: float,
                   info_size: float,
                   font: str,
                   line_density: float,
                   align=TA_CENTER) -> Paragraph:
    base_size = max(subj_size, info_size)
    leading = max(1.0, base_size * line_density)

    st_empty = ParagraphStyle(
        "cell-empty", fontName=font, fontSize=subj_size,
        leading=leading, alignment=align,
    )

    if not lines:
        return Paragraph("", st_empty)
    while lines and not lines[-1]:
        lines = lines[:-1]
    if not lines:
        return Paragraph("", st_empty)

    chunks: list[str] = []
    for i, raw in enumerate(lines):
        if not raw:
            continue
        if i == 0:
            chunks.append(f'<font size="{subj_size:.1f}">'
                         f'<b>{escape(raw)}</b></font>')
        else:
            chunks.append(f'<font size="{info_size:.1f}">'
                         f'{escape(raw)}</font>')
    html = "<br/>".join(chunks)

    st = ParagraphStyle(
        "cell", fontName=font, fontSize=subj_size,
        leading=leading, alignment=align,
        spaceBefore=0, spaceAfter=0,
    )
    return Paragraph(html, st)
"""Константы: размеры листов, цвета, пропорции, дни."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import (
    A3, A4, A5, LETTER, LEGAL, landscape, portrait,
)
from reportlab.lib.units import mm


# --- Размеры листов ---

_MM = 72.0 / 25.4  # мм в pt

PAGE_SIZES = {
    "a0": (841 * _MM, 1189 * _MM),
    "a1": (594 * _MM, 841 * _MM),
    "a2": (420 * _MM, 594 * _MM),
    "a3": A3,
    "a4": A4,
    "a5": A5,
    "letter": LETTER,
    "legal": LEGAL,
}

ORIENTATIONS = {
    "landscape": landscape,
    "portrait": portrait,
    "l": landscape,
    "p": portrait,
}


# --- Дни недели ---

DAY_NAMES = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт"}
DAY_FULL = {1: "Понедельник", 2: "Вторник", 3: "Среда",
            4: "Четверг", 5: "Пятница"}

DAY_ALIASES = {
    "1": 1, "пн": 1, "понедельник": 1, "mon": 1,
    "2": 2, "вт": 2, "вторник": 2, "tue": 2,
    "3": 3, "ср": 3, "среда": 3, "wed": 3,
    "4": 4, "чт": 4, "четверг": 4, "thu": 4,
    "5": 5, "пт": 5, "пятница": 5, "fri": 5,
    "all": 0, "все": 0, "вся": 0, "": 0,
}


# --- Части школы ---

PART_LABEL = {
    "beginners": "Начальная школа (1–4)",
    "basic": "Основная и старшая школа (5–11)",
    "all": None,
}


# --- Типы занятий ---

KIND_MARKS = {
    "igz": "ИГЗ",
    "ovz": "ОВЗ",
    "homeroom": "",
    "regular": "",
}


# --- Геометрия таблицы ---

ASPECT = 4.0                # ширина / высота обычной ячейки
ROW_HEIGHT_FACTOR = 1.5     # множитель высоты строки дня недели

MARGIN_X = 10 * mm
MARGIN_Y = 12 * mm

# Опорные значения для автошрифта (холст A3 landscape)
CANVAS_REF_W_MM = 400.0
CANVAS_REF_H_MM = 273.0


# --- Цвета ---

HEADER_BG = colors.HexColor("#2c3e50")
HEADER_FG = colors.white
SLOT_BG = colors.HexColor("#ecf0f1")
GRID = colors.HexColor("#bdc3c7")
DAY_BG = colors.HexColor("#34495e")
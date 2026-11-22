"""Регистрация шрифта с кириллицей."""

from __future__ import annotations

import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import getFont
from reportlab.pdfbase.ttfonts import TTFont


FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


_CANDIDATES = [
    ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("DejaVuSans", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("DejaVuSans", "/Library/Fonts/DejaVuSans.ttf",
     "/Library/Fonts/DejaVuSans-Bold.ttf"),
    ("Arial", "/Library/Fonts/Arial Unicode.ttf",
     "/Library/Fonts/Arial Unicode.ttf"),
    ("DejaVuSans", "C:/Windows/Fonts/DejaVuSans.ttf",
     "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
    ("Arial", "C:/Windows/Fonts/arial.ttf",
     "C:/Windows/Fonts/arialbd.ttf"),
]


def register_cyrillic_font() -> tuple[str, str]:
    """
    Регистрирует TTF-шрифт с кириллицей.
    Возвращает (font, font_bold).
    """
    for name, reg, bold in _CANDIDATES:
        if not os.path.exists(reg):
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, reg))
            if os.path.exists(bold):
                pdfmetrics.registerFont(TTFont(name + "-Bold", bold))
                pdfmetrics.registerFontFamily(
                    name, normal=name, bold=name + "-Bold",
                    italic=name, boldItalic=name + "-Bold",
                )
            else:
                pdfmetrics.registerFontFamily(
                    name, normal=name, bold=name,
                    italic=name, boldItalic=name,
                )
            return name, name + "-Bold"
        except Exception as e:
            print(f"Не удалось зарегистрировать {reg}: {e}")

    print("ВНИМАНИЕ: не найден TTF-шрифт с кириллицей, "
          "используется Helvetica.")
    return "Helvetica", "Helvetica-Bold"


def resolve_bold(font_name: str) -> str:
    """Возвращает имя bold-варианта, если он зарегистрирован."""
    try:
        getFont(font_name + "-Bold")
        return font_name + "-Bold"
    except Exception:
        return font_name
"""Объединение одинаковых подряд идущих ячеек в строке (SPAN)."""

from __future__ import annotations


def cell_key(cell) -> str | None:
    """
    Нормализованный ключ для сравнения или None, если объединять нельзя.

    Значения в rows_keys:
      None                 — пусто;
      (lines, multi_class) — содержимое + признак «classes > 1».
    Объединяем только ячейки с multi_class=True.
    """
    if cell is None:
        return None
    if isinstance(cell, tuple) and len(cell) == 2:
        lines, multi_class = cell
        if not multi_class:
            return None
        joined = "|".join(x for x in lines if x)
        return joined or None
    return None


def merge_equal_cells_keys(rows_keys: list[list], header_rows: int,
                           col_offset: int = 1) -> list:
    cmds: list = []
    for ri in range(header_rows, len(rows_keys)):
        row = rows_keys[ri]
        j = col_offset
        n = len(row)
        while j < n:
            val = cell_key(row[j])
            if val is None:
                j += 1
                continue
            k = j + 1
            while k < n and cell_key(row[k]) == val:
                k += 1
            if k - j > 1:
                cmds.append(("SPAN", (j, ri), (k - 1, ri)))
            j = k
    return cmds
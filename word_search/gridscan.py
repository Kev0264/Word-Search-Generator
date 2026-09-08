from __future__ import annotations

import re


def lines(rows: int, cols: int, min_length: int = 2) -> list[list[tuple[int, int]]]:
    """Every maximal straight line across a grid, one per axis family (rows,
    columns, and both diagonal directions). Checking a line and its reverse
    covers all 8 word-search directions along that axis."""
    out: list[list[tuple[int, int]]] = []
    for r in range(rows):
        out.append([(r, c) for c in range(cols)])
    for c in range(cols):
        out.append([(r, c) for r in range(rows)])
    for d in range(-(rows - 1), cols):
        cells = [(r, r + d) for r in range(rows) if 0 <= r + d < cols]
        if len(cells) >= min_length:
            out.append(cells)
    for d in range(rows + cols - 1):
        cells = [(r, d - r) for r in range(rows) if 0 <= d - r < cols]
        if len(cells) >= min_length:
            out.append(cells)
    return out


def find_matches(
    grid: list[list[str]], pattern: re.Pattern[str], min_length: int = 2
) -> list[tuple[str, list[tuple[int, int]]]]:
    """Scans the whole grid (every direction, forwards and backwards) for
    matches of the given compiled pattern, returning (text, cells) for each
    occurrence found."""
    rows = len(grid)
    cols = len(grid[0]) if grid else 0
    matches: list[tuple[str, list[tuple[int, int]]]] = []
    for cells in lines(rows, cols, min_length):
        text = "".join(grid[r][c] for r, c in cells)
        for line_cells, line_text in ((cells, text), (cells[::-1], text[::-1])):
            for m in pattern.finditer(line_text):
                matches.append((m.group(), line_cells[m.start() : m.end()]))
    return matches

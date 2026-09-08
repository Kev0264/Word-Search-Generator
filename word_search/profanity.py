from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

# Words shorter than this turn up by pure chance in almost any grid of
# random letters (2-3 letter fragments like "HE", "MF", "XX" are in the
# bundled list), so checking them would flag nearly every puzzle for no
# meaningful reason. Everything the check actually cares about -- real
# curse words and slurs -- is 4+ letters.
MIN_BLOCKED_WORD_LENGTH = 4


@lru_cache(maxsize=1)
def load_blocklist() -> frozenset[str]:
    """Loads the word list bundled with the `better-profanity` package,
    cleaned down to single-token, letters-only, uppercase entries of at
    least MIN_BLOCKED_WORD_LENGTH characters. Multi-word phrases are
    dropped entirely since they can't appear in a continuous letter grid."""
    import better_profanity

    wordlist_path = Path(better_profanity.__file__).parent / "profanity_wordlist.txt"
    words: set[str] = set()
    for line in wordlist_path.read_text(encoding="utf-8").splitlines():
        if " " in line.strip():
            continue
        cleaned = re.sub(r"[^A-Za-z]", "", line).upper()
        if len(cleaned) >= MIN_BLOCKED_WORD_LENGTH:
            words.add(cleaned)
    return frozenset(words)


def _lines(rows: int, cols: int) -> list[list[tuple[int, int]]]:
    """Every maximal straight line across the grid, one per axis family
    (rows, columns, and both diagonal directions). Checking a line and its
    reverse covers all 8 word-search directions along that axis."""
    lines: list[list[tuple[int, int]]] = []
    for r in range(rows):
        lines.append([(r, c) for c in range(cols)])
    for c in range(cols):
        lines.append([(r, c) for r in range(rows)])
    for d in range(-(rows - 1), cols):
        cells = [(r, r + d) for r in range(rows) if 0 <= r + d < cols]
        if len(cells) >= MIN_BLOCKED_WORD_LENGTH:
            lines.append(cells)
    for d in range(rows + cols - 1):
        cells = [(r, d - r) for r in range(rows) if 0 <= d - r < cols]
        if len(cells) >= MIN_BLOCKED_WORD_LENGTH:
            lines.append(cells)
    return lines


@lru_cache(maxsize=1)
def _compiled_pattern() -> re.Pattern[str]:
    # Longest-first so alternation prefers the longest match at a position.
    words = sorted(load_blocklist(), key=len, reverse=True)
    return re.compile("|".join(re.escape(w) for w in words))


def find_blocked_words(grid: list[list[str]]) -> list[tuple[str, list[tuple[int, int]]]]:
    """Scans the whole grid (every direction, forwards and backwards) for
    any blocklist word, returning (word, cells) for each occurrence found."""
    rows, cols = len(grid), len(grid[0]) if grid else 0
    pattern = _compiled_pattern()
    matches: list[tuple[str, list[tuple[int, int]]]] = []
    for cells in _lines(rows, cols):
        text = "".join(grid[r][c] for r, c in cells)
        for line_cells, line_text in ((cells, text), (cells[::-1], text[::-1])):
            for m in pattern.finditer(line_text):
                matches.append((m.group(), line_cells[m.start() : m.end()]))
    return matches

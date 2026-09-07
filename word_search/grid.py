from __future__ import annotations

import random
import string
from dataclasses import dataclass, field

DIRECTIONS: dict[str, tuple[int, int]] = {
    "E": (0, 1),
    "W": (0, -1),
    "S": (1, 0),
    "N": (-1, 0),
    "SE": (1, 1),
    "SW": (1, -1),
    "NE": (-1, 1),
    "NW": (-1, -1),
}


class WordSearchGenerationError(Exception):
    """Raised when a puzzle cannot be generated with the given settings."""


@dataclass
class PlacedWord:
    word: str
    row: int
    col: int
    direction: str
    cells: list[tuple[int, int]] = field(default_factory=list)


class WordSearchGenerator:
    """Builds a word search grid and tracks where each word ended up."""

    def __init__(
        self,
        words: list[str],
        rows: int = 15,
        cols: int = 15,
        allow_backwards: bool = True,
        directions: list[str] | None = None,
        seed: int | None = None,
        max_attempts_per_word: int = 500,
        fill_letters: str = string.ascii_uppercase,
    ):
        self.words = self._normalize_words(words)
        self.rows = rows
        self.cols = cols
        self.allow_backwards = allow_backwards
        self.directions = directions or list(DIRECTIONS.keys())
        self.max_attempts_per_word = max_attempts_per_word
        self.fill_letters = fill_letters

        self._rng = random.Random(seed)
        self.grid: list[list[str]] = [["" for _ in range(cols)] for _ in range(rows)]
        self.placements: list[PlacedWord] = []
        self.skipped: list[str] = []

    @staticmethod
    def _normalize_words(words: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for word in words:
            cleaned = "".join(ch for ch in word.strip().upper() if ch.isalpha())
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)
        return normalized

    def generate(self) -> list[list[str]]:
        if not self.words:
            raise WordSearchGenerationError("No valid words were provided.")

        longest = max(len(word) for word in self.words)
        if longest > max(self.rows, self.cols):
            raise WordSearchGenerationError(
                f"Grid too small for longest word ({longest} letters); increase the grid size."
            )

        for word in sorted(self.words, key=len, reverse=True):
            if not self._place_word(word):
                self.skipped.append(word)

        self._fill_blanks()
        return self.grid

    def _place_word(self, word: str) -> bool:
        for _ in range(self.max_attempts_per_word):
            direction_name = self._rng.choice(self.directions)
            dr, dc = DIRECTIONS[direction_name]

            letters = word
            if self.allow_backwards and self._rng.random() < 0.5:
                letters = word[::-1]

            length = len(letters)
            row = self._rng.randrange(0, self.rows)
            col = self._rng.randrange(0, self.cols)
            end_row = row + dr * (length - 1)
            end_col = col + dc * (length - 1)
            if not (0 <= end_row < self.rows and 0 <= end_col < self.cols):
                continue

            cells = [(row + dr * i, col + dc * i) for i in range(length)]
            if self._fits(cells, letters):
                for (r, c), ch in zip(cells, letters):
                    self.grid[r][c] = ch
                self.placements.append(PlacedWord(word, row, col, direction_name, cells))
                return True
        return False

    def _fits(self, cells: list[tuple[int, int]], letters: str) -> bool:
        for (r, c), ch in zip(cells, letters):
            existing = self.grid[r][c]
            if existing and existing != ch:
                return False
        return True

    def _fill_blanks(self) -> None:
        for r in range(self.rows):
            for c in range(self.cols):
                if not self.grid[r][c]:
                    self.grid[r][c] = self._rng.choice(self.fill_letters)

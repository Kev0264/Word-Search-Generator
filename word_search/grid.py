from __future__ import annotations

import random
import string
from dataclasses import dataclass, field

from .profanity import find_blocked_words

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
    display: str = ""


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
        check_profanity: bool = True,
        max_profanity_retries: int = 30,
    ):
        self.words, self.display_words = self._normalize_words(words)
        self.rows = rows
        self.cols = cols
        self.allow_backwards = allow_backwards
        self.directions = directions or list(DIRECTIONS.keys())
        self.max_attempts_per_word = max_attempts_per_word
        self.fill_letters = fill_letters
        self.check_profanity = check_profanity
        self.max_profanity_retries = max_profanity_retries

        self._rng = random.Random(seed)
        self.grid: list[list[str]] = [["" for _ in range(cols)] for _ in range(rows)]
        self.placements: list[PlacedWord] = []
        self.skipped: list[str] = []
        self.blocked_words_found: list[str] = []

    @staticmethod
    def _normalize_words(words: list[str]) -> tuple[list[str], dict[str, str]]:
        """Cleans each word down to the letters-only form placed in the grid,
        while remembering the original (uppercased) spelling for display in
        the word list, so a word like "mother-in-law" is hidden in the grid
        as MOTHERINLAW but still printed as MOTHER-IN-LAW to solvers."""
        normalized: list[str] = []
        display_words: dict[str, str] = {}
        for word in words:
            display = word.strip().upper()
            cleaned = "".join(ch for ch in display if ch.isalpha())
            if cleaned and cleaned not in display_words:
                normalized.append(cleaned)
                display_words[cleaned] = display
        return normalized, display_words

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
                self.skipped.append(self.display_words[word])

        self._fill_blanks()
        if self.check_profanity:
            self._avoid_blocked_words()
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
                self.placements.append(
                    PlacedWord(word, row, col, direction_name, cells, self.display_words[word])
                )
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

    def _avoid_blocked_words(self) -> None:
        """Rerolls the random filler letters (leaving placed words alone)
        whenever the grid happens to spell out a blocked word by chance, in
        any of the 8 directions.

        A match entirely contained within a single placed word's own cells
        is ignored outright, not just left unfixed -- e.g. "ORAL" inside
        "CORAL" or "PECKER" inside "WOODPECKER" isn't an accidental word
        appearing in the puzzle, it's just a substring of a word the author
        deliberately chose, forwards or in that word's own reversed
        spelling. The actual risk this guards against is a blocked word
        assembled from filler letters (whether entirely filler, or a
        coincidence spanning two different placed words at a crossing) --
        those are rerolled if possible, and reported if not."""
        cell_to_placements: dict[tuple[int, int], set[int]] = {}
        for idx, placed in enumerate(self.placements):
            for cell in placed.cells:
                cell_to_placements.setdefault(cell, set()).add(idx)

        filler_cells = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if (r, c) not in cell_to_placements
        ]

        def real_matches(matches):
            found = []
            for word, cells in matches:
                involved: set[int] = set()
                involves_filler = False
                for cell in cells:
                    placements_here = cell_to_placements.get(cell)
                    if not placements_here:
                        involves_filler = True
                    else:
                        involved |= placements_here
                if involves_filler or len(involved) > 1:
                    found.append((word, cells, involves_filler))
            return found

        for _ in range(self.max_profanity_retries):
            matches = real_matches(find_blocked_words(self.grid))
            if not matches:
                self.blocked_words_found = []
                return
            if not any(involves_filler for _, _, involves_filler in matches):
                # No remaining match involves a filler cell (it's purely
                # placed words crossing paths); further rerolls can't help.
                break
            for r, c in filler_cells:
                self.grid[r][c] = self._rng.choice(self.fill_letters)
        else:
            matches = real_matches(find_blocked_words(self.grid))

        self.blocked_words_found = sorted({word for word, _, _ in matches})

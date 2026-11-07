from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass, field

from .gridscan import find_matches
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
        check_duplicate_words: bool = True,
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
        self.check_duplicate_words = check_duplicate_words
        self.max_profanity_retries = max_profanity_retries

        self._rng = random.Random(seed)
        self.grid: list[list[str]] = [["" for _ in range(cols)] for _ in range(rows)]
        self.placements: list[PlacedWord] = []
        self.skipped: list[str] = []
        self.blocked_words_found: list[str] = []
        self.duplicate_words_found: list[str] = []
        self._cell_to_placements_cache: dict[tuple[int, int], set[int]] | None = None

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

        # Each check rerolls filler letters independently; run a couple of
        # rounds so the rare case of one check's reroll reintroducing an
        # issue the other check had just fixed still gets caught.
        for _ in range(3):
            if self.check_profanity:
                self._avoid_blocked_words()
            if self.check_duplicate_words:
                self._avoid_duplicate_words()
            if not self.blocked_words_found and not self.duplicate_words_found:
                break

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

    def _cell_to_placements(self) -> dict[tuple[int, int], set[int]]:
        if self._cell_to_placements_cache is None:
            mapping: dict[tuple[int, int], set[int]] = {}
            for idx, placed in enumerate(self.placements):
                for cell in placed.cells:
                    mapping.setdefault(cell, set()).add(idx)
            self._cell_to_placements_cache = mapping
        return self._cell_to_placements_cache

    def _classify_matches(
        self, matches: list[tuple[str, list[tuple[int, int]]]]
    ) -> list[tuple[str, list[tuple[int, int]], bool]]:
        """Keeps only matches that are a genuine coincidence -- involving at
        least one random filler cell, or spanning two *different* placed
        words crossing paths -- and drops any match fully explained by a
        single placed word's own letters (substring or exact, forwards or
        in that word's own reversed spelling), since that's simply how a
        deliberately chosen word is spelled, not an accidental occurrence."""
        cell_to_placements = self._cell_to_placements()
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

    def _reroll_until_clean(self, find_raw_matches) -> list[str]:
        """Rerolls filler letters (leaving placed words alone) until
        find_raw_matches() -- a callable scanning self.grid -- turns up no
        more genuine coincidences, or retries run out. Returns the sorted
        list of words that couldn't be avoided."""
        filler_cells = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if (r, c) not in self._cell_to_placements()
        ]

        for _ in range(self.max_profanity_retries):
            matches = self._classify_matches(find_raw_matches())
            if not matches:
                return []
            if not any(involves_filler for _, _, involves_filler in matches):
                # No remaining match involves a filler cell (it's purely
                # placed words crossing paths); further rerolls can't help.
                break
            for r, c in filler_cells:
                self.grid[r][c] = self._rng.choice(self.fill_letters)
        else:
            matches = self._classify_matches(find_raw_matches())

        return sorted({word for word, _, _ in matches})

    def _avoid_blocked_words(self) -> None:
        """Guards against the grid spelling out a profanity-blocklist word
        by chance. See _classify_matches for what counts as a genuine
        coincidence versus just a substring of a word you chose yourself."""
        self.blocked_words_found = self._reroll_until_clean(lambda: find_blocked_words(self.grid))

    def _avoid_duplicate_words(self) -> None:
        """Guards against one of your own placed words accidentally
        appearing a *second* time elsewhere in the grid by chance -- a
        solver could circle the wrong instance, which the answer key
        wouldn't match. A word that's simply a substring of another word
        you placed (e.g. CAT inside CATERPILLAR) is not flagged, for the
        same reason a blocklist substring inside a legitimate word isn't:
        it's not a coincidence, it's just how that other word is spelled."""
        if not self.placements:
            self.duplicate_words_found = []
            return

        unique_words = sorted({p.word for p in self.placements}, key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(w) for w in unique_words))
        min_length = min(len(w) for w in unique_words)

        expected_occurrences = set()
        for placed in self.placements:
            expected_occurrences.add(tuple(placed.cells))
            expected_occurrences.add(tuple(reversed(placed.cells)))

        def find_extra_occurrences():
            matches = find_matches(self.grid, pattern, min_length)
            return [(w, cells) for w, cells in matches if tuple(cells) not in expected_occurrences]

        self.duplicate_words_found = self._reroll_until_clean(find_extra_occurrences)

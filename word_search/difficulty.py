from __future__ import annotations

# Grid size, allowed directions, and a recommended word-count range for each
# difficulty preset, based on common conventions in published word search
# books.
DIFFICULTY_PRESETS: dict[str, dict] = {
    "easy": {
        "size": "12",
        "straight_only": True,
        "allow_backwards": False,
        "word_count": (8, 12),
    },
    "medium": {
        "size": "15",
        "straight_only": False,
        "allow_backwards": True,
        "word_count": (12, 18),
    },
    "hard": {
        "size": "20",
        "straight_only": False,
        "allow_backwards": True,
        "word_count": (20, 28),
    },
}


def word_count_warning(difficulty: str | None, count: int) -> str | None:
    if difficulty is None:
        return None
    lo, hi = DIFFICULTY_PRESETS[difficulty]["word_count"]
    if count < lo:
        return (
            f"{count} word(s) is light for '{difficulty}' difficulty "
            f"(recommended {lo}-{hi}); the puzzle may look sparse."
        )
    if count > hi:
        return (
            f"{count} word(s) is a lot for '{difficulty}' difficulty "
            f"(recommended {lo}-{hi}); consider a bigger --size or a higher --difficulty."
        )
    return None

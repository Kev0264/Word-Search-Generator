from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .gridscan import find_matches

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


@lru_cache(maxsize=1)
def _compiled_pattern() -> re.Pattern[str]:
    # Longest-first so alternation prefers the longest match at a position.
    words = sorted(load_blocklist(), key=len, reverse=True)
    return re.compile("|".join(re.escape(w) for w in words))


def find_blocked_words(grid: list[list[str]]) -> list[tuple[str, list[tuple[int, int]]]]:
    """Scans the whole grid (every direction, forwards and backwards) for
    any blocklist word, returning (word, cells) for each occurrence found."""
    return find_matches(grid, _compiled_pattern(), MIN_BLOCKED_WORD_LENGTH)

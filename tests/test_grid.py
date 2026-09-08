import pytest

from word_search.grid import DIRECTIONS, WordSearchGenerationError, WordSearchGenerator


def test_normalizes_and_dedupes_words():
    gen = WordSearchGenerator(["python ", "Python", "grid!", ""], rows=10, cols=10, seed=1)
    assert gen.words == ["PYTHON", "GRID"]


def test_display_words_preserve_original_spelling():
    gen = WordSearchGenerator(
        ["mother-in-law", "O'Brien", "new york", "python3"], rows=15, cols=15, seed=1
    )
    assert gen.words == ["MOTHERINLAW", "OBRIEN", "NEWYORK", "PYTHON"]
    assert gen.display_words == {
        "MOTHERINLAW": "MOTHER-IN-LAW",
        "OBRIEN": "O'BRIEN",
        "NEWYORK": "NEW YORK",
        "PYTHON": "PYTHON3",
    }
    gen.generate()
    for placed in gen.placements:
        assert placed.display == gen.display_words[placed.word]


def test_all_words_appear_in_grid_reading_in_their_direction():
    words = ["PYTHON", "GRID", "SEARCH", "WORD"]
    gen = WordSearchGenerator(words, rows=15, cols=15, seed=42)
    gen.generate()

    assert not gen.skipped
    for placed in gen.placements:
        dr, dc = DIRECTIONS[placed.direction]
        letters = placed.word if not _is_reversed(gen, placed) else placed.word[::-1]
        for (r, c), _ in zip(placed.cells, letters):
            assert 0 <= r < gen.rows
            assert 0 <= c < gen.cols
        read = "".join(gen.grid[r][c] for r, c in placed.cells)
        assert read in (placed.word, placed.word[::-1])


def _is_reversed(gen, placed):
    read = "".join(gen.grid[r][c] for r, c in placed.cells)
    return read == placed.word[::-1]


def test_grid_is_fully_filled_with_letters():
    gen = WordSearchGenerator(["CAT", "DOG"], rows=8, cols=8, seed=7)
    gen.generate()
    for row in gen.grid:
        for cell in row:
            assert cell.isalpha()


def test_reproducible_with_same_seed():
    words = ["ALPHA", "BETA", "GAMMA", "DELTA"]
    gen1 = WordSearchGenerator(words, rows=12, cols=12, seed=99)
    gen2 = WordSearchGenerator(words, rows=12, cols=12, seed=99)
    assert gen1.generate() == gen2.generate()


def test_word_too_long_for_grid_raises():
    gen = WordSearchGenerator(["SUPERCALIFRAGILISTIC"], rows=5, cols=5, seed=1)
    with pytest.raises(WordSearchGenerationError):
        gen.generate()


def test_no_words_raises():
    gen = WordSearchGenerator([""], rows=5, cols=5, seed=1)
    with pytest.raises(WordSearchGenerationError):
        gen.generate()


def test_straight_only_directions_are_respected():
    gen = WordSearchGenerator(
        ["PYTHON", "GRID"], rows=15, cols=15, seed=3, directions=["N", "S", "E", "W"]
    )
    gen.generate()
    for placed in gen.placements:
        assert placed.direction in ("N", "S", "E", "W")


def test_avoid_blocked_words_rerolls_filler_until_clean():
    from word_search.profanity import find_blocked_words, load_blocklist

    word = min(load_blocklist(), key=len)
    gen = WordSearchGenerator(["PLACEHOLDER"], rows=1, cols=len(word) + 10, seed=7)
    gen.placements = []
    gen.grid = [list(word + "Q" * (gen.cols - len(word)))]
    assert find_blocked_words(gen.grid)  # sanity check: dirty before the reroll

    gen._avoid_blocked_words()

    assert find_blocked_words(gen.grid) == []
    assert gen.blocked_words_found == []


def test_avoid_blocked_words_ignores_an_exact_intentional_placement():
    """If the author's own chosen word happens to match a blocklist entry
    outright (e.g. an innocuous word an overzealous list still flags), that's
    their deliberate choice, not an accidental letter combination -- it
    should be left alone and not reported."""
    from word_search.grid import PlacedWord
    from word_search.profanity import load_blocklist

    word = min(load_blocklist(), key=len)
    gen = WordSearchGenerator(["PLACEHOLDER"], rows=1, cols=len(word), seed=3)
    gen.grid = [list(word)]
    gen.placements = [PlacedWord(word, 0, 0, "E", [(0, i) for i in range(len(word))], word)]

    gen._avoid_blocked_words()

    assert "".join(gen.grid[0]) == word
    assert gen.blocked_words_found == []


def test_avoid_blocked_words_ignores_a_substring_of_an_intentional_placement():
    """A blocklist word that's simply a substring of a longer word the
    author typed (e.g. "ORAL" inside "CORAL") isn't an accidental word
    appearing in the puzzle -- it's just how that legitimate word is
    spelled, and shouldn't be flagged or rerolled."""
    from word_search.grid import PlacedWord
    from word_search.profanity import load_blocklist

    word = min(load_blocklist(), key=len)
    framed = "Q" + word + "Q"
    gen = WordSearchGenerator(["PLACEHOLDER"], rows=1, cols=len(framed), seed=3)
    gen.grid = [list(framed)]
    gen.placements = [PlacedWord(framed, 0, 0, "E", [(0, i) for i in range(len(framed))], framed)]

    gen._avoid_blocked_words()

    assert "".join(gen.grid[0]) == framed
    assert gen.blocked_words_found == []


def test_avoid_blocked_words_reports_a_match_spanning_two_crossing_placements():
    """A blocked word assembled from two different placed words crossing
    paths (no filler cell involved) is a genuine coincidence a solver could
    actually read -- rerolling filler can't fix it, but it should still be
    reported rather than silently ignored like a same-word substring is."""
    from word_search.grid import PlacedWord
    from word_search.profanity import load_blocklist

    word = min(load_blocklist(), key=len)
    split = len(word) // 2
    first, second = word[:split], word[split:]
    assert first and second  # sanity: both halves non-empty

    gen = WordSearchGenerator(["PLACEHOLDER"], rows=1, cols=len(word), seed=3)
    gen.grid = [list(word)]
    gen.placements = [
        PlacedWord(first, 0, 0, "E", [(0, i) for i in range(len(first))], first),
        PlacedWord(
            second,
            0,
            len(first),
            "E",
            [(0, len(first) + i) for i in range(len(second))],
            second,
        ),
    ]

    gen._avoid_blocked_words()

    assert "".join(gen.grid[0]) == word  # still can't be fixed by rerolling filler
    assert word in gen.blocked_words_found


def test_check_profanity_false_skips_the_check():
    gen = WordSearchGenerator(["CAT", "DOG"], rows=8, cols=8, seed=1, check_profanity=False)
    gen.generate()
    assert gen.blocked_words_found == []


def test_avoid_duplicate_words_rerolls_an_accidental_extra_occurrence():
    from word_search.grid import PlacedWord

    gen = WordSearchGenerator(["CAT"], rows=1, cols=10, seed=1)
    gen.placements = [PlacedWord("CAT", 0, 0, "E", [(0, 0), (0, 1), (0, 2)], "CAT")]
    gen.grid = [list("CATQCATQQQ")]  # a second, accidental "CAT" at cols 4-6

    gen._avoid_duplicate_words()

    assert gen.duplicate_words_found == []


def test_avoid_duplicate_words_ignores_a_substring_of_another_placed_word():
    """CAT showing up inside CATERPILLAR's own letters isn't a coincidence,
    it's just how CATERPILLAR is spelled -- shouldn't be flagged or touched."""
    from word_search.grid import PlacedWord

    gen = WordSearchGenerator(["CAT", "CATERPILLAR"], rows=2, cols=11, seed=1)
    gen.grid = [list("CATERPILLAR"), list("CAT" + "Q" * 8)]
    gen.placements = [
        PlacedWord(
            "CATERPILLAR", 0, 0, "E", [(0, i) for i in range(11)], "CATERPILLAR"
        ),
        PlacedWord("CAT", 1, 0, "E", [(1, 0), (1, 1), (1, 2)], "CAT"),
    ]

    gen._avoid_duplicate_words()

    assert "".join(gen.grid[0]) == "CATERPILLAR"
    assert gen.duplicate_words_found == []


def test_avoid_duplicate_words_reports_a_match_spanning_two_crossing_placements():
    from word_search.grid import PlacedWord

    gen = WordSearchGenerator(["ABCD", "AB", "CD"], rows=2, cols=4, seed=1)
    gen.grid = [list("ABCD"), list("ABCD")]
    gen.placements = [
        PlacedWord("ABCD", 1, 0, "E", [(1, 0), (1, 1), (1, 2), (1, 3)], "ABCD"),
        PlacedWord("AB", 0, 0, "E", [(0, 0), (0, 1)], "AB"),
        PlacedWord("CD", 0, 2, "E", [(0, 2), (0, 3)], "CD"),
    ]

    gen._avoid_duplicate_words()

    assert "".join(gen.grid[0]) == "ABCD"  # unfixable: no filler cell involved
    assert "ABCD" in gen.duplicate_words_found


def test_check_duplicate_words_false_skips_the_check():
    gen = WordSearchGenerator(
        ["CAT", "DOG"], rows=8, cols=8, seed=1, check_duplicate_words=False
    )
    gen.generate()
    assert gen.duplicate_words_found == []

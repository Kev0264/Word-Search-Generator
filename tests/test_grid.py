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

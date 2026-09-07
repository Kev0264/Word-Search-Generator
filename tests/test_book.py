from word_search.book import (
    PAGE_H,
    PAGE_W,
    _markdown_blocks,
    build_book,
    read_puzzle_csv,
)


def test_read_puzzle_csv_parses_title_and_words(tmp_path):
    csv_path = tmp_path / "puzzles.csv"
    csv_path.write_text("Title,Trivia,Words\nAnimals,,TIGER,LION,BEAR\nSpace,,MOON,STAR\n")

    specs = read_puzzle_csv(csv_path)

    assert [s.title for s in specs] == ["Animals", "Space"]
    assert specs[0].words == ["TIGER", "LION", "BEAR"]
    assert specs[1].words == ["MOON", "STAR"]


def test_read_puzzle_csv_skips_the_header_row(tmp_path):
    csv_path = tmp_path / "puzzles.csv"
    # A header row shaped like a data row shouldn't be mistaken for a puzzle.
    csv_path.write_text("Title,Trivia,Words\nAnimals,,CAT,DOG\n")

    specs = read_puzzle_csv(csv_path)

    assert len(specs) == 1
    assert specs[0].title == "Animals"


def test_read_puzzle_csv_auto_titles_blank_first_column(tmp_path):
    csv_path = tmp_path / "puzzles.csv"
    csv_path.write_text("Title,Trivia,Words\n,,CAT,DOG\n,,RED,BLUE\n")

    specs = read_puzzle_csv(csv_path)

    assert [s.title for s in specs] == ["Puzzle 1", "Puzzle 2"]


def test_read_puzzle_csv_skips_blank_rows_and_rows_without_words(tmp_path):
    csv_path = tmp_path / "puzzles.csv"
    csv_path.write_text("Title,Trivia,Words\nAnimals,,CAT,DOG\n\nEmpty\n,,\nSpace,,MOON\n")

    specs = read_puzzle_csv(csv_path)

    assert [s.title for s in specs] == ["Animals", "Space"]


def test_read_puzzle_csv_words_start_at_the_same_column_with_or_without_trivia(tmp_path):
    """The whole point of a dedicated trivia column: word columns line up
    the same way whether or not a given puzzle has a trivia blurb."""
    csv_path = tmp_path / "puzzles.csv"
    csv_path.write_text(
        'Title,Trivia,Words\n'
        'Animals,"Elephants have over 40,000 muscles in their trunk.",TIGER,LION\n'
        "Space,,MOON,STAR\n"
    )

    specs = read_puzzle_csv(csv_path)

    assert specs[0].trivia == "Elephants have over 40,000 muscles in their trunk."
    assert specs[0].words == ["TIGER", "LION"]
    assert specs[1].trivia is None
    assert specs[1].words == ["MOON", "STAR"]


def test_read_puzzle_csv_trivia_cell_supports_multiple_paragraphs(tmp_path):
    csv_path = tmp_path / "puzzles.csv"
    csv_path.write_text('Title,Trivia,Words\nAnimals,"Fact one.\n\nFact two.",TIGER,LION\n')

    specs = read_puzzle_csv(csv_path)

    assert specs[0].trivia == "Fact one.\n\nFact two."
    assert specs[0].words == ["TIGER", "LION"]


def test_markdown_bullet_continuation_line_stays_in_the_bullet():
    text = "- Check your work using the answer key\n  at the back of the book\n\nDone."
    blocks = _markdown_blocks(text)

    assert blocks[0] == ("bullet", "Check your work using the answer key at the back of the book")
    assert blocks[1] == ("para", "Done.")


def test_markdown_paragraph_continuation_line_joins_paragraph():
    text = "This is a long\nsentence split\nacross lines.\n\nNext paragraph."
    blocks = _markdown_blocks(text)

    assert blocks[0] == ("para", "This is a long sentence split across lines.")
    assert blocks[1] == ("para", "Next paragraph.")


def test_markdown_headings_and_bullets_parsed_separately():
    text = "# Title\n\n## Subtitle\n\n- one\n- two\n"
    blocks = _markdown_blocks(text)

    assert blocks == [
        ("h1", "Title"),
        ("h2", "Subtitle"),
        ("bullet", "one"),
        ("bullet", "two"),
    ]


def _sample_specs():
    from word_search.book import PuzzleSpec

    return [
        PuzzleSpec(title="Animals", words=["CAT", "DOG", "BIRD"]),
        PuzzleSpec(title="Colors", words=["RED", "BLUE", "GREEN"]),
    ]


def test_build_book_produces_correctly_sized_pages():
    pages, warnings = build_book(
        _sample_specs(),
        rows=10,
        cols=10,
        allow_backwards=True,
        directions=None,
        seed=1,
        book_title="Test Book",
    )

    assert len(pages) >= 1
    for page in pages:
        assert page.size == (PAGE_W, PAGE_H)


def test_build_book_pads_to_even_page_count():
    pages, _ = build_book(
        _sample_specs(),
        rows=10,
        cols=10,
        allow_backwards=True,
        directions=None,
        seed=1,
        book_title="Test Book",
    )

    assert len(pages) % 2 == 0


def test_build_book_warns_below_kdp_minimum_page_count():
    pages, warnings = build_book(
        _sample_specs(),
        rows=10,
        cols=10,
        allow_backwards=True,
        directions=None,
        seed=1,
        book_title="Test Book",
    )

    assert len(pages) < 24
    assert any("24" in w for w in warnings)


def test_build_book_skips_puzzle_too_long_for_grid_with_warning():
    from word_search.book import PuzzleSpec

    specs = [
        PuzzleSpec(title="TooLong", words=["SUPERCALIFRAGILISTIC"]),
        PuzzleSpec(title="Fine", words=["CAT", "DOG"]),
    ]
    pages, warnings = build_book(
        specs,
        rows=5,
        cols=5,
        allow_backwards=True,
        directions=None,
        seed=1,
        book_title="Test Book",
    )

    assert any("TooLong" in w for w in warnings)
    # Only the "Fine" puzzle should have produced a puzzle page (plus title
    # page, divider, answer key page, and any recto/even-page-count padding).
    assert len(pages) <= 8


def test_force_recto_inserts_blank_page_only_when_even():
    from word_search.book import _force_recto

    pages: list = []
    # Odd page number: nothing inserted, number unchanged.
    assert _force_recto(pages, 3) == 3
    assert pages == []

    # Even page number: one blank page inserted, number advances to odd.
    assert _force_recto(pages, 4) == 5
    assert len(pages) == 1


def test_toc_reservation_and_recto_forcing_produce_correct_total_pages():
    """The table of contents is backfilled after puzzle pages are laid out
    (reserved upfront, filled in once real page numbers are known). This
    re-derives the expected total page count from the same building blocks
    build_book uses internally, to catch the reservation/backfill drifting
    out of sync with the real per-puzzle page numbers."""
    import math as _math

    from word_search.book import PuzzleSpec, _force_recto, _toc_rows_per_page

    specs = [PuzzleSpec(title=f"Theme {i}", words=["CAT", "DOG", "BIRD"]) for i in range(1, 6)]
    pages, _ = build_book(
        specs,
        rows=10,
        cols=10,
        allow_backwards=True,
        directions=None,
        seed=1,
        book_title="Test Book",
    )

    page_number = 2  # after the title page
    page_number += _math.ceil(len(specs) / _toc_rows_per_page())  # TOC pages
    for _ in specs:
        page_number = _force_recto([], page_number)
        page_number += 1  # the puzzle page itself
    page_number = _force_recto([], page_number)  # the "Answer Keys" divider
    page_number += 1
    page_number += _math.ceil(len(specs) / 4)  # 4-up answer key pages

    expected_total = page_number - 1
    if expected_total % 2 == 1:
        expected_total += 1

    assert len(pages) == expected_total


def test_render_toc_pages_produces_exact_requested_page_count():
    from word_search.book import PuzzleSpec, WordSearchGenerator, render_toc_pages

    generator = WordSearchGenerator(["CAT", "DOG"], rows=10, cols=10, seed=1)
    generator.generate()
    entries = [(i, f"Theme {i}", 10 + i) for i in range(1, 4)]

    pages = render_toc_pages(entries, start_page_number=4, page_count=2)

    assert len(pages) == 2
    for page in pages:
        assert page.size == (PAGE_W, PAGE_H)


def test_large_print_preset_uses_small_grid_and_scaled_text():
    from word_search.book import text_scale_for
    from word_search.difficulty import DIFFICULTY_PRESETS

    preset = DIFFICULTY_PRESETS["large-print"]
    assert int(preset["size"]) <= 12
    assert preset["straight_only"] is True
    assert preset["allow_backwards"] is False
    assert text_scale_for("large-print") > 1.0
    assert text_scale_for("medium") == 1.0
    assert text_scale_for(None) == 1.0


def test_build_book_includes_intro_and_instructions_pages():
    pages_without, _ = build_book(
        _sample_specs(),
        rows=10,
        cols=10,
        allow_backwards=True,
        directions=None,
        seed=1,
        book_title="Test Book",
    )
    pages_with, _ = build_book(
        _sample_specs(),
        rows=10,
        cols=10,
        allow_backwards=True,
        directions=None,
        seed=1,
        book_title="Test Book",
        intro_text="# Welcome\n\nHello there.",
        instructions_text="# Rules\n\nFind the words.",
    )

    assert len(pages_with) > len(pages_without)

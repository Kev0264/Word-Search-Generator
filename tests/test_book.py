from word_search.book import (
    PAGE_H,
    PAGE_W,
    _markdown_blocks,
    build_book,
    read_puzzle_csv,
)


def test_read_puzzle_csv_parses_title_and_words(tmp_path):
    csv_path = tmp_path / "puzzles.csv"
    csv_path.write_text("Animals,TIGER,LION,BEAR\nSpace,MOON,STAR\n")

    specs = read_puzzle_csv(csv_path)

    assert [s.title for s in specs] == ["Animals", "Space"]
    assert specs[0].words == ["TIGER", "LION", "BEAR"]
    assert specs[1].words == ["MOON", "STAR"]


def test_read_puzzle_csv_auto_titles_blank_first_column(tmp_path):
    csv_path = tmp_path / "puzzles.csv"
    csv_path.write_text(",CAT,DOG\n,RED,BLUE\n")

    specs = read_puzzle_csv(csv_path)

    assert [s.title for s in specs] == ["Puzzle 1", "Puzzle 2"]


def test_read_puzzle_csv_skips_blank_rows_and_rows_without_words(tmp_path):
    csv_path = tmp_path / "puzzles.csv"
    csv_path.write_text("Animals,CAT,DOG\n\nEmpty\n,,\nSpace,MOON\n")

    specs = read_puzzle_csv(csv_path)

    assert [s.title for s in specs] == ["Animals", "Space"]


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
    # page, divider, answer key page, and any blank padding page).
    assert len(pages) <= 5


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

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from .difficulty import word_count_warning
from .grid import WordSearchGenerationError, WordSearchGenerator
from .render import (
    GRID_LINE_COLOR,
    load_body_font,
    load_font,
    load_heading_font,
    wrap_words_by_pixel,
)

# KDP paperback interior sized for 8.5x11in at the 300 DPI print requires.
# No bleed: nothing is drawn outside the margins, which keeps the layout
# simple and avoids the extra 0.125in bleed allowance entirely.
DPI = 300
PAGE_WIDTH_IN = 8.5
PAGE_HEIGHT_IN = 11.0
PAGE_W = round(PAGE_WIDTH_IN * DPI)
PAGE_H = round(PAGE_HEIGHT_IN * DPI)

# KDP's inside (gutter) margin needs to grow with page count to stay clear of
# the binding; 1.0in comfortably covers books up to a few hundred pages, with
# extra room beyond KDP's bare minimum since these are puzzles the reader
# marks up by hand near the grid's edge, not just text to read. Margins
# mirror left/right by page parity so facing pages read correctly once bound.
MARGIN_INSIDE_IN = 1.0
MARGIN_OUTSIDE_IN = 0.75
MARGIN_TOP_IN = 0.75
MARGIN_BOTTOM_IN = 0.85

# Extra breathing room between the margin and the puzzle grid itself, so a
# circled answer near the grid's edge never has to crowd the margin line.
GRID_PADDING_IN = 0.15

MIN_KDP_PAGES = 24

TITLE_SIZE = 100
AUTHOR_SIZE = 44
H1_SIZE = 78
H2_SIZE = 52
BODY_SIZE = 40
PUZZLE_TITLE_SIZE = 60
WORDLIST_HEADER_SIZE = 44
WORDLIST_BODY_SIZE = 38
MINI_TITLE_SIZE = 30
DIVIDER_SIZE = 90
PAGE_NUMBER_SIZE = 30
TOC_HEADER_SIZE = 64
TOC_ROW_SIZE = 32
TOC_ROW_HEIGHT_IN = 0.42

ANSWER_HIGHLIGHT_RGBA = (90, 90, 90, 100)
RULE_COLOR = "#555555"

# Accessibility preset: scales up every text element (grid letters already
# come out larger from that preset's smaller grid on the same fixed page).
LARGE_PRINT_TEXT_SCALE = 1.35


@dataclass
class PuzzleSpec:
    title: str
    words: list[str]
    trivia: str | None = None


def in_to_px(inches: float) -> int:
    return round(inches * DPI)


def text_scale_for(difficulty: str | None) -> float:
    return LARGE_PRINT_TEXT_SCALE if difficulty == "large-print" else 1.0


def page_margins(page_number: int) -> tuple[int, int, int, int]:
    """Returns (left, right, top, bottom) in pixels, mirroring the inside
    (gutter) margin to whichever side faces the spine for this page."""
    inside = in_to_px(MARGIN_INSIDE_IN)
    outside = in_to_px(MARGIN_OUTSIDE_IN)
    top = in_to_px(MARGIN_TOP_IN)
    bottom = in_to_px(MARGIN_BOTTOM_IN)
    if page_number % 2 == 1:
        return inside, outside, top, bottom
    return outside, inside, top, bottom


def new_page() -> Image.Image:
    return Image.new("RGB", (PAGE_W, PAGE_H), "white")


def stamp_page_number(img: Image.Image, number: int) -> None:
    draw = ImageDraw.Draw(img)
    draw.text(
        (PAGE_W / 2, PAGE_H - in_to_px(0.4)),
        str(number),
        font=load_body_font(PAGE_NUMBER_SIZE),
        fill="black",
        anchor="ma",
    )


def _draw_title_rule(draw: ImageDraw.ImageDraw, center_x: float, y: float, width: float) -> None:
    draw.line([(center_x - width / 2, y), (center_x + width / 2, y)], fill=RULE_COLOR, width=3)


def read_puzzle_csv(path: str | Path) -> list[PuzzleSpec]:
    """Reads one puzzle per row, with a required header row (its own content
    is ignored -- it's just skipped) and fixed columns: title, an optional
    trivia blurb (leave the cell blank if none; embed a blank line within
    the cell for multiple paragraphs), then every remaining column is a
    word. Words always start at the same column on every row regardless of
    whether a puzzle has trivia, which keeps a spreadsheet's columns lined
    up; there's no fixed limit on how many word columns a row can have."""
    specs: list[PuzzleSpec] = []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    for row in rows[1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        words = [w.strip() for w in row[2:] if w.strip()]
        if not words:
            continue
        title = row[0].strip() or f"Puzzle {len(specs) + 1}"
        trivia = row[1].strip() if len(row) > 1 else ""
        specs.append(PuzzleSpec(title=title, words=words, trivia=trivia or None))
    return specs


def _wrap_paragraph(text: str, font, max_width: int) -> list[str]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def _markdown_blocks(text: str) -> list[tuple[str, str]]:
    """Parses a tiny markdown subset: '# '/'## ' headings, '- '/'* ' bullets,
    blank-line-separated paragraphs. Anything else is treated as a paragraph,
    so plain, unformatted text still flows correctly. A wrapped continuation
    line (no marker of its own) stays part of whichever paragraph or bullet
    is currently open, rather than starting a stray new paragraph."""
    blocks: list[tuple[str, str]] = []
    open_type: str | None = None
    open_lines: list[str] = []

    def flush() -> None:
        nonlocal open_type, open_lines
        if open_lines:
            blocks.append((open_type, " ".join(open_lines)))
        open_type = None
        open_lines = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
        elif line.startswith("# "):
            flush()
            blocks.append(("h1", line[2:].strip()))
        elif line.startswith("## "):
            flush()
            blocks.append(("h2", line[3:].strip()))
        elif line.startswith("- ") or line.startswith("* "):
            flush()
            open_type = "bullet"
            open_lines = [line[2:].strip()]
        else:
            if open_type is None:
                open_type = "para"
            open_lines.append(line)
    flush()
    return blocks


def render_text_pages(
    markdown_text: str, start_page_number: int, text_scale: float = 1.0
) -> list[Image.Image]:
    """Flows a tiny-markdown document across as many pages as it needs."""
    blocks = _markdown_blocks(markdown_text)
    pages: list[Image.Image] = []
    page_number = start_page_number
    left, right, top, bottom = page_margins(page_number)
    printable_w = PAGE_W - left - right
    bottom_limit = PAGE_H - bottom

    img = new_page()
    draw = ImageDraw.Draw(img)
    y = top

    def start_new_page() -> None:
        nonlocal img, draw, y, page_number, left, right, printable_w
        pages.append(img)
        page_number += 1
        left, right, _, _ = page_margins(page_number)
        printable_w = PAGE_W - left - right
        img = new_page()
        draw = ImageDraw.Draw(img)
        y = top

    for block_type, text in blocks:
        if block_type == "h1":
            font = load_heading_font(round(H1_SIZE * text_scale))
            indent, align = 0, "center"
            lines = [text]
            gap_before, gap_after = in_to_px(0.15), in_to_px(0.12)
        elif block_type == "h2":
            font = load_heading_font(round(H2_SIZE * text_scale))
            indent, align = 0, "left"
            lines = [text]
            gap_before, gap_after = in_to_px(0.12), in_to_px(0.08)
        elif block_type == "bullet":
            font = load_body_font(round(BODY_SIZE * text_scale))
            indent, align = in_to_px(0.35), "left"
            lines = _wrap_paragraph("•  " + text, font, printable_w - indent)
            gap_before, gap_after = in_to_px(0.03), in_to_px(0.03)
        else:
            font = load_body_font(round(BODY_SIZE * text_scale))
            indent, align = 0, "left"
            lines = _wrap_paragraph(text, font, printable_w)
            gap_before, gap_after = in_to_px(0.05), in_to_px(0.14)

        line_height = int(font.size * 1.4)

        if y + gap_before + line_height > bottom_limit and y > top:
            start_new_page()
        y += gap_before

        for line in lines:
            if y + line_height > bottom_limit and y > top:
                start_new_page()
            if align == "center":
                draw.text((left + printable_w / 2, y), line, font=font, fill="black", anchor="ma")
            else:
                draw.text((left + indent, y), line, font=font, fill="black", anchor="la")
            y += line_height

        y += gap_after

    pages.append(img)
    return pages


def render_title_page(
    title: str, author: str | None, page_number: int, text_scale: float = 1.0
) -> Image.Image:
    img = new_page()
    draw = ImageDraw.Draw(img)
    title_y = PAGE_H * 0.4
    draw.text(
        (PAGE_W / 2, title_y),
        title,
        font=load_heading_font(round(TITLE_SIZE * text_scale)),
        fill="black",
        anchor="mm",
    )
    _draw_title_rule(draw, PAGE_W / 2, title_y + in_to_px(0.45), in_to_px(2.5))
    if author:
        draw.text(
            (PAGE_W / 2, title_y + in_to_px(0.75)),
            author,
            font=load_body_font(round(AUTHOR_SIZE * text_scale)),
            fill="black",
            anchor="mm",
        )
    return img


def render_section_divider(text: str, text_scale: float = 1.0) -> Image.Image:
    img = new_page()
    draw = ImageDraw.Draw(img)
    y = PAGE_H / 2
    draw.text(
        (PAGE_W / 2, y), text, font=load_heading_font(round(DIVIDER_SIZE * text_scale)),
        fill="black", anchor="mm",
    )
    _draw_title_rule(draw, PAGE_W / 2, y + in_to_px(0.4), in_to_px(2.5))
    return img


def render_puzzle_page(
    generator: WordSearchGenerator,
    title: str,
    page_number: int,
    puzzle_number: int | None = None,
    text_scale: float = 1.0,
) -> Image.Image:
    left, right, top, bottom = page_margins(page_number)
    printable_w = PAGE_W - left - right
    printable_h = PAGE_H - top - bottom

    img = new_page()
    draw = ImageDraw.Draw(img)

    heading_text = f"Puzzle {puzzle_number}: {title}" if puzzle_number else title
    title_font = load_heading_font(round(PUZZLE_TITLE_SIZE * text_scale))
    title_line_h = int(title_font.size * 1.3)
    rule_gap = in_to_px(0.1)
    title_h = title_line_h + rule_gap + in_to_px(0.15)
    title_y = top
    draw.text(
        (left + printable_w / 2, title_y), heading_text, font=title_font, fill="black", anchor="ma"
    )
    _draw_title_rule(
        draw, left + printable_w / 2, title_y + title_line_h + rule_gap, printable_w * 0.5
    )

    header_font = load_heading_font(round(WORDLIST_HEADER_SIZE * text_scale))
    word_font = load_body_font(round(WORDLIST_BODY_SIZE * text_scale))
    words = sorted(generator.display_words.values())
    wrapped = wrap_words_by_pixel(words, word_font, printable_w)
    header_h = int(header_font.size * 1.4)
    word_list_h = header_h + len(wrapped) * int(word_font.size * 1.4) + in_to_px(0.15)

    rows, cols = generator.rows, generator.cols
    grid_padding = in_to_px(GRID_PADDING_IN)
    grid_available_w = printable_w - grid_padding * 2
    grid_available_h = printable_h - title_h - word_list_h - in_to_px(0.1)
    cell_size = max(10, min(grid_available_w // cols, grid_available_h // rows))

    grid_w = cell_size * cols
    grid_h = cell_size * rows
    grid_left = left + (printable_w - grid_w) / 2
    grid_top = top + title_h + (grid_available_h - grid_h) / 2

    for r in range(rows + 1):
        y = grid_top + r * cell_size
        draw.line([(grid_left, y), (grid_left + grid_w, y)], fill=GRID_LINE_COLOR)
    for c in range(cols + 1):
        x = grid_left + c * cell_size
        draw.line([(x, grid_top), (x, grid_top + grid_h)], fill=GRID_LINE_COLOR)

    letter_font = load_font(int(cell_size * 0.55))
    for r in range(rows):
        for c in range(cols):
            cx = grid_left + c * cell_size + cell_size / 2
            cy = grid_top + r * cell_size + cell_size / 2
            draw.text(
                (cx, cy), generator.grid[r][c], font=letter_font, fill="black", anchor="mm"
            )

    word_list_top = grid_top + grid_h + in_to_px(0.15)
    draw.text(
        (left + printable_w / 2, word_list_top),
        "Find these words:",
        font=header_font,
        fill="black",
        anchor="ma",
    )
    y = word_list_top + header_h
    for line in wrapped:
        draw.text((left + printable_w / 2, y), line, font=word_font, fill="black", anchor="ma")
        y += int(word_font.size * 1.4)

    return img


def _draw_mini_answer_key(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    generator: WordSearchGenerator,
    title: str,
    qx: float,
    qy: float,
    quad_w: float,
    quad_h: float,
) -> None:
    title_font = load_heading_font(MINI_TITLE_SIZE)
    title_h = int(title_font.size * 1.4)
    draw.text((qx + quad_w / 2, qy), title, font=title_font, fill="black", anchor="ma")

    rows, cols = generator.rows, generator.cols
    avail_w = quad_w
    avail_h = quad_h - title_h
    cell = max(4, min(avail_w // cols, avail_h // rows))
    grid_w = cell * cols
    grid_h = cell * rows
    gx = qx + (quad_w - grid_w) / 2
    gy = qy + title_h + (avail_h - grid_h) / 2

    for r in range(rows + 1):
        y = gy + r * cell
        draw.line([(gx, y), (gx + grid_w, y)], fill=GRID_LINE_COLOR)
    for c in range(cols + 1):
        x = gx + c * cell
        draw.line([(x, gy), (x, gy + grid_h)], fill=GRID_LINE_COLOR)

    letter_font = load_font(max(6, int(cell * 0.6)))
    for r in range(rows):
        for c in range(cols):
            cx = gx + c * cell + cell / 2
            cy = gy + r * cell + cell / 2
            draw.text(
                (cx, cy), generator.grid[r][c], font=letter_font, fill="black", anchor="mm"
            )

    highlighted = {cell_rc for placed in generator.placements for cell_rc in placed.cells}
    if highlighted:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        for r, c in highlighted:
            x0, y0 = gx + c * cell, gy + r * cell
            odraw.rectangle([x0, y0, x0 + cell, y0 + cell], fill=ANSWER_HIGHLIGHT_RGBA)
        composited = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        img.paste(composited, (0, 0))


def render_answer_key_pages(
    entries: list[tuple[str, WordSearchGenerator]], start_page_number: int
) -> list[Image.Image]:
    """Lays out 4 mini answer keys per page (2x2), shaded with a uniform
    translucent gray over every solved cell -- print-safe in black & white
    and legible at quarter-page scale, where per-word outlines would not be."""
    pages: list[Image.Image] = []
    page_number = start_page_number
    per_page = 4
    for i in range(0, len(entries), per_page):
        chunk = entries[i : i + per_page]
        left, right, top, bottom = page_margins(page_number)
        printable_w = PAGE_W - left - right
        printable_h = PAGE_H - top - bottom

        img = new_page()
        draw = ImageDraw.Draw(img)
        header_h = in_to_px(0.45)
        draw.text(
            (left + printable_w / 2, top),
            "Answer Keys",
            font=load_heading_font(H2_SIZE),
            fill="black",
            anchor="ma",
        )

        gutter = in_to_px(0.25)
        quad_w = (printable_w - gutter) / 2
        quad_h = (printable_h - header_h - gutter) / 2
        quad_top = top + header_h
        positions = [
            (left, quad_top),
            (left + quad_w + gutter, quad_top),
            (left, quad_top + quad_h + gutter),
            (left + quad_w + gutter, quad_top + quad_h + gutter),
        ]

        for (title, generator), (qx, qy) in zip(chunk, positions):
            _draw_mini_answer_key(img, draw, generator, title, qx, qy, quad_w, quad_h)

        pages.append(img)
        page_number += 1

    return pages


def _toc_rows_per_page(text_scale: float = 1.0) -> int:
    # Top/bottom margins don't mirror by parity, so this is page-independent.
    _, _, top, bottom = page_margins(1)
    printable_h = PAGE_H - top - bottom
    header_h = in_to_px(0.9)
    row_h = in_to_px(TOC_ROW_HEIGHT_IN * text_scale)
    return max(1, (printable_h - header_h) // row_h)


def _render_toc_page(
    chunk: list[tuple[int, str, int]],
    page_number: int,
    is_first: bool,
    text_scale: float = 1.0,
) -> Image.Image:
    """chunk entries are (puzzle_number, title, puzzle_page_number)."""
    left, right, top, bottom = page_margins(page_number)
    printable_w = PAGE_W - left - right

    img = new_page()
    draw = ImageDraw.Draw(img)
    y = top

    if is_first:
        header_font = load_heading_font(round(TOC_HEADER_SIZE * text_scale))
        draw.text(
            (left + printable_w / 2, y), "Contents", font=header_font, fill="black", anchor="ma"
        )
        y += int(header_font.size * 1.3)
        _draw_title_rule(draw, left + printable_w / 2, y + in_to_px(0.08), in_to_px(2.0))
        y += in_to_px(0.35)
    else:
        y += in_to_px(0.15)

    row_h = in_to_px(TOC_ROW_HEIGHT_IN * text_scale)
    row_font = load_body_font(round(TOC_ROW_SIZE * text_scale))
    box_size = in_to_px(0.2 * text_scale)

    for puzzle_number, title, puzzle_page_number in chunk:
        cy = y + row_h / 2

        box_x0 = left
        draw.rectangle(
            [box_x0, cy - box_size / 2, box_x0 + box_size, cy + box_size / 2],
            outline="black",
            width=2,
        )

        text_x = box_x0 + box_size + in_to_px(0.15)
        label = f"{puzzle_number}. {title}"
        draw.text((text_x, cy), label, font=row_font, fill="black", anchor="lm")

        number_str = str(puzzle_page_number)
        number_w = draw.textlength(number_str, font=row_font)
        number_x = left + printable_w - number_w
        draw.text((number_x, cy), number_str, font=row_font, fill="black", anchor="lm")

        label_w = draw.textlength(label, font=row_font)
        dot_y = cy
        x = text_x + label_w + in_to_px(0.08)
        dot_limit = number_x - in_to_px(0.1)
        while x < dot_limit:
            draw.ellipse([x, dot_y - 1.5, x + 3, dot_y + 1.5], fill="black")
            x += 10

        y += row_h

    return img


def render_toc_pages(
    entries: list[tuple[int, str, int]],
    start_page_number: int,
    page_count: int,
    text_scale: float = 1.0,
) -> list[Image.Image]:
    """Renders a combined table of contents / progress checklist: a checkbox,
    puzzle number and title, and the page it starts on, dot-leadered to a
    right-aligned page number -- letting the reader both navigate to a
    puzzle and mark it done in the same list."""
    rows_per_page = _toc_rows_per_page(text_scale)
    pages: list[Image.Image] = []
    for i in range(page_count):
        chunk = entries[i * rows_per_page : (i + 1) * rows_per_page]
        pages.append(
            _render_toc_page(chunk, start_page_number + i, is_first=(i == 0), text_scale=text_scale)
        )
    return pages


def _force_recto(pages: list[Image.Image], page_number: int) -> int:
    """Inserts a blank page if page_number is even, so the next page (a
    puzzle, or the answer-key section) always starts on a right-hand
    (recto) page -- the convention in puzzle books, since the reader marks
    up the page and each puzzle should get a clean, dedicated spread rather
    than landing wherever the previous content happened to end."""
    if page_number % 2 == 0:
        pages.append(new_page())
        page_number += 1
    return page_number


def build_book(
    puzzle_specs: list[PuzzleSpec],
    rows: int,
    cols: int,
    allow_backwards: bool,
    directions: list[str] | None,
    seed: int | None,
    book_title: str,
    author: str | None = None,
    intro_text: str | None = None,
    instructions_text: str | None = None,
    difficulty: str | None = None,
) -> tuple[list[Image.Image], list[str]]:
    warnings: list[str] = []
    pages: list[Image.Image] = []
    page_number = 1
    text_scale = text_scale_for(difficulty)

    pages.append(render_title_page(book_title, author, page_number, text_scale))
    page_number += 1

    if intro_text:
        intro_pages = render_text_pages(intro_text, page_number, text_scale)
        pages += intro_pages
        page_number += len(intro_pages)

    if instructions_text:
        instructions_pages = render_text_pages(instructions_text, page_number, text_scale)
        pages += instructions_pages
        page_number += len(instructions_pages)

    # Reserve TOC/checklist placeholder pages now -- the exact page COUNT is
    # knowable upfront (rows-per-page is independent of the actual page
    # numbers, which are only fixed digits, not variable line counts), but
    # the real page numbers for each puzzle aren't known until after they're
    # laid out below. Placeholders are backfilled with real content once
    # every puzzle's page number is known.
    toc_index: int | None = None
    toc_page_number_start: int | None = None
    toc_page_count = 0
    if puzzle_specs:
        rows_per_page = _toc_rows_per_page(text_scale)
        toc_page_count = math.ceil(len(puzzle_specs) / rows_per_page)
        toc_index = len(pages)
        toc_page_number_start = page_number
        pages.extend(new_page() for _ in range(toc_page_count))
        page_number += toc_page_count

    entries: list[tuple[str, WordSearchGenerator]] = []
    toc_entries: list[tuple[int, str, int]] = []
    puzzle_number = 0

    # Every puzzle gets a dedicated left-hand (verso, even-numbered)
    # companion page immediately before it -- a trivia page if the puzzle
    # has one, otherwise left blank -- so a puzzle with trivia always has
    # somewhere to put it, rather than only sometimes getting a facing page
    # depending on upstream parity. Align to even once here so that holds
    # for every puzzle from the start.
    if page_number % 2 == 1:
        pages.append(new_page())
        page_number += 1

    for spec in puzzle_specs:
        generator = WordSearchGenerator(
            spec.words,
            rows=rows,
            cols=cols,
            allow_backwards=allow_backwards,
            directions=directions,
            seed=seed,
        )
        try:
            generator.generate()
        except WordSearchGenerationError as exc:
            warnings.append(f"{spec.title}: {exc} (puzzle skipped)")
            continue

        count_warning = word_count_warning(difficulty, len(generator.words))
        if count_warning:
            warnings.append(f"{spec.title}: {count_warning}")
        if generator.skipped:
            warnings.append(
                f"{spec.title}: could not place {len(generator.skipped)} word(s): "
                f"{', '.join(generator.skipped)}"
            )
        if generator.blocked_words_found:
            warnings.append(
                f"{spec.title}: could not avoid blocked word(s) in the grid: "
                f"{', '.join(generator.blocked_words_found)}"
            )

        puzzle_number += 1

        if spec.trivia:
            facts = [f.strip() for f in spec.trivia.split("\n\n") if f.strip()]
            doc = (
                "# Did You Know?\n\n## "
                + spec.title
                + "\n\n"
                + "\n\n".join(f"- {fact}" for fact in facts)
            )
            trivia_pages = render_text_pages(doc, page_number, text_scale)
            pages += trivia_pages
            page_number += len(trivia_pages)
        else:
            pages.append(new_page())
            page_number += 1
        # Safety net: a trivia blurb long enough to spill onto a second page
        # would otherwise flip parity for every puzzle after it.
        page_number = _force_recto(pages, page_number)

        pages.append(
            render_puzzle_page(
                generator,
                spec.title,
                page_number,
                puzzle_number=puzzle_number,
                text_scale=text_scale,
            )
        )
        toc_entries.append((puzzle_number, spec.title, page_number))
        page_number += 1
        entries.append((spec.title, generator))

    if toc_index is not None:
        toc_pages = render_toc_pages(
            toc_entries, toc_page_number_start, toc_page_count, text_scale
        )
        pages[toc_index : toc_index + toc_page_count] = toc_pages

    if entries:
        page_number = _force_recto(pages, page_number)
        pages.append(render_section_divider("Answer Keys", text_scale))
        page_number += 1

        answer_pages = render_answer_key_pages(entries, page_number)
        pages += answer_pages
        page_number += len(answer_pages)

    if len(pages) % 2 == 1:
        pages.append(new_page())

    if len(pages) < MIN_KDP_PAGES:
        warnings.append(
            f"Book is {len(pages)} page(s); KDP paperback requires at least "
            f"{MIN_KDP_PAGES}. Add more puzzles or front matter before uploading."
        )

    for i, page in enumerate(pages, start=1):
        stamp_page_number(page, i)

    return pages, warnings


def save_book(pages: list[Image.Image], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=DPI)

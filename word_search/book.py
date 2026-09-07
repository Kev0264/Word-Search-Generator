from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from .difficulty import word_count_warning
from .grid import WordSearchGenerationError, WordSearchGenerator
from .render import load_font, wrap_words_by_pixel

# KDP paperback interior sized for 8.5x11in at the 300 DPI print requires.
# No bleed: nothing is drawn outside the margins, which keeps the layout
# simple and avoids the extra 0.125in bleed allowance entirely.
DPI = 300
PAGE_WIDTH_IN = 8.5
PAGE_HEIGHT_IN = 11.0
PAGE_W = round(PAGE_WIDTH_IN * DPI)
PAGE_H = round(PAGE_HEIGHT_IN * DPI)

# KDP's inside (gutter) margin needs to grow with page count to stay clear of
# the binding; 0.75in comfortably covers books up to a few hundred pages.
# Margins mirror left/right by page parity so facing pages read correctly
# once bound.
MARGIN_INSIDE_IN = 0.75
MARGIN_OUTSIDE_IN = 0.5
MARGIN_TOP_IN = 0.6
MARGIN_BOTTOM_IN = 0.75

MIN_KDP_PAGES = 24

TITLE_SIZE = 100
AUTHOR_SIZE = 44
H1_SIZE = 78
H2_SIZE = 52
BODY_SIZE = 40
PUZZLE_TITLE_SIZE = 70
WORDLIST_HEADER_SIZE = 44
WORDLIST_BODY_SIZE = 38
MINI_TITLE_SIZE = 30
DIVIDER_SIZE = 90
PAGE_NUMBER_SIZE = 30

ANSWER_HIGHLIGHT_RGBA = (90, 90, 90, 100)


@dataclass
class PuzzleSpec:
    title: str
    words: list[str]


def in_to_px(inches: float) -> int:
    return round(inches * DPI)


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
        font=load_font(PAGE_NUMBER_SIZE),
        fill="black",
        anchor="ma",
    )


def read_puzzle_csv(path: str | Path) -> list[PuzzleSpec]:
    """Reads one puzzle per row: first column is the title (blank -> an
    auto-numbered "Puzzle N"), remaining columns are that puzzle's words."""
    specs: list[PuzzleSpec] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or not any(cell.strip() for cell in row):
                continue
            words = [w.strip() for w in row[1:] if w.strip()]
            if not words:
                continue
            title = row[0].strip() or f"Puzzle {len(specs) + 1}"
            specs.append(PuzzleSpec(title=title, words=words))
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


def render_text_pages(markdown_text: str, start_page_number: int) -> list[Image.Image]:
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
            font, indent, align = load_font(H1_SIZE), 0, "center"
            lines = [text]
            gap_before, gap_after = in_to_px(0.15), in_to_px(0.12)
        elif block_type == "h2":
            font, indent, align = load_font(H2_SIZE), 0, "left"
            lines = [text]
            gap_before, gap_after = in_to_px(0.12), in_to_px(0.08)
        elif block_type == "bullet":
            font, indent, align = load_font(BODY_SIZE), in_to_px(0.35), "left"
            lines = _wrap_paragraph("•  " + text, font, printable_w - indent)
            gap_before, gap_after = in_to_px(0.03), in_to_px(0.03)
        else:
            font, indent, align = load_font(BODY_SIZE), 0, "left"
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


def render_title_page(title: str, author: str | None, page_number: int) -> Image.Image:
    img = new_page()
    draw = ImageDraw.Draw(img)
    draw.text(
        (PAGE_W / 2, PAGE_H * 0.4),
        title,
        font=load_font(TITLE_SIZE),
        fill="black",
        anchor="mm",
    )
    if author:
        draw.text(
            (PAGE_W / 2, PAGE_H * 0.4 + in_to_px(0.7)),
            author,
            font=load_font(AUTHOR_SIZE),
            fill="black",
            anchor="mm",
        )
    return img


def render_section_divider(text: str) -> Image.Image:
    img = new_page()
    draw = ImageDraw.Draw(img)
    draw.text((PAGE_W / 2, PAGE_H / 2), text, font=load_font(DIVIDER_SIZE), fill="black", anchor="mm")
    return img


def render_puzzle_page(
    generator: WordSearchGenerator, title: str, page_number: int
) -> Image.Image:
    left, right, top, bottom = page_margins(page_number)
    printable_w = PAGE_W - left - right
    printable_h = PAGE_H - top - bottom

    img = new_page()
    draw = ImageDraw.Draw(img)

    title_font = load_font(PUZZLE_TITLE_SIZE)
    title_h = int(title_font.size * 1.4) + in_to_px(0.15)
    draw.text((left + printable_w / 2, top), title, font=title_font, fill="black", anchor="ma")

    header_font = load_font(WORDLIST_HEADER_SIZE)
    word_font = load_font(WORDLIST_BODY_SIZE)
    words = sorted(generator.display_words.values())
    wrapped = wrap_words_by_pixel(words, word_font, printable_w)
    header_h = int(header_font.size * 1.4)
    word_list_h = header_h + len(wrapped) * int(word_font.size * 1.4) + in_to_px(0.15)

    rows, cols = generator.rows, generator.cols
    grid_available_w = printable_w
    grid_available_h = printable_h - title_h - word_list_h - in_to_px(0.1)
    cell_size = max(10, min(grid_available_w // cols, grid_available_h // rows))

    grid_w = cell_size * cols
    grid_h = cell_size * rows
    grid_left = left + (printable_w - grid_w) / 2
    grid_top = top + title_h + (grid_available_h - grid_h) / 2

    for r in range(rows + 1):
        y = grid_top + r * cell_size
        draw.line([(grid_left, y), (grid_left + grid_w, y)], fill="black")
    for c in range(cols + 1):
        x = grid_left + c * cell_size
        draw.line([(x, grid_top), (x, grid_top + grid_h)], fill="black")

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
    title_font = load_font(MINI_TITLE_SIZE)
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
        draw.line([(gx, y), (gx + grid_w, y)], fill="black")
    for c in range(cols + 1):
        x = gx + c * cell
        draw.line([(x, gy), (x, gy + grid_h)], fill="black")

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
            font=load_font(H2_SIZE),
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

    pages.append(render_title_page(book_title, author, page_number))
    page_number += 1

    if intro_text:
        intro_pages = render_text_pages(intro_text, page_number)
        pages += intro_pages
        page_number += len(intro_pages)

    if instructions_text:
        instructions_pages = render_text_pages(instructions_text, page_number)
        pages += instructions_pages
        page_number += len(instructions_pages)

    entries: list[tuple[str, WordSearchGenerator]] = []
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

        pages.append(render_puzzle_page(generator, spec.title, page_number))
        page_number += 1
        entries.append((spec.title, generator))

    if entries:
        pages.append(render_section_divider("Answer Keys"))
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

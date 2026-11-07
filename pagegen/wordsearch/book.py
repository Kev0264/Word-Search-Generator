from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from ..bookparts import (  # noqa: F401  (several re-exported for callers/tests)
    DPI,
    H2_SIZE,
    LARGE_PRINT_TEXT_SCALE,
    MIN_KDP_PAGES,
    MIN_LARGE_PRINT_PX,
    PAGE_H,
    PAGE_W,
    RULE_COLOR,
    _draw_title_rule,
    _fit_heading_lines,
    _force_recto,
    _markdown_blocks,
    _wrap_paragraph,
    in_to_px,
    new_page,
    page_margins,
    render_copyright_page,
    render_section_divider,
    render_text_pages,
    render_title_page,
    save_book,
    scaled_font_px,
    stamp_page_number,
)
from ..fonts import load_body_font, load_font, load_heading_font, wrap_words_by_pixel
from .difficulty import word_count_warning
from .grid import WordSearchGenerationError, WordSearchGenerator
from .render import GRID_LINE_COLOR

# Extra breathing room between the margin and the puzzle grid itself, so a
# circled answer near the grid's edge never has to crowd the margin line.
GRID_PADDING_IN = 0.15

# Each puzzle's grid placement is independent of every other puzzle's, so a
# blocked-word collision (two of the puzzle's own chosen words crossing to
# spell something unintended) is retried per-puzzle with a different seed
# rather than by searching for one lucky seed for the entire book.
PLACEMENT_RETRY_ATTEMPTS = 25

PUZZLE_TITLE_SIZE = 60
WORDLIST_HEADER_SIZE = 44
WORDLIST_BODY_SIZE = 38
MINI_TITLE_SIZE = 30
TOC_HEADER_SIZE = 64
TOC_ROW_SIZE = 32
TOC_ROW_HEIGHT_IN = 0.42

ANSWER_HIGHLIGHT_RGBA = (90, 90, 90, 100)

# Label for the section holding puzzles whose Category cell was left blank,
# when at least one other puzzle in the book does have a category.
DEFAULT_CATEGORY_FALLBACK_LABEL = "More to Explore"


@dataclass
class PuzzleSpec:
    title: str
    words: list[str]
    trivia: str | None = None
    category: str | None = None


@dataclass
class TocRow:
    """One row of the table of contents: either a puzzle (with its checkbox,
    number, and title) or a bold category heading with no checkbox."""

    kind: str  # "puzzle" or "category"
    title: str
    page_number: int
    number: int | None = None  # puzzle number; unused for category rows


def text_scale_for(difficulty: str | None) -> float:
    return LARGE_PRINT_TEXT_SCALE if difficulty == "large-print" else 1.0


def read_puzzle_csv(path: str | Path) -> list[PuzzleSpec]:
    """Reads one puzzle per row, with a required header row and fixed
    columns: title, an optional trivia blurb (leave the cell blank if none;
    embed a blank line within the cell for multiple paragraphs), an optional
    `Category` column, then every remaining column is a word. The Category
    column is detected by its header, case-insensitively -- old 3-column
    (Title, Trivia, Words...) CSVs keep working unchanged, since without a
    "Category" header the third column is just the first word column, as
    before. Words always start at the same column on every row regardless of
    whether a puzzle has trivia, which keeps a spreadsheet's columns lined
    up; there's no fixed limit on how many word columns a row can have."""
    specs: list[PuzzleSpec] = []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header = rows[0] if rows else []
    has_category_column = len(header) > 2 and header[2].strip().lower() == "category"
    words_start = 3 if has_category_column else 2
    for row in rows[1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        words = [w.strip() for w in row[words_start:] if w.strip()]
        if not words:
            continue
        title = row[0].strip() or f"Puzzle {len(specs) + 1}"
        trivia = row[1].strip() if len(row) > 1 else ""
        category = row[2].strip() if has_category_column and len(row) > 2 else ""
        specs.append(
            PuzzleSpec(title=title, words=words, trivia=trivia or None, category=category or None)
        )
    return specs


def organize_puzzle_specs(
    puzzle_specs: list[PuzzleSpec],
    alphabetize: bool = False,
    category_fallback_label: str = DEFAULT_CATEGORY_FALLBACK_LABEL,
) -> list[tuple[str | None, list[PuzzleSpec]]]:
    """Groups puzzles into one section per distinct category value, in order
    of each category's first appearance (uncategorized puzzles are bucketed
    into a fallback section, always placed last). If no puzzle has a
    category, returns everything as a single unlabeled section -- callers
    should treat a None category as "no section divider needed".

    With alphabetize=True, sections are sorted alphabetically by name and
    puzzles alphabetically by title within each section; the fallback
    section still sorts last. With no categories at all, alphabetize just
    sorts the flat puzzle list by title.
    """
    if not any(spec.category for spec in puzzle_specs):
        specs = puzzle_specs
        if alphabetize:
            specs = sorted(specs, key=lambda s: s.title.lower())
        return [(None, specs)]

    groups: dict[str, list[PuzzleSpec]] = {}
    order: list[str] = []
    fallback: list[PuzzleSpec] = []
    for spec in puzzle_specs:
        if not spec.category:
            fallback.append(spec)
            continue
        if spec.category not in groups:
            groups[spec.category] = []
            order.append(spec.category)
        groups[spec.category].append(spec)

    if alphabetize:
        order = sorted(order, key=str.lower)
        for category in order:
            groups[category].sort(key=lambda s: s.title.lower())
        fallback.sort(key=lambda s: s.title.lower())

    result = [(category, groups[category]) for category in order]
    if fallback:
        result.append((category_fallback_label, fallback))
    return result


def find_duplicate_puzzle_warnings(specs: list[PuzzleSpec]) -> list[str]:
    """Flags likely copy-paste mistakes in a puzzle spreadsheet: the same
    title used twice, or two different-looking rows that hide an identical
    word list. Neither is fatal, so both are reported as warnings rather
    than blocking the build."""
    warnings: list[str] = []

    first_title_at: dict[str, int] = {}
    for number, spec in enumerate(specs, start=1):
        key = spec.title.strip().lower()
        if key in first_title_at:
            warnings.append(
                f'Duplicate puzzle title "{spec.title}" (puzzles '
                f"{first_title_at[key]} and {number}) -- check for a copy-paste mistake."
            )
        else:
            first_title_at[key] = number

    first_words_at: dict[tuple[str, ...], tuple[int, str]] = {}
    for number, spec in enumerate(specs, start=1):
        key = tuple(sorted(w.upper() for w in spec.words))
        if key in first_words_at:
            other_number, other_title = first_words_at[key]
            warnings.append(
                f'"{other_title}" (puzzle {other_number}) and "{spec.title}" '
                f"(puzzle {number}) have identical word lists -- check for a "
                "copy-paste mistake."
            )
        else:
            first_words_at[key] = (number, spec.title)

    return warnings


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
    title_font = load_heading_font(scaled_font_px(PUZZLE_TITLE_SIZE, text_scale))
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

    header_font = load_heading_font(scaled_font_px(WORDLIST_HEADER_SIZE, text_scale))
    word_font = load_body_font(scaled_font_px(WORDLIST_BODY_SIZE, text_scale))
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
            draw.text((cx, cy), generator.grid[r][c], font=letter_font, fill="black", anchor="mm")

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
    text_scale: float = 1.0,
) -> None:
    title_font = load_heading_font(scaled_font_px(MINI_TITLE_SIZE, text_scale))
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
            draw.text((cx, cy), generator.grid[r][c], font=letter_font, fill="black", anchor="mm")

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
    entries: list[tuple[str, WordSearchGenerator]],
    start_page_number: int,
    text_scale: float = 1.0,
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
        header_h = in_to_px(0.45 * text_scale)
        draw.text(
            (left + printable_w / 2, top),
            "Answer Keys",
            font=load_heading_font(scaled_font_px(H2_SIZE, text_scale)),
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
            _draw_mini_answer_key(img, draw, generator, title, qx, qy, quad_w, quad_h, text_scale)

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
    chunk: list[TocRow],
    page_number: int,
    is_first: bool,
    text_scale: float = 1.0,
) -> Image.Image:
    left, right, top, bottom = page_margins(page_number)
    printable_w = PAGE_W - left - right

    img = new_page()
    draw = ImageDraw.Draw(img)
    y = top

    if is_first:
        header_font = load_heading_font(scaled_font_px(TOC_HEADER_SIZE, text_scale))
        draw.text(
            (left + printable_w / 2, y), "Contents", font=header_font, fill="black", anchor="ma"
        )
        y += int(header_font.size * 1.3)
        _draw_title_rule(draw, left + printable_w / 2, y + in_to_px(0.08), in_to_px(2.0))
        y += in_to_px(0.35)
    else:
        y += in_to_px(0.15)

    row_h = in_to_px(TOC_ROW_HEIGHT_IN * text_scale)
    row_font = load_body_font(scaled_font_px(TOC_ROW_SIZE, text_scale))
    heading_font = load_heading_font(scaled_font_px(TOC_ROW_SIZE, text_scale))
    box_size = in_to_px(0.2 * text_scale)

    for row in chunk:
        cy = y + row_h / 2

        if row.kind == "category":
            # A bold heading row with no checkbox, distinguishing a section
            # divider's entry from the checkbox-and-title puzzle rows below it.
            font = heading_font
            text_x = left
            label = row.title
        else:
            font = row_font
            box_x0 = left
            draw.rectangle(
                [box_x0, cy - box_size / 2, box_x0 + box_size, cy + box_size / 2],
                outline="black",
                width=2,
            )
            text_x = box_x0 + box_size + in_to_px(0.15)
            label = f"{row.number}. {row.title}"

        draw.text((text_x, cy), label, font=font, fill="black", anchor="lm")

        number_str = str(row.page_number)
        number_w = draw.textlength(number_str, font=font)
        number_x = left + printable_w - number_w
        draw.text((number_x, cy), number_str, font=font, fill="black", anchor="lm")

        label_w = draw.textlength(label, font=font)
        dot_y = cy
        x = text_x + label_w + in_to_px(0.08)
        dot_limit = number_x - in_to_px(0.1)
        while x < dot_limit:
            draw.ellipse([x, dot_y - 1.5, x + 3, dot_y + 1.5], fill="black")
            x += 10

        y += row_h

    return img


def render_toc_pages(
    entries: list[TocRow],
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


def difficulty_placeholders(directions: list[str] | None, allow_backwards: bool) -> dict[str, str]:
    """Short phrases describing the actual placement rules used for this
    book, so an intro/instructions file can reference `{{directions}}`,
    `{{backwards}}`, and `{{scan_tip}}` instead of hardcoding text that's
    only true for some difficulties (e.g. "easy" never places words
    backwards or diagonally)."""
    has_diagonals = directions is None or any(d in ("NE", "NW", "SE", "SW") for d in directions)
    return {
        "directions": (
            "Words can appear horizontally, vertically, or diagonally"
            if has_diagonals
            else "Words can appear horizontally or vertically"
        ),
        "backwards": (
            "Words can be spelled forwards or backwards"
            if allow_backwards
            else "Words are always spelled forwards"
        ),
        "scan_tip": (
            "Scan row by row, then column by column, then try the diagonals"
            if has_diagonals
            else "Scan row by row, then column by column"
        ),
    }


def apply_placeholders(text: str, placeholders: dict[str, str]) -> str:
    for key, value in placeholders.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def build_book(
    puzzle_specs: list[PuzzleSpec],
    rows: int,
    cols: int,
    allow_backwards: bool,
    directions: list[str] | None,
    seed: int | None,
    book_title: str,
    author: str | None = None,
    subtitle: str | None = None,
    intro_text: str | None = None,
    instructions_text: str | None = None,
    difficulty: str | None = None,
    year: int | None = None,
    alphabetize: bool = False,
    category_fallback_label: str = DEFAULT_CATEGORY_FALLBACK_LABEL,
) -> tuple[list[Image.Image], list[str]]:
    warnings: list[str] = list(find_duplicate_puzzle_warnings(puzzle_specs))
    pages: list[Image.Image] = []
    page_number = 1
    text_scale = text_scale_for(difficulty)
    if year is None:
        year = date.today().year

    # If any puzzle has a category, group same-category puzzles together
    # (each getting its own section-divider page and TOC heading) instead of
    # processing puzzle_specs in raw CSV order. Uncategorized puzzles bucket
    # into a labeled fallback section. With no categories at all, this is a
    # single unlabeled section -- behaves exactly as before.
    sections = organize_puzzle_specs(puzzle_specs, alphabetize, category_fallback_label)
    has_sections = any(category is not None for category, _ in sections)
    ordered_specs: list[PuzzleSpec] = [spec for _, specs in sections for spec in specs]
    section_starts: dict[int, str] = {}
    if has_sections:
        index = 0
        for category, specs in sections:
            section_starts[index] = category
            index += len(specs)

    pages.append(render_title_page(book_title, author, page_number, text_scale, subtitle=subtitle))
    page_number += 1

    pages.append(render_copyright_page(book_title, author, year, page_number, text_scale))
    page_number += 1

    placeholders = difficulty_placeholders(directions, allow_backwards)

    if intro_text:
        intro_pages = render_text_pages(
            apply_placeholders(intro_text, placeholders), page_number, text_scale
        )
        pages += intro_pages
        page_number += len(intro_pages)

    if instructions_text:
        instructions_pages = render_text_pages(
            apply_placeholders(instructions_text, placeholders), page_number, text_scale
        )
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
        # Each category heading takes up one row of its own, alongside every
        # puzzle's row, when this book is organized into labeled sections.
        toc_row_count = len(ordered_specs) + (len(sections) if has_sections else 0)
        toc_page_count = math.ceil(toc_row_count / rows_per_page)
        toc_index = len(pages)
        toc_page_number_start = page_number
        pages.extend(new_page() for _ in range(toc_page_count))
        page_number += toc_page_count

    entries: list[tuple[str, WordSearchGenerator]] = []
    toc_entries: list[TocRow] = []
    puzzle_number = 0

    # Every puzzle gets a dedicated left-hand (verso, even-numbered)
    # companion page immediately before it -- a trivia page if the puzzle
    # has one, otherwise left blank -- so a puzzle with trivia always has
    # somewhere to put it, rather than only sometimes getting a facing page
    # depending on upstream parity. Align to even once here so that holds
    # for every puzzle from the start. When the book is sectioned, the first
    # section's divider (below) establishes this same alignment instead.
    if not has_sections and page_number % 2 == 1:
        pages.append(new_page())
        page_number += 1

    for puzzle_index, spec in enumerate(ordered_specs):
        if puzzle_index in section_starts:
            category_label = section_starts[puzzle_index]
            page_number = _force_recto(pages, page_number)
            pages.append(render_section_divider(category_label, text_scale))
            toc_entries.append(
                TocRow(kind="category", title=category_label, page_number=page_number)
            )
            page_number += 1

        generator: WordSearchGenerator | None = None
        generation_error: WordSearchGenerationError | None = None
        for attempt in range(PLACEMENT_RETRY_ATTEMPTS):
            trial_seed = None if seed is None else seed + puzzle_index * 1000 + attempt
            trial = WordSearchGenerator(
                spec.words,
                rows=rows,
                cols=cols,
                allow_backwards=allow_backwards,
                directions=directions,
                seed=trial_seed,
            )
            try:
                trial.generate()
            except WordSearchGenerationError as exc:
                generation_error = exc
                generator = None
                break
            generator = trial
            if not generator.blocked_words_found and not generator.duplicate_words_found:
                break

        if generator is None:
            warnings.append(f"{spec.title}: {generation_error} (puzzle skipped)")
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
        if generator.duplicate_words_found:
            warnings.append(
                f"{spec.title}: word(s) accidentally appear more than once in the grid: "
                f"{', '.join(generator.duplicate_words_found)}"
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
        toc_entries.append(
            TocRow(kind="puzzle", title=spec.title, page_number=page_number, number=puzzle_number)
        )
        page_number += 1
        entries.append((spec.title, generator))

    if toc_index is not None:
        toc_pages = render_toc_pages(toc_entries, toc_page_number_start, toc_page_count, text_scale)
        pages[toc_index : toc_index + toc_page_count] = toc_pages

    if entries:
        page_number = _force_recto(pages, page_number)
        pages.append(render_section_divider("Answer Keys", text_scale))
        page_number += 1

        answer_pages = render_answer_key_pages(entries, page_number, text_scale)
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

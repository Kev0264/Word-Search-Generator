"""Front matter and other generic pages for KDP book interiors: title and
copyright pages, flowing markdown text, section dividers, recto alignment.

Everything here lays out on the KDP_BOOK format (8.5x11in, mirrored gutter
margins), which is the only format that gets book front matter -- loose
printables (Letter/A4) skip straight to their content pages.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .fonts import (
    load_body_font,
    load_heading_font,
    load_italic_font,
    wrap_paragraph,
)
from .layout import KDP_BOOK, MIN_KDP_PAGES, PAGE_NUMBER_SIZE, save_pdf  # noqa: F401

DPI = KDP_BOOK.dpi
PAGE_WIDTH_IN = KDP_BOOK.width_in
PAGE_HEIGHT_IN = KDP_BOOK.height_in
PAGE_W = KDP_BOOK.width_px
PAGE_H = KDP_BOOK.height_px
MARGIN_INSIDE_IN = KDP_BOOK.margin_inside_in
MARGIN_OUTSIDE_IN = KDP_BOOK.margin_outside_in
MARGIN_TOP_IN = KDP_BOOK.margin_top_in
MARGIN_BOTTOM_IN = KDP_BOOK.margin_bottom_in

TITLE_SIZE = 100
SUBTITLE_SIZE = 52
AUTHOR_SIZE = 44
COPYRIGHT_SIZE = 28
H1_SIZE = 78
H2_SIZE = 52
BODY_SIZE = 40
DIVIDER_SIZE = 90

RULE_COLOR = "#555555"

# Accessibility preset: scales up every text element.
LARGE_PRINT_TEXT_SCALE = 1.35

# KDP requires a large-print book's text to be 16pt or larger to be listed as
# such. A flat 1.35x multiplier undershoots that floor for any element whose
# base (medium-print) size was already small -- e.g. the word list comes out
# to just ~12pt -- so every scaled size is additionally floored in points.
MIN_LARGE_PRINT_PT = 16
MIN_LARGE_PRINT_PX = math.ceil(MIN_LARGE_PRINT_PT * DPI / 72)

DEFAULT_COPYRIGHT_NOTE = (
    "Facts researched from a variety of public sources and independently verified."
)

_wrap_paragraph = wrap_paragraph


def in_to_px(inches: float) -> int:
    return round(inches * DPI)


def scaled_font_px(base_px: float, text_scale: float) -> int:
    """Applies text_scale to a base font size, then -- only when a scale is
    actually in effect -- floors the result to MIN_LARGE_PRINT_PX so every
    scaled text element genuinely qualifies as large print, not just ones
    whose base size happened to already be large."""
    size = round(base_px * text_scale)
    if text_scale > 1.0:
        size = max(size, MIN_LARGE_PRINT_PX)
    return size


def page_margins(page_number: int) -> tuple[int, int, int, int]:
    """Returns (left, right, top, bottom) in pixels, mirroring the inside
    (gutter) margin to whichever side faces the spine for this page."""
    return KDP_BOOK.margins(page_number)


def new_page() -> Image.Image:
    return KDP_BOOK.new_page()


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
            font = load_heading_font(scaled_font_px(H1_SIZE, text_scale))
            indent, align = 0, "center"
            lines = [text]
            gap_before, gap_after = in_to_px(0.15), in_to_px(0.12)
        elif block_type == "h2":
            font = load_heading_font(scaled_font_px(H2_SIZE, text_scale))
            indent, align = 0, "left"
            lines = [text]
            gap_before, gap_after = in_to_px(0.12), in_to_px(0.08)
        elif block_type == "bullet":
            font = load_body_font(scaled_font_px(BODY_SIZE, text_scale))
            indent, align = in_to_px(0.35), "left"
            lines = _wrap_paragraph("•  " + text, font, printable_w - indent)
            gap_before, gap_after = in_to_px(0.03), in_to_px(0.03)
        else:
            font = load_body_font(scaled_font_px(BODY_SIZE, text_scale))
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


def _fit_heading_lines(
    text: str, printable_w: int, base_size: int, min_size: int
) -> tuple[ImageFont.ImageFont, list[str]]:
    """Shrinks a heading font until its wrapped text fits in at most two
    lines within printable_w, down to min_size."""
    size = base_size
    font = load_heading_font(size)
    lines = _wrap_paragraph(text, font, printable_w)
    while len(lines) > 2 and size > min_size:
        size -= 4
        font = load_heading_font(size)
        lines = _wrap_paragraph(text, font, printable_w)
    return font, lines


def render_title_page(
    title: str,
    author: str | None,
    page_number: int,
    text_scale: float = 1.0,
    subtitle: str | None = None,
) -> Image.Image:
    img = new_page()
    draw = ImageDraw.Draw(img)
    left, right, _, _ = page_margins(page_number)
    printable_w = PAGE_W - left - right

    title_size = scaled_font_px(TITLE_SIZE, text_scale)
    title_font, title_lines = _fit_heading_lines(
        title, printable_w, title_size, round(title_size * 0.45)
    )
    title_line_height = int(title_font.size * 1.15)
    title_block_height = title_line_height * len(title_lines)

    subtitle_font = None
    subtitle_lines: list[str] = []
    subtitle_line_height = 0
    subtitle_block_height = 0
    subtitle_gap = in_to_px(0.18) if subtitle else 0
    if subtitle:
        subtitle_size = scaled_font_px(SUBTITLE_SIZE, text_scale)
        size = subtitle_size
        font = load_italic_font(size)
        lines = _wrap_paragraph(subtitle, font, printable_w)
        min_size = round(subtitle_size * 0.5)
        while len(lines) > 2 and size > min_size:
            size -= 4
            font = load_italic_font(size)
            lines = _wrap_paragraph(subtitle, font, printable_w)
        subtitle_font, subtitle_lines = font, lines
        subtitle_line_height = int(subtitle_font.size * 1.2)
        subtitle_block_height = subtitle_line_height * len(subtitle_lines)

    total_height = title_block_height + subtitle_gap + subtitle_block_height
    title_y = PAGE_H * 0.4
    top_of_block = title_y - total_height / 2

    for i, line in enumerate(title_lines):
        line_center_y = top_of_block + title_line_height * i + title_line_height / 2
        draw.text((PAGE_W / 2, line_center_y), line, font=title_font, fill="black", anchor="mm")

    cursor_y = top_of_block + title_block_height
    if subtitle and subtitle_font is not None:
        cursor_y += subtitle_gap
        for i, line in enumerate(subtitle_lines):
            line_center_y = cursor_y + subtitle_line_height * i + subtitle_line_height / 2
            draw.text(
                (PAGE_W / 2, line_center_y), line, font=subtitle_font, fill="#333333", anchor="mm"
            )
        cursor_y += subtitle_block_height

    rule_y = cursor_y + in_to_px(0.25)
    _draw_title_rule(draw, PAGE_W / 2, rule_y, in_to_px(2.5))
    if author:
        draw.text(
            (PAGE_W / 2, rule_y + in_to_px(0.3)),
            author,
            font=load_body_font(scaled_font_px(AUTHOR_SIZE, text_scale)),
            fill="black",
            anchor="mm",
        )
    return img


def render_copyright_page(
    book_title: str,
    author: str | None,
    year: int,
    page_number: int,
    text_scale: float = 1.0,
    note: str | None = DEFAULT_COPYRIGHT_NOTE,
) -> Image.Image:
    """The copyright/imprint page conventionally on the back of the title
    page (page 2, the title page's verso) in a published book."""
    left, right, top, bottom = page_margins(page_number)
    printable_w = PAGE_W - left - right

    notice = f"© {year} {author}" if author else f"© {year} {book_title}"
    lines_to_draw = [
        notice,
        "All rights reserved.",
        "",
        "No part of this publication may be reproduced, distributed, or "
        "transmitted in any form or by any means, including photocopying, "
        "recording, or other electronic or mechanical methods, without "
        "prior written permission from the publisher, except for brief "
        "quotations embodied in critical reviews and certain other "
        "noncommercial uses permitted by copyright law.",
    ]
    if note:
        lines_to_draw += ["", note]

    font = load_body_font(scaled_font_px(COPYRIGHT_SIZE, text_scale))
    line_height = int(font.size * 1.5)

    # Wrap every line up front so the block's total height is known before
    # drawing -- large-print's much bigger copyright text can otherwise
    # overflow the bottom margin if we always start from the same fixed
    # vertical position regardless of how tall the block turns out to be.
    all_lines: list[str] = []
    for line in lines_to_draw:
        all_lines.extend(_wrap_paragraph(line, font, printable_w) if line else [""])
    total_height = len(all_lines) * line_height

    img = new_page()
    draw = ImageDraw.Draw(img)
    y = min(PAGE_H * 0.6, PAGE_H - bottom - total_height)
    for line in all_lines:
        if line:
            draw.text((left + printable_w / 2, y), line, font=font, fill="black", anchor="ma")
        y += line_height
    return img


def render_section_divider(text: str, text_scale: float = 1.0) -> Image.Image:
    img = new_page()
    draw = ImageDraw.Draw(img)
    y = PAGE_H / 2
    draw.text(
        (PAGE_W / 2, y),
        text,
        font=load_heading_font(scaled_font_px(DIVIDER_SIZE, text_scale)),
        fill="black",
        anchor="mm",
    )
    _draw_title_rule(draw, PAGE_W / 2, y + in_to_px(0.4), in_to_px(2.5))
    return img


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


def save_book(pages: list[Image.Image], path: str | Path) -> None:
    save_pdf(pages, path, DPI)

"""Fill-in tarot spread journal pages: date/moon/deck fields, the question,
a scaled diagram of the card layout, a numbered key with a line for each
card drawn, and lined space for the reading."""

from __future__ import annotations

from datetime import date

from PIL import Image, ImageDraw

from .. import bookparts
from ..fonts import wrap_paragraph
from ..layout import KDP_BOOK, MIN_KDP_PAGES, PageFormat, stamp_page_numbers
from ..ornaments import draw_header, paste_center, render_themed_title_page, sparkle, start_page
from ..theme import PLAIN, Theme
from .spreads import CARD_ASPECT, SPREADS, Spread

# Cap on drawn card width so a one-card spread doesn't fill the page.
MAX_CARD_WIDTH_IN = 1.25
# Show each position's name under its card only for small, non-overlapping
# spreads; bigger ones rely on the numbered key alone.
MAX_CARDS_FOR_INLINE_LABELS = 5


def _rule(draw: ImageDraw.ImageDraw, x0: float, x1: float, y: float, color: str) -> None:
    draw.line([(x0, y), (x1, y)], fill=color, width=2)


def _draw_field(draw, theme: Theme, x: float, y: float, width: float, label: str, font) -> None:
    draw.text((x, y), label, font=font, fill=theme.ink, anchor="ls")
    label_w = draw.textlength(label + " ", font=font)
    _rule(draw, x + label_w, x + width, y + 4, theme.grid)


def _draw_diagram(
    page: Image.Image,
    theme: Theme,
    spread: Spread,
    fmt: PageFormat,
    left: float,
    top: float,
    width: float,
    max_height: float,
) -> float:
    """Draws the spread scaled to fit within width x max_height, anchored at
    the top, and returns the height actually used -- so a small spread whose
    cards hit MAX_CARD_WIDTH_IN doesn't leave a band of dead space below."""

    def extent(p):
        w, h = (CARD_ASPECT, 1.0) if p.rotated else (1.0, CARD_ASPECT)
        return p.x - w / 2, p.y - h / 2, p.x + w / 2, p.y + h / 2

    inline_labels = len(spread.positions) <= MAX_CARDS_FOR_INLINE_LABELS and not any(
        p.rotated for p in spread.positions
    )
    draw = ImageDraw.Draw(page)
    label_font = theme.body_font(fmt.px(0.1))
    label_reserve = label_font.size * 3.2 if inline_labels else 0

    boxes = [extent(p) for p in spread.positions]
    min_x = min(b[0] for b in boxes)
    min_y = min(b[1] for b in boxes)
    span_x = max(b[2] for b in boxes) - min_x
    span_y = max(b[3] for b in boxes) - min_y
    scale = min(width / span_x, (max_height - label_reserve) / span_y, fmt.px(MAX_CARD_WIDTH_IN))
    offset_x = left + (width - span_x * scale) / 2 - min_x * scale
    offset_y = top - min_y * scale
    # A card with a sideways card laid across it only shows its top and
    # bottom strips, so its number goes in the top strip instead.
    crossed = {(p.x, p.y) for p in spread.positions if p.rotated}

    number_font = theme.numeral_font(round(scale * 0.34))
    radius = round(scale * 0.08)
    for number, (p, (x0, y0, x1, y1)) in enumerate(zip(spread.positions, boxes), start=1):
        rect = [
            offset_x + x0 * scale,
            offset_y + y0 * scale,
            offset_x + x1 * scale,
            offset_y + y1 * scale,
        ]
        # Opaque fill so a crossing card cleanly overlays the card beneath it.
        draw.rounded_rectangle(
            rect,
            radius=radius,
            fill=theme.tint if theme.ornaments else "white",
            outline=theme.accent if theme.ornaments else theme.ink,
            width=max(3, fmt.px(0.012)),
        )
        inset = scale * 0.07
        inner = [rect[0] + inset, rect[1] + inset, rect[2] - inset, rect[3] - inset]
        draw.rounded_rectangle(
            inner, radius=max(1, radius - round(inset)), outline=theme.grid, width=2
        )
        cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        covered = not p.rotated and (p.x, p.y) in crossed
        if theme.ornaments and not covered:
            # A card-back motif: stars in the inner border's corners and a
            # white medallion behind the number.
            star = scale * 0.16
            for sx, sy in (
                (inner[0] + star * 0.8, inner[1] + star * 0.8),
                (inner[2] - star * 0.8, inner[1] + star * 0.8),
                (inner[0] + star * 0.8, inner[3] - star * 0.8),
                (inner[2] - star * 0.8, inner[3] - star * 0.8),
            ):
                paste_center(page, sparkle(star, theme.grid), sx, sy)
            medallion = scale * 0.3
            draw.ellipse(
                [cx - medallion, cy - medallion, cx + medallion, cy + medallion],
                fill="white",
                outline=theme.accent,
                width=max(2, fmt.px(0.006)),
            )
        number_color = theme.accent if theme.ornaments else theme.ink
        if covered:
            strip_font = theme.numeral_font(round(scale * 0.22))
            draw.text(
                (cx, rect[1] + scale * 0.2),
                str(number),
                font=strip_font,
                fill=number_color,
                anchor="mm",
            )
        else:
            draw.text((cx, cy), str(number), font=number_font, fill=number_color, anchor="mm")
        if inline_labels:
            ly = rect[3] + label_font.size * 0.5
            for line in wrap_paragraph(p.label, label_font, scale * 1.3)[:2]:
                draw.text((cx, ly), line, font=label_font, fill=theme.ink, anchor="ma")
                ly += label_font.size * 1.2
    return span_y * scale + label_reserve


def render_spread_page(
    spread: Spread, fmt: PageFormat, page_number: int = 1, theme: Theme = PLAIN
) -> Image.Image:
    page, box = start_page(fmt, theme, page_number)
    draw = ImageDraw.Draw(page)
    y = draw_header(page, fmt, theme, box, spread.name, spread.description, title_size_in=0.34)
    y += fmt.px(0.16)

    field_font = theme.body_font(fmt.px(0.12))
    gap = fmt.px(0.25)
    field_w = (box.width - 2 * gap) / 3
    for i, label in enumerate(["Date", "Moon Phase", "Deck"]):
        _draw_field(draw, theme, box.left + i * (field_w + gap), y, field_w, label, field_font)
    y += fmt.px(0.45)
    _draw_field(draw, theme, box.left, y, box.width, "Question", field_font)
    y += fmt.px(0.38)
    _rule(draw, box.left, box.right, y + 4, theme.grid)
    y += fmt.px(0.2)

    n = len(spread.positions)
    key_font = theme.body_font(fmt.px(0.115))
    key_row_h = fmt.px(0.34)
    key_cols = 2 if n > 5 else 1
    key_rows = -(-n // key_cols)
    key_h = fmt.px(0.4) + key_rows * key_row_h
    reflection_min_h = fmt.px(2.4)
    diagram_max_h = min(box.height * 0.4, box.bottom - y - key_h - reflection_min_h)
    y += fmt.px(0.1)
    y += _draw_diagram(page, theme, spread, fmt, box.left, y, box.width, diagram_max_h)
    y += fmt.px(0.3)

    section_font = theme.heading_font(fmt.px(0.15))
    draw.text((box.left, y), "Cards Drawn", font=section_font, fill=theme.accent, anchor="la")
    y += fmt.px(0.36)
    col_gap = fmt.px(0.3)
    col_w = (box.width - col_gap * (key_cols - 1)) / key_cols
    for i, p in enumerate(spread.positions):
        col, row = divmod(i, key_rows)
        x = box.left + col * (col_w + col_gap)
        baseline = y + row * key_row_h + key_font.size
        _draw_field(draw, theme, x, baseline, col_w, f"{i + 1}. {p.label}:", key_font)
    y += key_rows * key_row_h + fmt.px(0.2)

    draw.text((box.left, y), "Reflections", font=section_font, fill=theme.accent, anchor="la")
    line_y = y + fmt.px(0.55)
    while line_y <= box.bottom:
        _rule(draw, box.left, box.right, line_y, theme.rule)
        line_y += fmt.px(0.34)
    return page


def build_tarot_pages(
    spread_keys: list[str],
    fmt: PageFormat,
    count: int = 1,
    title: str | None = None,
    subtitle: str | None = None,
    author: str | None = None,
    intro_text: str | None = None,
    theme: Theme = PLAIN,
) -> tuple[list[Image.Image], list[str]]:
    """`count` copies of the given spreads, cycled in order (so
    ["daily", "three_card"] with count=2 gives daily, three, daily, three).
    In KDP format this becomes a journal book with front matter."""
    unknown = [k for k in spread_keys if k not in SPREADS]
    if unknown:
        raise ValueError(
            f"Unknown spread(s): {', '.join(unknown)}. Choose from: {', '.join(SPREADS)}"
        )
    warnings: list[str] = []
    pages: list[Image.Image] = []
    is_book = fmt is KDP_BOOK
    book_title = title or "Tarot Journal"
    if is_book:
        theme = theme.grayscale()  # KDP black-and-white interior

    if is_book:
        if theme.ornaments:
            pages.append(render_themed_title_page(fmt, theme, book_title, subtitle, author, 1))
        else:
            pages.append(bookparts.render_title_page(book_title, author, 1, subtitle=subtitle))
        pages.append(
            bookparts.render_copyright_page(book_title, author, date.today().year, 2, note=None)
        )
        if intro_text:
            pages += bookparts.render_text_pages(intro_text, len(pages) + 1)
        bookparts._force_recto(pages, len(pages) + 1)

    for _ in range(count):
        for key in spread_keys:
            pages.append(render_spread_page(SPREADS[key], fmt, len(pages) + 1, theme))

    if is_book:
        if len(pages) % 2 == 1:
            pages.append(fmt.new_page())
        if len(pages) < MIN_KDP_PAGES:
            warnings.append(
                f"Book is {len(pages)} page(s); KDP paperback requires at least {MIN_KDP_PAGES}. "
                "Raise --count to add more spread pages."
            )
    stamp_page_numbers(pages, fmt)
    return pages, warnings

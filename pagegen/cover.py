"""KDP paperback wraparound covers: back cover, spine and front cover in one
image with bleed, built around front-cover art from any source.

The art supplies the front cover's picture; this module handles everything
KDP is strict about -- the exact canvas size for the page count and paper,
bleed, the spine (and whether it may carry text), the clear barcode area on
the back -- and sets the title, subtitle, author and back-cover blurb in the
theme's fonts, since AI image tools still garble lettering.
"""

from __future__ import annotations

import re
import statistics
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .fonts import wrap_paragraph
from .layout import DPI, KDP_BOOK
from .ornaments import divider, paste_center, star_scatter, triple_moon
from .theme import CELESTIAL, Theme

BLEED_IN = 0.125
# KDP spine width per page by paper type (from KDP's cover calculator).
SPINE_IN_PER_PAGE = {"white": 0.002252, "cream": 0.0025}
# KDP only allows spine text on books with at least this many pages, and it
# must stay this far from each spine edge.
MIN_PAGES_FOR_SPINE_TEXT = 79
SPINE_TEXT_CLEARANCE_IN = 0.0625
# Narrower than this after clearance and spine text would be under ~5pt.
MIN_SPINE_TEXT_IN = 0.07
MIN_PAGES = 24
# Text keeps at least this far inside the trim (KDP's minimum is 0.125in).
SAFE_IN = 0.5
# KDP prints the ISBN barcode in a 2 x 1.2in box at the back cover's
# bottom-right corner, 0.25in from the trim.
BARCODE_W_IN = 2.0
BARCODE_H_IN = 1.2
BARCODE_INSET_IN = 0.25

GOLD = "#e6c57f"
BLURB_TEXT = "#efe7f3"
SHADOW = (12, 6, 20)


@dataclass(frozen=True)
class CoverGeometry:
    trim_w_in: float
    trim_h_in: float
    spine_in: float
    dpi: int = DPI

    def px(self, inches: float) -> int:
        return round(inches * self.dpi)

    @property
    def width_px(self) -> int:
        return self.px(2 * BLEED_IN + 2 * self.trim_w_in + self.spine_in)

    @property
    def height_px(self) -> int:
        return self.px(2 * BLEED_IN + self.trim_h_in)

    @property
    def spine_left(self) -> int:
        return self.px(BLEED_IN + self.trim_w_in)

    @property
    def spine_right(self) -> int:
        return self.px(BLEED_IN + self.trim_w_in + self.spine_in)

    @property
    def trim_top(self) -> int:
        return self.px(BLEED_IN)

    @property
    def trim_bottom(self) -> int:
        return self.height_px - self.px(BLEED_IN)

    @property
    def back_box(self) -> tuple[int, int, int, int]:
        """Back cover trim box (left, top, right, bottom)."""
        return self.px(BLEED_IN), self.trim_top, self.spine_left, self.trim_bottom

    @property
    def front_box(self) -> tuple[int, int, int, int]:
        """Front cover trim box (left, top, right, bottom)."""
        return self.spine_right, self.trim_top, self.width_px - self.px(BLEED_IN), self.trim_bottom

    @property
    def barcode_box(self) -> tuple[int, int, int, int]:
        _, _, right, bottom = self.back_box
        inset = self.px(BARCODE_INSET_IN)
        return (
            right - inset - self.px(BARCODE_W_IN),
            bottom - inset - self.px(BARCODE_H_IN),
            right - inset,
            bottom - inset,
        )


def spine_width_in(pages: int, paper: str = "white") -> float:
    return pages * SPINE_IN_PER_PAGE[paper]


def count_pdf_pages(path: str | Path) -> int:
    """Page count of a PDF (enough for the simple PDFs Pillow writes, and
    most others) without a PDF library dependency."""
    data = Path(path).read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))


# --------------------------------------------------------------------------
# Drawing helpers


def _font_fit(theme: Theme, text: str, max_w: float, start: int, minimum: int, kind="display"):
    loader = theme.display_font if kind == "display" else theme.heading_font
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    size = start
    font = loader(size)
    while draw.textlength(text, font=font) > max_w and size > minimum:
        size = round(size * 0.95)
        font = loader(size)
    return font


def _shadowed_text(
    canvas: Image.Image,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
    anchor: str,
    glow: float = 0.06,
) -> None:
    """Draws text over a soft dark glow so it stays legible on busy art."""
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=font, fill=255, anchor=anchor, stroke_width=4)
    radius = max(4, round(font.size * glow))
    mask = mask.filter(ImageFilter.GaussianBlur(radius))
    mask = mask.point(lambda v: min(255, int(v * 1.6)))
    canvas.paste(Image.new("RGB", canvas.size, SHADOW), (0, 0), mask)
    ImageDraw.Draw(canvas).text(xy, text, font=font, fill=fill, anchor=anchor)


def _balanced_lines(text: str, lines: int) -> list[str]:
    words = text.split()
    if lines <= 1 or len(words) < 2:
        return [text]
    target = len(text) / lines
    best, best_score = [text], float("inf")
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = abs(len(a) - target) + abs(len(b) - target)
        if score < best_score:
            best, best_score = [a, b], score
    return best


def _title_lines(theme, title: str, max_w: float, geo: CoverGeometry, size_in: float = 0.8):
    """One line if it fits large enough, else two balanced lines; a "|" in
    the title forces the break. size_in caps the title's font size."""
    start, minimum = geo.px(size_in), geo.px(0.36)
    if "|" in title:
        lines = [part.strip() for part in title.split("|")]
    else:
        lines = [title]
        font = _font_fit(theme, title, max_w, start, minimum)
        if font.size >= min(start, geo.px(0.62)):
            return lines, font
        lines = _balanced_lines(title, 2)
    longest = max(lines, key=len)
    font = _font_fit(theme, longest, max_w, start, minimum)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    while any(draw.textlength(line, font=font) > max_w for line in lines) and font.size > minimum:
        font = theme.display_font(round(font.size * 0.95))
    return lines, font


def _edge_color(art: Image.Image) -> tuple[int, int, int]:
    """Median color of the art's outer border -- the background for the
    back cover and spine, so they match the front."""
    small = art.convert("RGB").resize((200, round(200 * art.height / art.width)))
    w, h = small.size
    border = [small.getpixel((x, y)) for x in range(w) for y in (2, h - 3)]
    border += [small.getpixel((x, y)) for y in range(h) for x in (2, w - 3)]
    return tuple(round(statistics.median(p[i] for p in border)) for i in range(3))


def _place_art(canvas: Image.Image, art: Image.Image, geo: CoverGeometry, scale: float) -> None:
    """Fills the front panel (trim plus top/right/bottom bleed) with the art,
    centered on the front trim. scale < 1 shrinks the art so a border drawn
    near its edge moves inside the trim's safe zone; the gap is filled with
    the art's own edge color and the art's edge is feathered into it."""
    left, _, right, _ = geo.front_box
    region_w = canvas.width - left
    region_h = canvas.height
    cx = (left + right) / 2 - left  # front trim center, within the region
    cy = region_h / 2

    # Size the art so it covers the front trim + bleed at scale 1.
    base = max((right - left + 2 * geo.px(BLEED_IN)) / art.width, region_h / art.height)
    art_w, art_h = round(art.width * base * scale), round(art.height * base * scale)
    sharp = art.convert("RGB").resize((art_w, art_h), Image.LANCZOS)

    region = Image.new("RGB", (region_w, region_h), _edge_color(art))
    ax, ay = round(cx - art_w / 2), round(cy - art_h / 2)
    if scale < 1:
        feather = geo.px(0.08)
        mask = Image.new("L", (art_w, art_h), 0)
        ImageDraw.Draw(mask).rectangle(
            [feather, feather, art_w - feather, art_h - feather], fill=255
        )
        mask = mask.filter(ImageFilter.GaussianBlur(feather / 2))
        region.paste(sharp, (ax, ay), mask)
    else:
        region.paste(sharp, (ax, ay))
    canvas.paste(region, (left, 0))


def _draw_front_text(
    canvas: Image.Image,
    geo: CoverGeometry,
    theme: Theme,
    title: str,
    subtitle: str | None,
    author: str | None,
    title_top_in: float,
    author_bottom_in: float,
    title_size_in: float,
) -> None:
    left, top, right, bottom = geo.front_box
    cx = (left + right) / 2
    max_w = (right - left) * 0.72
    lines, font = _title_lines(theme, title, max_w, geo, title_size_in)
    y = top + geo.px(title_top_in)
    for line in lines:
        _shadowed_text(canvas, (cx, y), line, font, GOLD, "ma")
        y += round(font.size * 1.12)
    y += geo.px(0.08)
    gold_theme = _gold(theme)
    if theme.ornaments:
        divider(canvas, KDP_BOOK, gold_theme, cx, y + geo.px(0.06), (right - left) * 0.42)
        y += geo.px(0.25)
    if subtitle:
        sub_font = theme.italic_font(geo.px(0.24))
        for line in wrap_paragraph(subtitle, sub_font, max_w):
            _shadowed_text(canvas, (cx, y), line, sub_font, BLURB_TEXT, "ma")
            y += round(sub_font.size * 1.3)
    if author:
        author_font = _font_fit(theme, author, max_w, geo.px(0.26), geo.px(0.14), kind="heading")
        _shadowed_text(
            canvas,
            (cx, bottom - geo.px(author_bottom_in)),
            author,
            author_font,
            GOLD,
            "ms",
        )


def _gold(theme: Theme) -> Theme:
    from dataclasses import replace

    return replace(theme, accent=GOLD)


def _draw_back(
    canvas: Image.Image,
    geo: CoverGeometry,
    theme: Theme,
    title: str,
    blurb: str | None,
    seed: int,
) -> None:
    left, top, right, bottom = geo.back_box
    star_scatter(canvas, (0, 0, geo.spine_left, geo.height_px), KDP_BOOK, "#b49a6a", seed, 1.2)
    safe = geo.px(SAFE_IN)
    barcode_top = geo.barcode_box[1]
    # Lay the text out on a transparent layer first, then center the block
    # vertically in the space above the barcode area.
    layer = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx = layer.width / 2
    max_w = layer.width - 2 * geo.px(0.8)
    y = 0

    heading = _font_fit(theme, title.replace("|", " "), max_w, geo.px(0.36), geo.px(0.2))
    for line in _balanced_lines(title.replace("|", " "), 1):
        draw.text((cx, y), line, font=heading, fill=GOLD, anchor="ma")
        y += round(heading.size * 1.2)
    if theme.ornaments:
        divider(layer, KDP_BOOK, _gold(theme), cx, y + geo.px(0.1), layer.width * 0.4)
    y += geo.px(0.45)

    if blurb:
        body = theme.body_font(geo.px(0.17))
        line_h = round(body.size * 1.4)
        for para in [p.strip() for p in re.split(r"\n\s*\n", blurb) if p.strip()]:
            if para.startswith(("- ", "* ", "• ")):
                items = [i.lstrip("-*• ").strip() for i in para.splitlines() if i.strip()]
                for item in items:
                    star = geo.px(0.1)
                    wrapped = wrap_paragraph(item, body, max_w - geo.px(0.35))
                    paste_center(
                        layer,
                        _sparkle(star),
                        cx - max_w / 2 + star / 2,
                        y + body.size * 0.55,
                    )
                    for line in wrapped:
                        draw.text(
                            (cx - max_w / 2 + geo.px(0.3), y),
                            line,
                            font=body,
                            fill=BLURB_TEXT,
                            anchor="la",
                        )
                        y += line_h
                    y += round(line_h * 0.15)
            else:
                for line in wrap_paragraph(para, body, max_w):
                    draw.text((cx, y), line, font=body, fill=BLURB_TEXT, anchor="ma")
                    y += line_h
            y += round(line_h * 0.6)
    space_top, space_bottom = top + safe, barcode_top - geo.px(0.3)
    if y > space_bottom - space_top:
        raise ValueError("Back-cover blurb is too long: it runs into the barcode area. Shorten it.")
    # Center slightly above the middle -- optically centered.
    offset = space_top + round((space_bottom - space_top - y) * 0.42)
    canvas.paste(layer, (left, offset), layer)
    if theme.ornaments:
        emblem = triple_moon(geo.px(0.28), GOLD)
        paste_center(canvas, emblem, left + safe + emblem.width / 2, bottom - safe - emblem.height)


def _sparkle(size: int) -> Image.Image:
    from .ornaments import sparkle

    return sparkle(size, GOLD)


def _draw_spine(
    canvas: Image.Image, geo: CoverGeometry, theme: Theme, pages: int, title, author
) -> str | None:
    """Spine text, rotated to read top-to-bottom. Returns why it was left
    off, or None if it was drawn."""
    if pages < MIN_PAGES_FOR_SPINE_TEXT:
        return (
            f"No spine text: KDP allows it only on books with {MIN_PAGES_FOR_SPINE_TEXT}+ "
            f"pages (this one has {pages}; spine {geo.spine_in:.3f}in)."
        )
    usable = geo.px(geo.spine_in - 2 * SPINE_TEXT_CLEARANCE_IN)
    if usable < geo.px(MIN_SPINE_TEXT_IN):
        return (
            f"No spine text: the {geo.spine_in:.3f}in spine leaves too little room for legible "
            f"text after KDP's {SPINE_TEXT_CLEARANCE_IN}in clearance on each side "
            "(roughly 100+ pages needed)."
        )
    text = title.replace("|", " ") + (f"   ·   {author}" if author else "")
    length = geo.trim_bottom - geo.trim_top - 2 * geo.px(0.5)
    size = min(round(usable * 0.75), geo.px(0.3))
    font = _font_fit(theme, text, length, size, 8, kind="heading")
    strip = Image.new("RGBA", (round(length), usable), (0, 0, 0, 0))
    ImageDraw.Draw(strip).text((length / 2, usable / 2), text, font=font, fill=GOLD, anchor="mm")
    strip = strip.rotate(-90, expand=True)
    paste_center(canvas, strip, (geo.spine_left + geo.spine_right) / 2, geo.height_px / 2)
    return None


def _draw_guides(canvas: Image.Image, geo: CoverGeometry) -> None:
    """Proofing overlay: trim (cyan), text safe zone (magenta), spine
    (yellow) and the barcode area (white box)."""
    draw = ImageDraw.Draw(canvas)
    w = 3
    b = geo.px(BLEED_IN)
    draw.rectangle([b, b, canvas.width - b, canvas.height - b], outline="cyan", width=w)
    for box in (geo.back_box, geo.front_box):
        s = geo.px(SAFE_IN)
        draw.rectangle([box[0] + s, box[1] + s, box[2] - s, box[3] - s], outline="magenta", width=w)
    for x in (geo.spine_left, geo.spine_right):
        draw.line([(x, 0), (x, canvas.height)], fill="yellow", width=w)
    draw.rectangle(geo.barcode_box, outline="white", width=w)


# --------------------------------------------------------------------------


def build_cover(
    art_path: str | Path,
    pages: int,
    title: str,
    subtitle: str | None = None,
    author: str | None = None,
    blurb: str | None = None,
    paper: str = "white",
    theme: Theme = CELESTIAL,
    art_scale: float = 1.0,
    title_top_in: float = 0.75,
    author_bottom_in: float = 0.75,
    title_size_in: float = 0.8,
    guides: bool = False,
) -> tuple[Image.Image, list[str]]:
    """Returns the full wraparound cover image and any warnings."""
    if pages < MIN_PAGES:
        raise ValueError(f"KDP paperbacks need at least {MIN_PAGES} pages (got {pages}).")
    if paper not in SPINE_IN_PER_PAGE:
        raise ValueError(f"paper must be one of: {', '.join(SPINE_IN_PER_PAGE)}")
    warnings: list[str] = []
    art = Image.open(art_path)
    art.load()

    geo = CoverGeometry(KDP_BOOK.width_in, KDP_BOOK.height_in, spine_width_in(pages, paper))
    front_w = geo.px(KDP_BOOK.width_in + 2 * BLEED_IN)
    effective_dpi = min(art.width / (front_w / DPI), art.height / (geo.height_px / DPI))
    if effective_dpi < 290:
        warnings.append(
            f"Art is {art.width}x{art.height}px, about {effective_dpi:.0f} DPI on the front "
            f"cover; KDP wants 300 DPI ({front_w}x{geo.height_px}px). Upscale it first."
        )
    art_ratio = art.width / art.height
    front_ratio = front_w / geo.height_px
    if abs(art_ratio - front_ratio) / front_ratio > 0.03:
        warnings.append(
            f"Art aspect ratio {art_ratio:.3f} differs from the front cover's {front_ratio:.3f}; "
            "its edges will be cropped."
        )

    canvas = Image.new("RGB", (geo.width_px, geo.height_px), _edge_color(art))
    _place_art(canvas, art, geo, art_scale)
    _draw_front_text(
        canvas, geo, theme, title, subtitle, author, title_top_in, author_bottom_in, title_size_in
    )
    _draw_back(canvas, geo, theme, title, blurb, seed=pages)
    spine_problem = _draw_spine(canvas, geo, theme, pages, title, author)
    if spine_problem:
        warnings.append(spine_problem)
    if guides:
        _draw_guides(canvas, geo)
    return canvas, warnings


def describe(pages: int, paper: str) -> str:
    geo = CoverGeometry(KDP_BOOK.width_in, KDP_BOOK.height_in, spine_width_in(pages, paper))
    return textwrap.dedent(
        f"""\
        {pages} pages on {paper} paper: spine {geo.spine_in:.3f}in;
        full cover {geo.width_px / DPI:.3f} x {geo.height_px / DPI:.3f}in
        ({geo.width_px} x {geo.height_px}px at {DPI} DPI)"""
    )

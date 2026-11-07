"""Paper formats shared by every page type.

A page type draws onto whatever `PageFormat` it's handed, so the same tarot
spread or moon calendar can come out as a KDP book interior (mirrored gutter
margins, page numbers) or as an Etsy-style home-printable PDF (even margins,
US Letter or A4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from .fonts import load_body_font

DPI = 300


@dataclass(frozen=True)
class Box:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2


@dataclass(frozen=True)
class PageFormat:
    name: str
    width_in: float
    height_in: float
    margin_inside_in: float
    margin_outside_in: float
    margin_top_in: float
    margin_bottom_in: float
    # Book interiors swap the inside (gutter) margin to whichever side faces
    # the spine; loose printables use the same margins on every page.
    mirrored: bool
    page_numbers: bool
    dpi: int = DPI

    @property
    def width_px(self) -> int:
        return round(self.width_in * self.dpi)

    @property
    def height_px(self) -> int:
        return round(self.height_in * self.dpi)

    def px(self, inches: float) -> int:
        return round(inches * self.dpi)

    def margins(self, page_number: int = 1) -> tuple[int, int, int, int]:
        """(left, right, top, bottom) in pixels. Odd pages are recto
        (right-hand), so their inside margin is on the left."""
        inside = self.px(self.margin_inside_in)
        outside = self.px(self.margin_outside_in)
        top = self.px(self.margin_top_in)
        bottom = self.px(self.margin_bottom_in)
        if not self.mirrored or page_number % 2 == 1:
            return inside, outside, top, bottom
        return outside, inside, top, bottom

    def content_box(self, page_number: int = 1) -> Box:
        left, right, top, bottom = self.margins(page_number)
        return Box(left, top, self.width_px - right, self.height_px - bottom)

    def new_page(self) -> Image.Image:
        return Image.new("RGB", (self.width_px, self.height_px), "white")


# KDP paperback interior, 8.5x11in, no bleed. The 1.0in gutter comfortably
# covers books up to a few hundred pages.
KDP_BOOK = PageFormat(
    name="kdp",
    width_in=8.5,
    height_in=11.0,
    margin_inside_in=1.0,
    margin_outside_in=0.75,
    margin_top_in=0.75,
    margin_bottom_in=0.85,
    mirrored=True,
    page_numbers=True,
)

# Home-printable downloads. 0.5in keeps everything clear of the unprintable
# edge on typical inkjet/laser printers.
LETTER = PageFormat(
    name="letter",
    width_in=8.5,
    height_in=11.0,
    margin_inside_in=0.5,
    margin_outside_in=0.5,
    margin_top_in=0.5,
    margin_bottom_in=0.5,
    mirrored=False,
    page_numbers=False,
)

A4 = PageFormat(
    name="a4",
    width_in=210 / 25.4,
    height_in=297 / 25.4,
    margin_inside_in=0.5,
    margin_outside_in=0.5,
    margin_top_in=0.5,
    margin_bottom_in=0.5,
    mirrored=False,
    page_numbers=False,
)

PAPER_FORMATS: dict[str, PageFormat] = {f.name: f for f in (KDP_BOOK, LETTER, A4)}

PAGE_NUMBER_SIZE = 30
MIN_KDP_PAGES = 24


def stamp_page_numbers(pages: list[Image.Image], fmt: PageFormat) -> None:
    if not fmt.page_numbers:
        return
    font = load_body_font(PAGE_NUMBER_SIZE)
    for number, img in enumerate(pages, start=1):
        ImageDraw.Draw(img).text(
            (fmt.width_px / 2, fmt.height_px - fmt.px(0.4)),
            str(number),
            font=font,
            fill="black",
            anchor="ma",
        )


def save_pdf(
    pages: list[Image.Image], path: str | Path, dpi: int = DPI, quality: int | None = None
) -> None:
    """Pillow embeds RGB/grayscale pages as JPEG; `quality` (1-95) raises it
    above Pillow's default of 75 -- worth it for photographic cover art."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    extra = {"quality": quality} if quality is not None else {}
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=dpi, **extra)


def output_path_for(base: str | Path, fmt: PageFormat, multiple: bool) -> Path:
    """When one run writes several paper sizes, suffix each file with its
    format name (`moon_2027.pdf` -> `moon_2027_letter.pdf`, `..._a4.pdf`)."""
    base = Path(base)
    if base.suffix.lower() != ".pdf":
        base = base.with_suffix(".pdf")
    if not multiple:
        return base
    return base.with_name(f"{base.stem}_{fmt.name}{base.suffix}")

"""Visual themes: the fonts, colors and decoration a page type draws with.

A page renderer takes a `Theme` and asks it for fonts and colors instead of
hard-coding them, so the same moon calendar can come out plain (system
fonts, no ornaments) or as a `celestial` grimoire-style page (Cinzel
headings, Garamond body text, a framed page with moon and star ornaments).

Bundled fonts are SIL Open Font License (see pagegen/assets/fonts/OFL-*.txt),
which allows embedding them in commercial PDFs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from .fonts import load_body_font, load_font, load_heading_font, load_italic_font

FONT_DIR = Path(__file__).parent / "assets" / "fonts"


@lru_cache(maxsize=256)
def _bundled_font(filename: str, size: int, weight: int | None) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT_DIR / filename), max(1, size))
    if weight is not None:
        try:
            font.set_variation_by_axes([weight])
        except (OSError, AttributeError):
            pass  # FreeType built without variation support: default weight
    return font


@dataclass(frozen=True)
class FontSpec:
    """A bundled font file (optionally a variable font at a given weight),
    or None to fall back to the plain system loader."""

    filename: str | None = None
    weight: int | None = None


@dataclass(frozen=True)
class Theme:
    name: str
    # Big page titles ("January 2027"); headings (section titles, labels);
    # body (lists, fields); italic (subtitles, prompts); numerals (day numbers).
    display: FontSpec
    heading: FontSpec
    body: FontSpec
    italic: FontSpec
    numerals: FontSpec
    ink: str = "#1f1f1f"
    soft: str = "#4a4a4a"  # secondary text
    rule: str = "#b5b5b5"  # writing lines
    grid: str = "#8a8a8a"  # table/grid lines
    accent: str = "#555555"  # titles, ornaments, frame
    tint: str = "#f2f2f2"  # light background fills
    moon_dark: str = "#2e2e2e"
    # Decoration
    frame: bool = False
    ornaments: bool = False
    # Garamond's small x-height reads smaller than DejaVu at the same point
    # size, so body text is scaled up to keep the same legibility.
    body_scale: float = 1.0

    def _load(self, spec: FontSpec, size: int, fallback) -> ImageFont.ImageFont:
        if spec.filename is None:
            return fallback(size)
        try:
            return _bundled_font(spec.filename, size, spec.weight)
        except OSError:
            return fallback(size)

    def display_font(self, size: int) -> ImageFont.ImageFont:
        return self._load(self.display, size, load_heading_font)

    def heading_font(self, size: int) -> ImageFont.ImageFont:
        return self._load(self.heading, size, load_heading_font)

    def body_font(self, size: int) -> ImageFont.ImageFont:
        return self._load(self.body, round(size * self.body_scale), load_body_font)

    def italic_font(self, size: int) -> ImageFont.ImageFont:
        return self._load(self.italic, round(size * self.body_scale), load_italic_font)

    def numeral_font(self, size: int) -> ImageFont.ImageFont:
        return self._load(self.numerals, size, load_font)

    def grayscale(self) -> Theme:
        """The same theme with every color converted to gray -- for KDP's
        black-and-white interiors and 'printer-friendly' downloads."""

        def gray(color: str) -> str:
            r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
            v = round(0.299 * r + 0.587 * g + 0.114 * b)
            return f"#{v:02x}{v:02x}{v:02x}"

        return replace(
            self,
            ink=gray(self.ink),
            soft=gray(self.soft),
            rule=gray(self.rule),
            grid=gray(self.grid),
            accent=gray(self.accent),
            tint=gray(self.tint),
            moon_dark=gray(self.moon_dark),
        )


PLAIN = Theme(
    name="plain",
    display=FontSpec(),
    heading=FontSpec(),
    body=FontSpec(),
    italic=FontSpec(),
    numerals=FontSpec(),
)

CELESTIAL = Theme(
    name="celestial",
    display=FontSpec("Cinzel-Variable.ttf", 700),
    heading=FontSpec("Cinzel-Variable.ttf", 600),
    body=FontSpec("EBGaramond-Variable.ttf", 450),
    italic=FontSpec("EBGaramond-Italic-Variable.ttf", 450),
    numerals=FontSpec("Cinzel-Variable.ttf", 600),
    ink="#231b2e",
    soft="#54485f",
    rule="#bdb4c4",
    grid="#8c7f99",
    accent="#4b2f63",  # deep plum
    tint="#f1edf4",
    moon_dark="#3b3049",
    frame=True,
    ornaments=True,
    body_scale=1.15,
)

THEMES: dict[str, Theme] = {t.name: t for t in (PLAIN, CELESTIAL)}
DEFAULT_THEME = "celestial"


def resolve_theme(name: str, grayscale: bool) -> Theme:
    theme = THEMES[name]
    return theme.grayscale() if grayscale else theme

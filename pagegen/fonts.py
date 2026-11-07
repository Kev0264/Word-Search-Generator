"""Font loading and text-wrapping helpers shared by every page type."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


def _first_available(names: tuple[str, ...], size: int) -> ImageFont.ImageFont | None:
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return None


def load_font(size: int) -> ImageFont.ImageFont:
    """Bold sans -- used for grid letters and other bold emphasis."""
    font = _first_available(("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"), size)
    return font or ImageFont.load_default()


def load_heading_font(size: int) -> ImageFont.ImageFont:
    """Bold serif -- used for titles/headings, distinct from body text and
    grid letters so the page reads with real typographic hierarchy."""
    font = _first_available(
        ("DejaVuSerif-Bold.ttf", "Georgia Bold.ttf", "Times New Roman Bold.ttf"), size
    )
    return font or load_font(size)


def load_body_font(size: int) -> ImageFont.ImageFont:
    """Regular-weight sans -- used for paragraphs and word lists, so not
    every line on the page is shouting in bold."""
    font = _first_available(("DejaVuSans.ttf", "Arial.ttf", "arial.ttf"), size)
    return font or load_font(size)


def load_italic_font(size: int) -> ImageFont.ImageFont:
    """Italic sans -- used for small callouts like a trivia blurb."""
    font = _first_available(("DejaVuSans-Oblique.ttf", "Arial Italic.ttf", "ariali.ttf"), size)
    return font or load_body_font(size)


def wrap_words_by_pixel(words: list[str], font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """Greedily packs words onto lines (three spaces apart) so that no
    rendered line exceeds max_width pixels for the given font."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = "   ".join(current + [word])
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append("   ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append("   ".join(current))
    return lines


def wrap_paragraph(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """Wraps prose on single spaces so no line exceeds max_width pixels."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    current: list[str] = []
    for word in text.split():
        candidate = " ".join(current + [word])
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [""]

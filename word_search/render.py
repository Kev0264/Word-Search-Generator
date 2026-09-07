from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .grid import WordSearchGenerator

MARGIN = 40
TITLE_HEIGHT = 50
CIRCLE_WIDTH_RATIO = 0.09
CIRCLE_RADIUS_RATIO = 0.46
GRID_LINE_COLOR = "#999999"

# Distinct colors cycled per placed word so that unrelated words which happen
# to cross near each other (e.g. two diagonals sharing a row) are visually
# distinguishable, and so that two words sharing a letter both stay visible
# as overlapping outlines rather than one word's fill covering the other's.
HIGHLIGHT_PALETTE = [
    "#ffd166",
    "#ef476f",
    "#06d6a0",
    "#118ab2",
    "#c77dff",
    "#f4a261",
    "#83c5be",
    "#e76f51",
    "#adc178",
    "#a0c4ff",
    "#ff99c8",
    "#bde0fe",
]


def load_font(size: int) -> ImageFont.ImageFont:
    """Bold sans -- used for grid letters and other bold emphasis."""
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_heading_font(size: int) -> ImageFont.ImageFont:
    """Bold serif -- used for titles/headings, distinct from body text and
    grid letters so the page reads with real typographic hierarchy."""
    for name in ("DejaVuSerif-Bold.ttf", "Georgia Bold.ttf", "Times New Roman Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return load_font(size)


def load_body_font(size: int) -> ImageFont.ImageFont:
    """Regular-weight sans -- used for paragraphs and word lists, so not
    every line on the page is shouting in bold."""
    for name in ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return load_font(size)


def load_italic_font(size: int) -> ImageFont.ImageFont:
    """Italic sans -- used for small callouts like a trivia blurb."""
    for name in ("DejaVuSans-Oblique.ttf", "Arial Italic.ttf", "ariali.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return load_body_font(size)


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


class PuzzleRenderer:
    """Renders a WordSearchGenerator's grid to a PNG or PDF image."""

    def __init__(
        self,
        generator: WordSearchGenerator,
        title: str = "Word Search",
        cell_size: int = 40,
    ):
        self.generator = generator
        self.title = title
        self.cell_size = cell_size

    def save_puzzle(self, path: str | Path) -> None:
        self._save(self._render(with_answers=False), path)

    def save_answer_key(self, path: str | Path) -> None:
        self._save(self._render(with_answers=True), path)

    @staticmethod
    def _font(size: int) -> ImageFont.ImageFont:
        return load_font(size)

    def _wrap_word_list(self, width: int, font: ImageFont.ImageFont) -> list[str]:
        words = sorted(self.generator.display_words.values())
        return wrap_words_by_pixel(words, font, width - MARGIN * 2)

    def _word_list_height(self, width: int) -> int:
        lines = self._wrap_word_list(width, load_body_font(18))
        return 40 + len(lines) * 24

    def _render(self, with_answers: bool) -> Image.Image:
        rows, cols = self.generator.rows, self.generator.cols
        grid_w = cols * self.cell_size
        grid_h = rows * self.cell_size
        width = grid_w + MARGIN * 2
        word_list_h = self._word_list_height(width)
        height = TITLE_HEIGHT + grid_h + word_list_h + MARGIN * 2

        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)

        draw.text(
            (width / 2, MARGIN / 2),
            self.title,
            fill="black",
            font=load_heading_font(28),
            anchor="ma",
        )

        grid_top = TITLE_HEIGHT + MARGIN
        grid_left = MARGIN

        for r in range(rows + 1):
            y = grid_top + r * self.cell_size
            draw.line([(grid_left, y), (grid_left + grid_w, y)], fill=GRID_LINE_COLOR)
        for c in range(cols + 1):
            x = grid_left + c * self.cell_size
            draw.line([(x, grid_top), (x, grid_top + grid_h)], fill=GRID_LINE_COLOR)

        letter_font = self._font(int(self.cell_size * 0.55))
        for r in range(rows):
            for c in range(cols):
                cx = grid_left + c * self.cell_size + self.cell_size / 2
                cy = grid_top + r * self.cell_size + self.cell_size / 2
                draw.text(
                    (cx, cy),
                    self.generator.grid[r][c],
                    fill="black",
                    font=letter_font,
                    anchor="mm",
                )

        if with_answers:
            for i, placed in enumerate(self.generator.placements):
                color = HIGHLIGHT_PALETTE[i % len(HIGHLIGHT_PALETTE)]
                start = (
                    grid_left + placed.cells[0][1] * self.cell_size + self.cell_size / 2,
                    grid_top + placed.cells[0][0] * self.cell_size + self.cell_size / 2,
                )
                end = (
                    grid_left + placed.cells[-1][1] * self.cell_size + self.cell_size / 2,
                    grid_top + placed.cells[-1][0] * self.cell_size + self.cell_size / 2,
                )
                self._draw_word_circle(draw, start, end, color)

        self._draw_word_list(draw, grid_top + grid_h + MARGIN, width)
        return img

    def _draw_word_circle(
        self,
        draw: ImageDraw.ImageDraw,
        start: tuple[float, float],
        end: tuple[float, float],
        color: str,
    ) -> None:
        """Draws a stadium-shaped (pill) outline from the center of the first
        letter to the center of the last letter, circling the whole word."""
        radius = self.cell_size * CIRCLE_RADIUS_RATIO
        stroke = max(2, round(self.cell_size * CIRCLE_WIDTH_RATIO))

        sx, sy = start
        ex, ey = end
        angle = math.degrees(math.atan2(ey - sy, ex - sx))

        def offset(x: float, y: float, angle_deg: float, dist: float) -> tuple[float, float]:
            rad = math.radians(angle_deg)
            return (x + dist * math.cos(rad), y + dist * math.sin(rad))

        side_a_start = offset(sx, sy, angle + 90, radius)
        side_a_end = offset(ex, ey, angle + 90, radius)
        side_b_start = offset(sx, sy, angle - 90, radius)
        side_b_end = offset(ex, ey, angle - 90, radius)

        draw.line([side_a_start, side_a_end], fill=color, width=stroke)
        draw.line([side_b_start, side_b_end], fill=color, width=stroke)
        draw.arc(
            [sx - radius, sy - radius, sx + radius, sy + radius],
            angle + 90,
            angle + 270,
            fill=color,
            width=stroke,
        )
        draw.arc(
            [ex - radius, ey - radius, ex + radius, ey + radius],
            angle - 90,
            angle + 90,
            fill=color,
            width=stroke,
        )

    def _draw_word_list(self, draw: ImageDraw.ImageDraw, top: int, width: int) -> None:
        draw.text(
            (width / 2, top),
            "Find these words:",
            fill="black",
            font=load_heading_font(20),
            anchor="ma",
        )
        font = load_body_font(18)
        wrapped = self._wrap_word_list(width, font)
        y = top + 30
        for line in wrapped:
            draw.text((width / 2, y), line, fill="black", font=font, anchor="ma")
            y += 24

    @staticmethod
    def _save(img: Image.Image, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".pdf":
            img.save(path, "PDF", resolution=100.0)
        else:
            img.save(path)

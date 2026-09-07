from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .grid import WordSearchGenerator

MARGIN = 40
TITLE_HEIGHT = 50

# Distinct colors cycled per placed word so that unrelated words which happen
# to cross near each other (e.g. two diagonals sharing a row) are visually
# distinguishable instead of blending into one same-colored, misleading block.
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
        for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _word_list_height(self, width: int) -> int:
        text = "   ".join(sorted(self.generator.words))
        wrapped = textwrap.wrap(text, width=max(20, width // 11))
        return 40 + len(wrapped) * 24

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
            font=self._font(28),
            anchor="ma",
        )

        grid_top = TITLE_HEIGHT + MARGIN
        grid_left = MARGIN

        if with_answers:
            for i, placed in enumerate(self.generator.placements):
                color = HIGHLIGHT_PALETTE[i % len(HIGHLIGHT_PALETTE)]
                for r, c in placed.cells:
                    x0 = grid_left + c * self.cell_size
                    y0 = grid_top + r * self.cell_size
                    draw.rectangle(
                        [x0, y0, x0 + self.cell_size, y0 + self.cell_size],
                        fill=color,
                    )

        for r in range(rows + 1):
            y = grid_top + r * self.cell_size
            draw.line([(grid_left, y), (grid_left + grid_w, y)], fill="black")
        for c in range(cols + 1):
            x = grid_left + c * self.cell_size
            draw.line([(x, grid_top), (x, grid_top + grid_h)], fill="black")

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

        self._draw_word_list(draw, grid_top + grid_h + MARGIN, width)
        return img

    def _draw_word_list(self, draw: ImageDraw.ImageDraw, top: int, width: int) -> None:
        draw.text(
            (width / 2, top),
            "Find these words:",
            fill="black",
            font=self._font(20),
            anchor="ma",
        )
        text = "   ".join(sorted(self.generator.words))
        wrapped = textwrap.wrap(text, width=max(20, width // 11))
        font = self._font(18)
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

"""Line-art ornaments drawn in code: stars, crescents, a triple-moon divider,
page frames and star scatters.

Every shape is rendered as an anti-aliased alpha mask at 4x and downsampled,
then tinted with the theme color -- so ornaments stay crisp at 300 DPI, in
any color, with no image assets or art licensing to worry about.
"""

from __future__ import annotations

import math
import random
import zlib
from collections.abc import Callable

from PIL import Image, ImageDraw

from .layout import Box, PageFormat
from .theme import Theme

SUPERSAMPLE = 4

# The decorative frame sits this far outside the format's content box (in
# the margin), and page content is inset this far inside it.
FRAME_OUT_IN = 0.18
FRAME_IN_IN = 0.17


def _shape(
    width: int, height: int, color: str, painter: Callable[[ImageDraw.ImageDraw, int], None]
) -> Image.Image:
    """Runs painter(draw, ss) on a supersampled 'L' mask (255 = ink) and
    returns an RGBA image in `color` with that mask as its alpha."""
    width, height = max(1, round(width)), max(1, round(height))
    ss = SUPERSAMPLE
    mask = Image.new("L", (width * ss, height * ss), 0)
    painter(ImageDraw.Draw(mask), ss)
    mask = mask.resize((width, height), Image.LANCZOS)
    img = Image.new("RGBA", (width, height), color)
    img.putalpha(mask)
    return img


def paste_center(page: Image.Image, img: Image.Image, cx: float, cy: float) -> None:
    page.paste(img, (round(cx - img.width / 2), round(cy - img.height / 2)), img)


def knock_out(draw: ImageDraw.ImageDraw, cx: float, cy: float, rx: float, ry: float | None = None):
    """Clears a white ellipse so an ornament can sit on top of a line."""
    ry = rx if ry is None else ry
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill="white")


def sparkle(size: float, color: str, points: int = 4, inner: float = 0.22) -> Image.Image:
    """A star with concave sides -- 4 points for a twinkle, 8 for a
    compass-rose style burst (alternating long and short rays)."""

    def paint(draw, ss):
        s = size * ss
        c = s / 2
        poly = []
        rays = points * 2
        for i in range(rays * 6):
            t = i / (rays * 6)
            angle = 2 * math.pi * t - math.pi / 2
            # Smooth concave falloff between ray tips.
            phase = (t * rays) % 2
            frac = abs(phase - 1)  # 1 at a ray tip, 0 between
            tip = c if points == 4 or (round(t * rays) // 2) % 2 == 0 else c * 0.55
            r = c * inner + (tip - c * inner) * frac**2.2
            poly.append((c + r * math.cos(angle), c + r * math.sin(angle)))
        draw.polygon(poly, fill=255)

    return _shape(size, size, color, paint)


def dot(size: float, color: str) -> Image.Image:
    return _shape(
        size, size, color, lambda d, ss: d.ellipse([0, 0, size * ss - 1, size * ss - 1], fill=255)
    )


def crescent(size: float, color: str, opens: str = "left", thickness: float = 0.38) -> Image.Image:
    """A crescent moon. opens='left' gives a waxing ☽-style crescent (lit
    edge on the right, horns pointing left); 'right' gives the waning ☾."""

    def paint(draw, ss):
        s = size * ss
        draw.ellipse([0, 0, s - 1, s - 1], fill=255)
        shift = s * thickness * (-1 if opens == "left" else 1)
        draw.ellipse([shift - s * 0.04, -s * 0.06, s + shift + s * 0.04, s * 1.06], fill=0)

    return _shape(size, size, color, paint)


def triple_moon(height: float, color: str) -> Image.Image:
    """Waxing crescent, full moon, waning crescent: the triple moon."""
    gap = height * 0.16
    width = height * 3 + gap * 2
    img = Image.new("RGBA", (round(width), round(height)), (0, 0, 0, 0))
    left = crescent(height, color, opens="left")
    right = crescent(height, color, opens="right")
    full = _shape(
        height,
        height,
        color,
        lambda d, ss: d.ellipse(
            [height * ss * 0.12, height * ss * 0.12, height * ss * 0.88, height * ss * 0.88],
            fill=255,
        ),
    )
    img.alpha_composite(left, (0, 0))
    img.alpha_composite(full, (round(height + gap), 0))
    img.alpha_composite(right, (round(2 * (height + gap)), 0))
    return img


def divider(
    page: Image.Image,
    fmt: PageFormat,
    theme: Theme,
    cx: float,
    y: float,
    width: float,
) -> None:
    """A centered rule with a triple moon in the middle and a small star at
    each end. Plain themes get a simple rule."""
    draw = ImageDraw.Draw(page)
    if not theme.ornaments:
        draw.line([(cx - width / 2, y), (cx + width / 2, y)], fill=theme.accent, width=3)
        return
    moon_h = fmt.px(0.13)
    emblem = triple_moon(moon_h, theme.accent)
    gap = emblem.width / 2 + fmt.px(0.09)
    star = fmt.px(0.09)
    line_w = max(2, fmt.px(0.007))
    draw.line([(cx - width / 2 + star, y), (cx - gap, y)], fill=theme.accent, width=line_w)
    draw.line([(cx + gap, y), (cx + width / 2 - star, y)], fill=theme.accent, width=line_w)
    paste_center(page, emblem, cx, y)
    for sx in (cx - width / 2 + star / 2, cx + width / 2 - star / 2):
        paste_center(page, sparkle(star, theme.accent), sx, y)


def page_frame(page: Image.Image, fmt: PageFormat, theme: Theme, outer: Box) -> None:
    """A double-ruled border with star corners and a crescent at the top
    center and a star at the bottom center."""
    draw = ImageDraw.Draw(page)
    thick = max(3, fmt.px(0.011))
    thin = max(2, fmt.px(0.005))
    gap = fmt.px(0.045)
    draw.rectangle(
        [outer.left, outer.top, outer.right, outer.bottom], outline=theme.accent, width=thick
    )
    draw.rectangle(
        [outer.left + gap, outer.top + gap, outer.right - gap, outer.bottom - gap],
        outline=theme.accent,
        width=thin,
    )
    corner = fmt.px(0.26)
    mid = gap / 2
    corners = [
        (outer.left + mid, outer.top + mid),
        (outer.right - mid, outer.top + mid),
        (outer.left + mid, outer.bottom - mid),
        (outer.right - mid, outer.bottom - mid),
    ]
    for x, y in corners:
        knock_out(draw, x, y, corner * 0.42)
        paste_center(page, sparkle(corner, theme.accent), x, y)

    cx = (outer.left + outer.right) / 2
    top_y = outer.top + mid
    bottom_y = outer.bottom - mid
    moon = fmt.px(0.2)
    knock_out(draw, cx, top_y, moon * 1.15, moon * 0.62)
    paste_center(page, crescent(moon, theme.accent, opens="left"), cx - moon * 0.32, top_y)
    paste_center(page, sparkle(moon * 0.55, theme.accent), cx + moon * 0.42, top_y)
    knock_out(draw, cx, bottom_y, moon * 0.62)
    paste_center(page, sparkle(moon * 1.1, theme.accent, points=8, inner=0.12), cx, bottom_y)


def star_scatter(
    page: Image.Image,
    box: tuple[float, float, float, float],
    fmt: PageFormat,
    color: str,
    seed: int,
    density: float = 3.0,
) -> None:
    """Scatters small stars and dots over a region -- `density` is roughly
    marks per square inch."""
    x0, y0, x1, y1 = box
    area_in = (x1 - x0) * (y1 - y0) / (fmt.dpi**2)
    rng = random.Random(seed)
    count = max(1, round(area_in * density))
    margin = fmt.px(0.06)
    for _ in range(count):
        x = rng.uniform(x0 + margin, x1 - margin)
        y = rng.uniform(y0 + margin, y1 - margin)
        roll = rng.random()
        if roll < 0.35:
            paste_center(page, sparkle(fmt.px(rng.uniform(0.07, 0.12)), color), x, y)
        else:
            paste_center(page, dot(fmt.px(rng.uniform(0.018, 0.03)), color), x, y)


def start_page(fmt: PageFormat, theme: Theme, page_number: int) -> tuple[Image.Image, Box]:
    """A blank page with the theme's frame (if any) and the content box to
    draw inside it."""
    page = fmt.new_page()
    box = fmt.content_box(page_number)
    if not theme.frame:
        return page, box
    out, inset = fmt.px(FRAME_OUT_IN), fmt.px(FRAME_IN_IN)
    page_frame(
        page, fmt, theme, Box(box.left - out, box.top - out, box.right + out, box.bottom + out)
    )
    return page, Box(box.left + inset, box.top + inset, box.right - inset, box.bottom - inset)


def draw_header(
    page: Image.Image,
    fmt: PageFormat,
    theme: Theme,
    box: Box,
    title: str,
    subtitle: str | None = None,
    title_size_in: float = 0.42,
) -> float:
    """Centered page title, optional italic subtitle and a divider; returns
    the y coordinate where the page body should start."""
    draw = ImageDraw.Draw(page)
    title_font = theme.display_font(fmt.px(title_size_in))
    # Shrink long titles to fit the width.
    while draw.textlength(title, font=title_font) > box.width and title_font.size > 20:
        title_font = theme.display_font(round(title_font.size * 0.92))
    draw.text((box.center_x, box.top), title, font=title_font, fill=theme.accent, anchor="ma")
    # 1.35x clears descenders (the "y" in January, the "J" in Journal).
    y = box.top + int(title_font.size * 1.35)
    if subtitle:
        sub_font = theme.italic_font(fmt.px(0.15))
        draw.text((box.center_x, y), subtitle, font=sub_font, fill=theme.soft, anchor="ma")
        y += int(sub_font.size * 1.45)
    divider(page, fmt, theme, box.center_x, y + fmt.px(0.06), box.width * 0.5)
    return y + fmt.px(0.26)


def render_themed_title_page(
    fmt: PageFormat,
    theme: Theme,
    title: str,
    subtitle: str | None,
    author: str | None,
    page_number: int = 1,
) -> Image.Image:
    """A KDP title page in the theme's style: a large moon emblem, the title,
    subtitle and author, with a light star scatter."""
    page, box = start_page(fmt, theme, page_number)
    draw = ImageDraw.Draw(page)
    cy = box.top + box.height * 0.3
    if theme.ornaments:
        emblem = triple_moon(fmt.px(0.55), theme.accent)
        paste_center(page, emblem, box.center_x, cy - fmt.px(0.9))
        star_scatter(
            page,
            (box.left, box.top, box.right, cy - fmt.px(1.4)),
            fmt,
            theme.grid,
            seed=zlib.crc32(title.encode()),
            density=1.2,
        )
    title_font = theme.display_font(fmt.px(0.62))
    while draw.textlength(title, font=title_font) > box.width * 0.9 and title_font.size > 40:
        title_font = theme.display_font(round(title_font.size * 0.92))
    draw.text((box.center_x, cy), title, font=title_font, fill=theme.accent, anchor="mm")
    y = cy + title_font.size * 0.9
    divider(page, fmt, theme, box.center_x, y, box.width * 0.55)
    y += fmt.px(0.3)
    if subtitle:
        sub_font = theme.italic_font(fmt.px(0.22))
        draw.text((box.center_x, y), subtitle, font=sub_font, fill=theme.soft, anchor="ma")
    if author:
        author_font = theme.heading_font(fmt.px(0.2))
        draw.text(
            (box.center_x, box.bottom - fmt.px(0.6)),
            author,
            font=author_font,
            fill=theme.ink,
            anchor="ms",
        )
    return page

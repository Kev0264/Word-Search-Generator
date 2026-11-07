from PIL import Image, ImageFont

from pagegen import ornaments
from pagegen.layout import KDP_BOOK, LETTER
from pagegen.moon.calendar import build_moon_calendar, build_moon_year, render_month_page
from pagegen.tarot.render import build_tarot_pages
from pagegen.theme import CELESTIAL, FONT_DIR, PLAIN, THEMES, resolve_theme


def _is_gray(img: Image.Image) -> bool:
    rgb = img.convert("RGB")
    r, g, b = rgb.split()
    return r.tobytes() == g.tobytes() == b.tobytes()


def test_bundled_fonts_load_and_have_licenses():
    font = CELESTIAL.heading_font(60)
    assert isinstance(font, ImageFont.FreeTypeFont)
    assert "Cinzel" in font.getname()[0]
    assert "Garamond" in CELESTIAL.body_font(60).getname()[0]
    assert sorted(p.name for p in FONT_DIR.glob("OFL-*.txt")) == [
        "OFL-Cinzel.txt",
        "OFL-EBGaramond.txt",
    ]


def test_grayscale_converts_every_color():
    gray = CELESTIAL.grayscale()
    for name in ("ink", "soft", "rule", "grid", "accent", "tint", "moon_dark"):
        value = getattr(gray, name)
        assert value[1:3] == value[3:5] == value[5:7], name
    assert resolve_theme("celestial", grayscale=False) is THEMES["celestial"]


def test_celestial_month_page_uses_color_and_frame():
    year = build_moon_year(2027)
    page = render_month_page(year, 10, LETTER, theme=CELESTIAL)
    assert not _is_gray(page)
    # The frame sits in the margin, outside the plain content box.
    box = LETTER.content_box(1)
    frame_y = box.top - LETTER.px(ornaments.FRAME_OUT_IN)
    row = page.crop((box.left + 50, frame_y - 3, box.left + 400, frame_y + 4)).convert("L")
    assert row.getextrema()[0] < 120
    plain = render_month_page(year, 10, LETTER, theme=PLAIN)
    row = plain.crop((box.left + 50, frame_y - 3, box.left + 400, frame_y + 4)).convert("L")
    assert row.getextrema()[0] == 255


def test_kdp_output_is_always_grayscale():
    pages, _ = build_moon_calendar(2027, KDP_BOOK, journal=True, theme=CELESTIAL)
    assert all(_is_gray(p) for p in pages[:5])
    pages, _ = build_tarot_pages(["daily"], KDP_BOOK, count=22, theme=CELESTIAL)
    assert all(_is_gray(p) for p in pages[:4])


def test_ornaments_render():
    for img in (
        ornaments.sparkle(40, "#4b2f63"),
        ornaments.sparkle(40, "#4b2f63", points=8),
        ornaments.crescent(40, "#4b2f63"),
        ornaments.triple_moon(40, "#4b2f63"),
    ):
        assert img.mode == "RGBA"
        assert img.getchannel("A").getextrema()[1] > 200
    # A waxing crescent's ink is on the right side.
    alpha = ornaments.crescent(80, "#000000", opens="left").getchannel("A")
    assert alpha.getpixel((70, 40)) > alpha.getpixel((10, 40))

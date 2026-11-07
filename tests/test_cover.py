import pytest
from PIL import Image

from pagegen.cli import main
from pagegen.cover import (
    MIN_PAGES_FOR_SPINE_TEXT,
    CoverGeometry,
    build_cover,
    count_pdf_pages,
    spine_width_in,
)
from pagegen.layout import LETTER, save_pdf


@pytest.fixture
def art(tmp_path):
    """A 300 DPI front-cover-sized image: dark plum with a lighter center."""
    path = tmp_path / "art.png"
    img = Image.new("RGB", (2625, 3375), (40, 28, 56))
    img.paste((200, 180, 220), (900, 1200, 1700, 2000))
    img.save(path)
    return path


def test_spine_and_canvas_dimensions():
    assert spine_width_in(100, "white") == pytest.approx(0.2252)
    assert spine_width_in(100, "cream") == pytest.approx(0.25)
    geo = CoverGeometry(8.5, 11, spine_width_in(100, "white"))
    # bleed + back + spine + front + bleed, at 300 DPI
    assert geo.width_px == round((0.125 * 2 + 8.5 * 2 + 0.2252) * 300)
    assert geo.height_px == round(11.25 * 300)
    assert geo.spine_right - geo.spine_left == pytest.approx(0.2252 * 300, abs=1)
    left, top, right, bottom = geo.barcode_box
    assert right <= geo.spine_left and bottom < geo.trim_bottom


def test_count_pdf_pages(tmp_path):
    path = tmp_path / "interior.pdf"
    save_pdf([LETTER.new_page() for _ in range(5)], path)
    assert count_pdf_pages(path) == 5


def test_build_cover_and_spine_text_rule(art):
    image, warnings = build_cover(art, 28, "Moon|Calendar", "Subtitle", "Author", "Blurb.")
    assert image.size == (CoverGeometry(8.5, 11, spine_width_in(28)).width_px, 3375)
    assert any("79+" in w for w in warnings)
    # Allowed at 79 pages, but that spine is too thin to letter legibly.
    _, warnings = build_cover(art, MIN_PAGES_FOR_SPINE_TEXT, "Moon Calendar", author="A")
    assert any("legible" in w for w in warnings)
    image, warnings = build_cover(art, 200, "Moon Calendar", author="A")
    assert not any("spine" in w for w in warnings)
    geo = CoverGeometry(8.5, 11, spine_width_in(200))
    spine = image.crop((geo.spine_left, 0, geo.spine_right, image.height)).convert("L")
    assert spine.getextrema()[1] > 150  # gold lettering on the dark spine


def test_low_resolution_art_warns(tmp_path):
    path = tmp_path / "small.png"
    Image.new("RGB", (875, 1125), (30, 20, 40)).save(path)
    _, warnings = build_cover(path, 30, "Title")
    assert any("DPI" in w for w in warnings)


def test_rejects_short_books_and_overlong_blurbs(art):
    with pytest.raises(ValueError):
        build_cover(art, 10, "Title")
    with pytest.raises(ValueError, match="barcode"):
        build_cover(art, 30, "Title", blurb="\n\n".join(["Word " * 80] * 8))


def test_cover_command(art, tmp_path):
    out = tmp_path / "cover.pdf"
    args = ["cover", "--art", str(art), "--pages", "30", "--title", "Tarot Journal"]
    assert main([*args, "--author", "A", "--art-scale", "0.92", "-o", str(out)]) == 0
    assert out.is_file()
    assert main([*args, "--strict", "-o", str(out)]) == 1  # warns: no spine text

import pytest

from pagegen.layout import A4, KDP_BOOK, LETTER
from pagegen.tarot.render import build_tarot_pages, render_spread_page
from pagegen.tarot.spreads import CARD_ASPECT, SPREADS


def _card_box(p):
    w, h = (CARD_ASPECT, 1.0) if p.rotated else (1.0, CARD_ASPECT)
    return p.x - w / 2, p.y - h / 2, p.x + w / 2, p.y + h / 2


@pytest.mark.parametrize("key", list(SPREADS))
def test_spread_cards_do_not_overlap_except_crossing_card(key):
    positions = SPREADS[key].positions
    for i, a in enumerate(positions):
        for b in positions[i + 1 :]:
            if a.rotated or b.rotated:
                continue
            ax0, ay0, ax1, ay1 = _card_box(a)
            bx0, by0, bx1, by1 = _card_box(b)
            overlap = ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1
            assert not overlap, f"{key}: '{a.label}' overlaps '{b.label}'"


@pytest.mark.parametrize("key", list(SPREADS))
@pytest.mark.parametrize("fmt", [LETTER, A4, KDP_BOOK])
def test_every_spread_renders_on_every_format(key, fmt):
    page = render_spread_page(SPREADS[key], fmt)
    assert page.size == (fmt.width_px, fmt.height_px)


def test_printable_pages_cycle_spreads_without_front_matter():
    pages, warnings = build_tarot_pages(["daily", "three_card"], LETTER, count=3)
    assert len(pages) == 6
    assert warnings == []


def test_kdp_journal_has_front_matter_and_warns_when_short():
    pages, warnings = build_tarot_pages(["daily"], KDP_BOOK, count=4)
    assert len(pages) % 2 == 0
    assert warnings and "24" in warnings[0]
    pages, warnings = build_tarot_pages(["daily"], KDP_BOOK, count=40)
    assert warnings == []
    assert len(pages) >= 42  # title + copyright + 40 spreads


def test_unknown_spread_is_rejected():
    with pytest.raises(ValueError, match="nope"):
        build_tarot_pages(["nope"], LETTER)

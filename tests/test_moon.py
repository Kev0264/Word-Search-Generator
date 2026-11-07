from datetime import date, datetime, timezone

import pytest

from pagegen.layout import A4, KDP_BOOK, LETTER, MIN_KDP_PAGES
from pagegen.moon.astronomy import (
    DECEMBER_SOLSTICE,
    FULL_MOON,
    MARCH_EQUINOX,
    NEW_MOON,
    illumination,
    lunation_fraction,
    moon_phases,
    season_start,
)
from pagegen.moon.calendar import build_moon_calendar, build_moon_year, draw_moon, phase_name


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


# Published USNO times (UTC, to the minute).
@pytest.mark.parametrize(
    "phase, expected",
    [
        (NEW_MOON, _utc(2024, 4, 8, 18, 21)),  # the April 2024 total solar eclipse
        (FULL_MOON, _utc(2024, 1, 25, 17, 54)),
        (FULL_MOON, _utc(2025, 3, 14, 6, 55)),  # March 2025 total lunar eclipse
    ],
)
def test_moon_phase_times_match_published_values(phase, expected):
    events = moon_phases(
        _utc(expected.year, expected.month, 1), _utc(expected.year, expected.month, 28, 23)
    )
    match = [e for e in events if e.phase == phase]
    assert match, f"no {phase} found"
    assert abs((match[0].when - expected).total_seconds()) < 120


def test_moon_phases_are_ordered_and_cycle():
    events = moon_phases(_utc(2027, 1, 1), _utc(2028, 1, 1))
    assert all(a.when < b.when for a, b in zip(events, events[1:]))
    order = ["New Moon", "First Quarter", "Full Moon", "Last Quarter"]
    for a, b in zip(events, events[1:]):
        assert order.index(b.phase) == (order.index(a.phase) + 1) % 4


def test_season_start_matches_published_values():
    assert abs((season_start(2024, MARCH_EQUINOX) - _utc(2024, 3, 20, 3, 6)).total_seconds()) < 120
    assert (
        abs((season_start(2024, DECEMBER_SOLSTICE) - _utc(2024, 12, 21, 9, 20)).total_seconds())
        < 120
    )


def test_lunation_fraction_and_illumination():
    events = moon_phases(_utc(2024, 1, 1), _utc(2024, 3, 1))
    full = next(e for e in events if e.phase == FULL_MOON)
    assert lunation_fraction(full.when, events) == pytest.approx(0.5)
    assert illumination(0.5) == pytest.approx(1.0)
    assert illumination(0.0) == pytest.approx(0.0)
    assert phase_name(0.1) == "Waxing Crescent"
    assert phase_name(0.9) == "Waning Crescent"


def test_moon_year_marks_sabbats_and_full_moon_names():
    year = build_moon_year(2027, "America/New_York")
    assert len(year.days) == 365
    assert year.days[date(2027, 10, 31)].sabbat == "Samhain"
    assert year.days[date(2027, 3, 20)].sabbat == "Ostara"
    assert year.days[date(2027, 1, 22)].full_moon_name == "Wolf Moon"
    names = set(year.full_moon_names.values())
    assert {"Harvest Moon", "Hunter's Moon"} <= names


def test_blue_moon_only_counts_same_calendar_year():
    # 2026 has a Blue Moon on May 31; 2027 has none (a regression check that
    # last November/December's full moons aren't counted against this year).
    assert "Blue Moon" in build_moon_year(2026).full_moon_names.values()
    assert "Blue Moon" not in build_moon_year(2027).full_moon_names.values()


def test_harvest_moon_can_fall_in_october():
    year = build_moon_year(2028)
    harvest = [when for when, name in year.full_moon_names.items() if name == "Harvest Moon"]
    assert len(harvest) == 1 and harvest[0].month == 10


def test_principal_phase_days_draw_the_exact_phase():
    year = build_moon_year(2027)
    for info in year.days.values():
        for e in info.events:
            if e.phase == FULL_MOON:
                assert info.fraction == 0.5


def test_draw_moon_shading():
    full = draw_moon(0.5, 80).convert("L")
    new = draw_moon(0.0, 80).convert("L")
    center = (40, 40)
    assert full.getpixel(center) > 200
    assert new.getpixel(center) < 100
    waxing = draw_moon(0.2, 80).convert("L")
    assert waxing.getpixel((62, 40)) > waxing.getpixel((18, 40))  # lit on the right


@pytest.mark.parametrize("fmt", [LETTER, A4])
def test_printable_calendar_page_counts(fmt):
    pages, warnings = build_moon_calendar(2027, fmt)
    assert len(pages) == 13  # overview + 12 months
    assert all(p.size == (fmt.width_px, fmt.height_px) for p in pages)
    assert warnings == []
    pages, _ = build_moon_calendar(2027, fmt, journal=True)
    assert len(pages) == 25


def test_kdp_calendar_needs_journal_to_reach_minimum():
    pages, warnings = build_moon_calendar(2027, KDP_BOOK)
    assert warnings and "24" in warnings[0]
    pages, warnings = build_moon_calendar(2027, KDP_BOOK, journal=True)
    assert warnings == []
    assert len(pages) >= MIN_KDP_PAGES and len(pages) % 2 == 0

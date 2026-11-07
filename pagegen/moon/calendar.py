"""Moon phase calendar: a year-at-a-glance page, one month grid per month
(every day's moon drawn to its actual phase), and optional facing journal
pages for new-moon intentions and full-moon reflections."""

from __future__ import annotations

import calendar as pycal
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from .. import bookparts
from ..fonts import wrap_paragraph
from ..layout import KDP_BOOK, MIN_KDP_PAGES, PageFormat, stamp_page_numbers
from ..ornaments import (
    divider,
    draw_header,
    paste_center,
    render_themed_title_page,
    sparkle,
    star_scatter,
    start_page,
)
from ..theme import PLAIN, Theme
from .astronomy import (
    DECEMBER_SOLSTICE,
    FIRST_QUARTER,
    FULL_MOON,
    JUNE_SOLSTICE,
    LAST_QUARTER,
    MARCH_EQUINOX,
    NEW_MOON,
    SEPTEMBER_EQUINOX,
    PhaseEvent,
    lunation_fraction,
    moon_phases,
    season_start,
)

DEFAULT_TIMEZONE = "America/New_York"

# Traditional (North American / Old Farmer's Almanac) full moon names by
# month. The Harvest and Hunter's Moons are assigned by the equinox rather
# than by month -- see _full_moon_names.
MONTHLY_FULL_MOON_NAMES = {
    1: "Wolf Moon",
    2: "Snow Moon",
    3: "Worm Moon",
    4: "Pink Moon",
    5: "Flower Moon",
    6: "Strawberry Moon",
    7: "Buck Moon",
    8: "Sturgeon Moon",
    9: "Corn Moon",
    10: "Hunter's Moon",
    11: "Beaver Moon",
    12: "Cold Moon",
}

# Traditional correspondences, shown as a month page's subtitle and in the
# full-moon journal prompt.
FULL_MOON_MEANINGS = {
    "Wolf Moon": "protection, resilience, inner strength",
    "Snow Moon": "purification, rest, quiet planning",
    "Worm Moon": "renewal, awakening, fresh starts",
    "Pink Moon": "growth, hope, new love",
    "Flower Moon": "abundance, beauty, creativity",
    "Strawberry Moon": "gratitude, sweetness, fulfillment",
    "Buck Moon": "ambition, strength, setting goals",
    "Sturgeon Moon": "perseverance, abundance, reaping effort",
    "Corn Moon": "gathering, balance, gratitude",
    "Harvest Moon": "harvest, balance, giving thanks",
    "Hunter's Moon": "ancestors, protection, preparation",
    "Beaver Moon": "home, preparation, shadow work",
    "Cold Moon": "reflection, rest, release",
    "Blue Moon": "rare magic, wishes, amplified intentions",
}

SABBAT_MEANINGS = {
    "Imbolc": "hearth, candle magic, first stirrings of spring",
    "Ostara": "balance and new growth",
    "Beltane": "fire, fertility and blossoming",
    "Litha": "the sun at its height",
    "Lughnasadh": "first harvest, gratitude and skill",
    "Mabon": "balance and thanksgiving",
    "Samhain": "honoring ancestors as the veil thins",
    "Yule": "the return of the light",
}

INK = PLAIN.ink
MOON_DARK = PLAIN.moon_dark


@dataclass
class DayInfo:
    day: date
    fraction: float  # position in the lunar cycle at local noon
    events: list[PhaseEvent] = field(default_factory=list)  # local-time events on this date
    full_moon_name: str | None = None
    sabbat: str | None = None


@dataclass
class MoonYear:
    year: int
    tz: ZoneInfo
    days: dict[date, DayInfo]
    events: list[PhaseEvent]  # this year's principal phases, local time
    full_moon_names: dict[datetime, str]
    sabbats: list[tuple[date, str]]

    def month_events(self, month: int) -> list[PhaseEvent]:
        return [e for e in self.events if e.when.month == month]


def phase_name(fraction: float) -> str:
    """One of the eight conventional phase names for a lunation fraction,
    used for days that don't contain a principal phase instant."""
    if fraction < 0.25:
        return "Waxing Crescent"
    if fraction < 0.5:
        return "Waxing Gibbous"
    if fraction < 0.75:
        return "Waning Gibbous"
    return "Waning Crescent"


def _full_moon_names(
    full_moons: list[PhaseEvent], september_equinox: datetime
) -> dict[datetime, str]:
    names = {e.when: MONTHLY_FULL_MOON_NAMES[e.when.month] for e in full_moons}

    # A second full moon in the same calendar month is a Blue Moon.
    seen_months: set[tuple[int, int]] = set()
    for e in full_moons:
        key = (e.when.year, e.when.month)
        if key in seen_months:
            names[e.when] = "Blue Moon"
        seen_months.add(key)

    # The Harvest Moon is whichever full moon falls nearest the September
    # equinox (so it's sometimes in October), and the Hunter's Moon is the
    # one after it.
    if full_moons:
        harvest_index = min(
            range(len(full_moons)),
            key=lambda i: abs((full_moons[i].when - september_equinox).total_seconds()),
        )
        names[full_moons[harvest_index].when] = "Harvest Moon"
        if harvest_index + 1 < len(full_moons):
            names[full_moons[harvest_index + 1].when] = "Hunter's Moon"
    return names


def build_moon_year(year: int, tz_name: str = DEFAULT_TIMEZONE) -> MoonYear:
    tz = ZoneInfo(tz_name)
    # Compute a margin of phases either side of the year so every day's
    # lunation fraction is bracketed by a phase before and after it.
    utc_events = moon_phases(
        datetime(year - 1, 11, 15, tzinfo=timezone.utc),
        datetime(year + 1, 2, 15, tzinfo=timezone.utc),
    )
    local_events = [PhaseEvent(e.phase, e.when.astimezone(tz)) for e in utc_events]
    in_year = [e for e in local_events if e.when.year == year]

    seasons = {
        name: season_start(year, name).astimezone(tz)
        for name in (MARCH_EQUINOX, JUNE_SOLSTICE, SEPTEMBER_EQUINOX, DECEMBER_SOLSTICE)
    }
    # Northern-hemisphere Wheel of the Year: the cross-quarter days on their
    # traditional fixed dates, the quarter days on the actual solstice or
    # equinox date in this timezone.
    sabbats = sorted(
        [
            (date(year, 2, 1), "Imbolc"),
            (seasons[MARCH_EQUINOX].date(), "Ostara"),
            (date(year, 5, 1), "Beltane"),
            (seasons[JUNE_SOLSTICE].date(), "Litha"),
            (date(year, 8, 1), "Lughnasadh"),
            (seasons[SEPTEMBER_EQUINOX].date(), "Mabon"),
            (date(year, 10, 31), "Samhain"),
            (seasons[DECEMBER_SOLSTICE].date(), "Yule"),
        ]
    )

    full_moons = [e for e in local_events if e.phase == FULL_MOON]
    names = _full_moon_names(full_moons, seasons[SEPTEMBER_EQUINOX])
    sabbat_by_date = dict(sabbats)

    days: dict[date, DayInfo] = {}
    d = date(year, 1, 1)
    while d.year == year:
        noon = datetime.combine(d, time(12), tzinfo=tz)
        info = DayInfo(day=d, fraction=lunation_fraction(noon, local_events))
        info.events = [e for e in in_year if e.when.date() == d]
        for e in info.events:
            if e.phase == FULL_MOON:
                info.full_moon_name = names.get(e.when)
            # Draw the principal phase exactly on its own day, not the
            # noon interpolation, so e.g. a full moon at 11pm still shows full.
            info.fraction = {
                NEW_MOON: 0.0,
                FIRST_QUARTER: 0.25,
                FULL_MOON: 0.5,
                LAST_QUARTER: 0.75,
            }[e.phase]
        info.sabbat = sabbat_by_date.get(d)
        days[d] = info
        d += timedelta(days=1)

    return MoonYear(
        year=year,
        tz=tz,
        days=days,
        events=in_year,
        full_moon_names={k: v for k, v in names.items() if k.year == year},
        sabbats=sabbats,
    )


# --------------------------------------------------------------------------
# Drawing

PHASE_FRACTION_EXACT = {NEW_MOON: 0.0, FIRST_QUARTER: 0.25, FULL_MOON: 0.5, LAST_QUARTER: 0.75}


def draw_moon(
    fraction: float,
    diameter: int,
    supersample: int = 4,
    dark: str = MOON_DARK,
    outline: str = INK,
) -> Image.Image:
    """An RGBA moon icon showing the lit portion for a lunation fraction, as
    seen from the northern hemisphere (waxing lit on the right). Drawn
    oversized and downsampled so the limb and terminator stay smooth."""
    size = diameter * supersample
    r = size / 2 - supersample * 1.5
    c = size / 2
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([c - r, c - r, c + r, c + r], fill=dark)

    theta = 2 * math.pi * fraction
    steps = 120
    limb: list[tuple[float, float]] = []
    terminator: list[tuple[float, float]] = []
    for i in range(steps + 1):
        y = -r + 2 * r * i / steps
        w = math.sqrt(max(0.0, r * r - y * y))
        if fraction < 0.5:  # waxing: lit from the terminator to the right limb
            limb.append((c + w, c + y))
            terminator.append((c + w * math.cos(theta), c + y))
        else:  # waning: lit from the left limb to the terminator
            limb.append((c - w, c + y))
            terminator.append((c - w * math.cos(theta), c + y))
    polygon = limb + terminator[::-1]
    if len(polygon) >= 3:
        draw.polygon(polygon, fill="white")
    draw.ellipse(
        [c - r, c - r, c + r, c + r], outline=outline, width=max(2, round(supersample * 1.6))
    )
    return img.resize((diameter, diameter), Image.LANCZOS)


def _paste_moon(
    page: Image.Image, theme: Theme, fraction: float, diameter: int, cx: float, cy: float
) -> None:
    icon = draw_moon(fraction, diameter, dark=theme.moon_dark, outline=theme.ink)
    page.paste(icon, (round(cx - diameter / 2), round(cy - diameter / 2)), icon)


def _rule(draw: ImageDraw.ImageDraw, x0: float, x1: float, y: float, color: str, width: int = 2):
    draw.line([(x0, y), (x1, y)], fill=color, width=width)


def _fmt_time(when: datetime) -> str:
    hour = when.strftime("%I").lstrip("0")
    return f"{hour}:{when.strftime('%M %p')} {when.tzname()}"


def _short_date(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}"


def _event_label(moon_year: MoonYear, event: PhaseEvent) -> str:
    if event.phase == FULL_MOON and event.when in moon_year.full_moon_names:
        return f"Full Moon · {moon_year.full_moon_names[event.when]}"
    return event.phase


def _month_full_moons(moon_year: MoonYear, month: int) -> list[str]:
    return [
        moon_year.full_moon_names[e.when]
        for e in moon_year.month_events(month)
        if e.phase == FULL_MOON and e.when in moon_year.full_moon_names
    ]


def _month_subtitle(moon_year: MoonYear, month: int) -> str | None:
    """e.g. "Hunter's Moon · ancestors, protection, preparation"."""
    names = _month_full_moons(moon_year, month)
    if not names:
        return None
    # A Blue Moon month shows the rarer moon's meaning.
    name = "Blue Moon" if "Blue Moon" in names else names[0]
    meaning = FULL_MOON_MEANINGS.get(name)
    return f"{name} · {meaning}" if meaning else name


def _draw_writing_lines(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    left: float,
    right: float,
    top: float,
    bottom: float,
    spacing: int,
) -> float:
    y = top + spacing
    while y <= bottom:
        _rule(draw, left, right, y, theme.rule)
        y += spacing
    return y


def _section_heading(draw, theme: Theme, fmt: PageFormat, x: float, y: float, text: str) -> int:
    font = theme.heading_font(fmt.px(0.15))
    draw.text((x, y), text, font=font, fill=theme.accent, anchor="la")
    return font.size


def render_month_page(
    moon_year: MoonYear,
    month: int,
    fmt: PageFormat,
    page_number: int = 1,
    week_start: int = 6,
    theme: Theme = PLAIN,
) -> Image.Image:
    """week_start follows the `calendar` module: 6 = Sunday, 0 = Monday."""
    page, box = start_page(fmt, theme, page_number)
    draw = ImageDraw.Draw(page)
    month_name = pycal.month_name[month]
    subtitle = _month_subtitle(moon_year, month) if theme.ornaments else None
    y = draw_header(page, fmt, theme, box, f"{month_name} {moon_year.year}", subtitle)

    weeks = pycal.Calendar(firstweekday=week_start).monthdatescalendar(moon_year.year, month)
    cols = 7
    cell_w = box.width / cols

    weekday_font = theme.heading_font(fmt.px(0.11))
    weekday_h = fmt.px(0.24)
    weekday_names = [pycal.day_abbr[(week_start + i) % 7].upper() for i in range(cols)]
    if theme.ornaments:
        draw.rectangle([box.left, y, box.right, y + weekday_h], fill=theme.tint)
    for i, name in enumerate(weekday_names):
        draw.text(
            (box.left + cell_w * (i + 0.5), y + weekday_h / 2),
            name,
            font=weekday_font,
            fill=theme.accent if theme.ornaments else theme.soft,
            anchor="mm",
        )
    y += weekday_h

    events = moon_year.month_events(month)
    sabbats = [(d, name) for d, name in moon_year.sabbats if d.month == month]
    list_font = theme.body_font(fmt.px(0.115))
    list_line_h = int(list_font.size * 1.6)
    # Reserve room for the month's phase list plus a few note lines below.
    footer_h = fmt.px(0.45) + list_line_h * (len(events) + len(sabbats)) + fmt.px(0.9)
    grid_h = min(box.bottom - y - footer_h, cell_w * 1.05 * len(weeks))
    cell_h = grid_h / len(weeks)
    grid_top = y

    day_font = theme.numeral_font(fmt.px(0.13))
    label_font = theme.body_font(fmt.px(0.085))
    sabbat_font = theme.heading_font(fmt.px(0.085))
    moon_d = round(min(cell_w, cell_h) * 0.42)
    pad = fmt.px(0.05)

    for r, week in enumerate(weeks):
        for c, d in enumerate(week):
            x0 = box.left + c * cell_w
            y0 = grid_top + r * cell_h
            if d.month != month:
                draw.rectangle([x0, y0, x0 + cell_w, y0 + cell_h], fill=theme.tint)
                if theme.ornaments:
                    star_scatter(
                        page,
                        (x0, y0, x0 + cell_w, y0 + cell_h),
                        fmt,
                        theme.grid,
                        seed=d.toordinal(),
                        density=7,
                    )
                continue
            info = moon_year.days[d]
            if theme.ornaments and any(e.phase == FULL_MOON for e in info.events):
                draw.rectangle([x0, y0, x0 + cell_w, y0 + cell_h], fill=theme.tint)
            draw.text((x0 + pad, y0 + pad), str(d.day), font=day_font, fill=theme.ink, anchor="la")
            if info.sabbat and theme.ornaments:
                star = fmt.px(0.13)
                paste_center(
                    page,
                    sparkle(star, theme.accent),
                    x0 + cell_w - pad - star / 2,
                    y0 + pad + star / 2,
                )
            _paste_moon(page, theme, info.fraction, moon_d, x0 + cell_w / 2, y0 + cell_h * 0.47)

            labels: list[tuple[str, object, str]] = []
            if info.sabbat:
                labels.append((info.sabbat, sabbat_font, theme.accent))
            for e in info.events:
                text = (
                    info.full_moon_name if e.phase == FULL_MOON and info.full_moon_name else e.phase
                )
                labels.append((text, label_font, theme.ink))
            ly = y0 + cell_h - pad
            for text, font, color in reversed(labels[:2]):
                draw.text((x0 + cell_w / 2, ly), text, font=font, fill=color, anchor="md")
                ly -= int(font.size * 1.15)

    for r in range(len(weeks) + 1):
        _rule(draw, box.left, box.right, grid_top + r * cell_h, theme.grid, 2)
    for c in range(cols + 1):
        x = box.left + c * cell_w
        draw.line([(x, grid_top), (x, grid_top + grid_h)], fill=theme.grid, width=2)

    y = grid_top + grid_h + fmt.px(0.25)
    heading_size = _section_heading(draw, theme, fmt, box.left, y, "This Month's Moon")
    y += int(heading_size * 1.6)
    icon_d = round(fmt.px(0.115) * 1.3)
    for e in events:
        cy = y + list_line_h / 2
        _paste_moon(page, theme, PHASE_FRACTION_EXACT[e.phase], icon_d, box.left + icon_d / 2, cy)
        when = f"{e.when.strftime('%a')}, {_short_date(e.when.date())} · {_fmt_time(e.when)}"
        text = f"{_event_label(moon_year, e)} — {when}"
        draw.text((box.left + icon_d * 1.6, cy), text, font=list_font, fill=theme.ink, anchor="lm")
        y += list_line_h

    for d, name in sabbats:
        cy = y + list_line_h / 2
        paste_center(page, sparkle(icon_d * 1.05, theme.accent), box.left + icon_d / 2, cy)
        text = f"{name} — {d.strftime('%a')}, {_short_date(d)}"
        if theme.ornaments and name in SABBAT_MEANINGS:
            text += f" · {SABBAT_MEANINGS[name]}"
        draw.text((box.left + icon_d * 1.6, cy), text, font=list_font, fill=theme.ink, anchor="lm")
        y += list_line_h

    y += fmt.px(0.1)
    if box.bottom - y > fmt.px(0.5):
        heading_size = _section_heading(draw, theme, fmt, box.left, y, "Notes")
        _draw_writing_lines(
            draw, theme, box.left, box.right, y + int(heading_size * 0.6), box.bottom, fmt.px(0.34)
        )
    return page


def render_journal_page(
    moon_year: MoonYear, month: int, fmt: PageFormat, page_number: int = 1, theme: Theme = PLAIN
) -> Image.Image:
    page, box = start_page(fmt, theme, page_number)
    draw = ImageDraw.Draw(page)
    events = moon_year.month_events(month)
    y = draw_header(page, fmt, theme, box, f"{pycal.month_name[month]} Moon Journal")

    def dates_for(phase: str) -> str:
        found = [e for e in events if e.phase == phase]
        if not found:
            return ""
        parts = []
        for e in found:
            label = _short_date(e.when.date())
            if phase == FULL_MOON and e.when in moon_year.full_moon_names:
                label += f" ({moon_year.full_moon_names[e.when]})"
            parts.append(label)
        return " & ".join(parts)

    full_prompt = "What has come to fruition? What am I ready to let go of?"
    full_names = _month_full_moons(moon_year, month)
    if theme.ornaments and full_names and full_names[0] in FULL_MOON_MEANINGS:
        full_prompt += f" {full_names[0]} themes: {FULL_MOON_MEANINGS[full_names[0]]}."
    sections = [
        (
            0.0,
            "New Moon",
            dates_for(NEW_MOON),
            "Intentions",
            "What am I calling in this cycle? What seeds am I planting?",
        ),
        (0.5, "Full Moon", dates_for(FULL_MOON), "Release & Gratitude", full_prompt),
    ]
    heading_font = theme.heading_font(fmt.px(0.2))
    date_font = theme.italic_font(fmt.px(0.13))
    prompt_font = theme.italic_font(fmt.px(0.115))
    icon_d = fmt.px(0.42)
    section_h = (box.bottom - y) / len(sections)

    for i, (fraction, phase_label, dates, purpose, prompt) in enumerate(sections):
        top = y + i * section_h
        if i and theme.ornaments:
            divider(page, fmt, theme, box.center_x, top - fmt.px(0.12), box.width * 0.3)
        _paste_moon(page, theme, fraction, icon_d, box.left + icon_d / 2, top + icon_d / 2)
        tx = box.left + icon_d + fmt.px(0.18)
        draw.text(
            (tx, top),
            f"{phase_label}: {purpose}",
            font=heading_font,
            fill=theme.accent,
            anchor="la",
        )
        if dates:
            draw.text(
                (tx, top + int(heading_font.size * 1.3)),
                dates,
                font=date_font,
                fill=theme.soft,
                anchor="la",
            )
        prompt_y = top + icon_d + fmt.px(0.12)
        for line in wrap_paragraph(prompt, prompt_font, box.width):
            draw.text((box.left, prompt_y), line, font=prompt_font, fill=theme.soft, anchor="la")
            prompt_y += int(prompt_font.size * 1.3)
        _draw_writing_lines(
            draw, theme, box.left, box.right, prompt_y, top + section_h - fmt.px(0.25), fmt.px(0.36)
        )
    return page


def render_overview_page(
    moon_year: MoonYear, fmt: PageFormat, page_number: int = 1, theme: Theme = PLAIN
) -> Image.Image:
    page, box = start_page(fmt, theme, page_number)
    draw = ImageDraw.Draw(page)
    y = draw_header(
        page,
        fmt,
        theme,
        box,
        f"{moon_year.year} at a Glance",
        "New moons, full moons & the Wheel of the Year",
    )

    head_font = theme.heading_font(fmt.px(0.13))
    cell_font = theme.body_font(fmt.px(0.115))
    row_h = fmt.px(0.35)
    col_x = [box.left + fmt.px(0.08), box.left + box.width * 0.24, box.left + box.width * 0.47]
    icon_d = round(head_font.size * 1.3)

    if theme.ornaments:
        draw.rectangle(
            [box.left, y - fmt.px(0.06), box.right, y + row_h - fmt.px(0.1)], fill=theme.tint
        )
    _paste_moon(page, theme, 0.0, icon_d, col_x[1] + icon_d / 2, y + head_font.size * 0.55)
    _paste_moon(page, theme, 0.5, icon_d, col_x[2] + icon_d / 2, y + head_font.size * 0.55)
    draw.text((col_x[0], y), "Month", font=head_font, fill=theme.accent, anchor="la")
    draw.text(
        (col_x[1] + icon_d * 1.4, y), "New Moon", font=head_font, fill=theme.accent, anchor="la"
    )
    draw.text(
        (col_x[2] + icon_d * 1.4, y), "Full Moon", font=head_font, fill=theme.accent, anchor="la"
    )
    y += row_h
    _rule(draw, box.left, box.right, y - fmt.px(0.08), theme.grid, 2)

    for month in range(1, 13):
        events = moon_year.month_events(month)
        new = ", ".join(str(e.when.day) for e in events if e.phase == NEW_MOON)
        full = ", ".join(
            f"{e.when.day} · {moon_year.full_moon_names.get(e.when, '')}"
            for e in events
            if e.phase == FULL_MOON
        )
        draw.text(
            (col_x[0], y), pycal.month_name[month], font=cell_font, fill=theme.ink, anchor="la"
        )
        draw.text((col_x[1], y), new, font=cell_font, fill=theme.ink, anchor="la")
        draw.text((col_x[2], y), full, font=cell_font, fill=theme.ink, anchor="la")
        y += row_h
        _rule(draw, box.left, box.right, y - fmt.px(0.08), theme.rule)

    y += fmt.px(0.3)
    if theme.ornaments:
        divider(page, fmt, theme, box.center_x, y, box.width * 0.4)
        y += fmt.px(0.22)
    section_font = theme.heading_font(fmt.px(0.2))
    draw.text(
        (box.center_x, y), "Wheel of the Year", font=section_font, fill=theme.accent, anchor="ma"
    )
    y += int(section_font.size * 1.8)
    half = box.width / 2
    name_font = theme.heading_font(fmt.px(0.115))
    star = fmt.px(0.13)
    for i, (d, name) in enumerate(moon_year.sabbats):
        col, row = divmod(i, 4)
        x = box.left + col * half + fmt.px(0.2)
        yy = y + row * row_h
        paste_center(page, sparkle(star, theme.accent), x + star / 2, yy + name_font.size * 0.5)
        baseline = yy + name_font.size
        draw.text((x + fmt.px(0.25), baseline), name, font=name_font, fill=theme.ink, anchor="ls")
        draw.text(
            (x + half - fmt.px(0.4), baseline),
            f"{d.strftime('%a')}, {_short_date(d)}",
            font=cell_font,
            fill=theme.ink,
            anchor="rs",
        )
    y += row_h * 4 + fmt.px(0.2)

    note_font = theme.italic_font(fmt.px(0.1))
    note = (
        f"Moon phases are calculated astronomically for the {moon_year.tz.key.replace('_', ' ')} "
        "time zone; dates near midnight can differ by a day elsewhere. Sabbat dates follow the "
        "northern hemisphere."
    )
    for line in wrap_paragraph(note, note_font, box.width):
        draw.text((box.center_x, y), line, font=note_font, fill=theme.soft, anchor="ma")
        y += int(note_font.size * 1.4)
    return page


def build_moon_calendar(
    year: int,
    fmt: PageFormat,
    tz_name: str = DEFAULT_TIMEZONE,
    journal: bool = False,
    week_start: int = 6,
    title: str | None = None,
    subtitle: str | None = None,
    author: str | None = None,
    theme: Theme = PLAIN,
) -> tuple[list[Image.Image], list[str]]:
    moon_year = build_moon_year(year, tz_name)
    warnings: list[str] = []
    pages: list[Image.Image] = []
    is_book = fmt is KDP_BOOK
    if is_book:
        theme = theme.grayscale()  # KDP black-and-white interior

    if is_book:
        book_title = title or f"{year} Moon Calendar"
        if theme.ornaments:
            pages.append(render_themed_title_page(fmt, theme, book_title, subtitle, author, 1))
        else:
            pages.append(bookparts.render_title_page(book_title, author, 1, subtitle=subtitle))
        pages.append(
            bookparts.render_copyright_page(
                book_title,
                author,
                date.today().year,
                2,
                note="Moon phase dates and times are calculated astronomically.",
            )
        )

    pages.append(render_overview_page(moon_year, fmt, len(pages) + 1, theme))
    if is_book and journal:
        # Put each month on a left-hand (even) page with its journal page
        # facing it, so the pair reads as one spread.
        if (len(pages) + 1) % 2 == 1:
            pages.append(fmt.new_page())

    for month in range(1, 13):
        pages.append(render_month_page(moon_year, month, fmt, len(pages) + 1, week_start, theme))
        if journal:
            pages.append(render_journal_page(moon_year, month, fmt, len(pages) + 1, theme))

    if is_book:
        if len(pages) % 2 == 1:
            pages.append(fmt.new_page())
        if len(pages) < MIN_KDP_PAGES:
            warnings.append(
                f"Book is {len(pages)} page(s); KDP paperback requires at least {MIN_KDP_PAGES}. "
                "Add --journal to include a journal page for each month."
            )
    stamp_page_numbers(pages, fmt)
    return pages, warnings

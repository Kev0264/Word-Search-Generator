"""Offline lunar phase and equinox/solstice times.

Implements the algorithms from Jean Meeus, *Astronomical Algorithms* (2nd
ed.): chapter 49 for the moon's principal phases (accurate to well under a
minute for current centuries) and chapter 27 for equinoxes and solstices.
Both produce Julian Ephemeris Days in Dynamical Time, converted to UTC with
an approximate Delta-T -- a ~70 second correction that only matters for a
phase landing within a minute of midnight.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SYNODIC_MONTH = 29.530588861

NEW_MOON = "New Moon"
FIRST_QUARTER = "First Quarter"
FULL_MOON = "Full Moon"
LAST_QUARTER = "Last Quarter"

PRINCIPAL_PHASES = (NEW_MOON, FIRST_QUARTER, FULL_MOON, LAST_QUARTER)

# Fraction of the lunation (0 = new, 0.5 = full) at each principal phase.
PHASE_FRACTION = {NEW_MOON: 0.0, FIRST_QUARTER: 0.25, FULL_MOON: 0.5, LAST_QUARTER: 0.75}

MARCH_EQUINOX = "March Equinox"
JUNE_SOLSTICE = "June Solstice"
SEPTEMBER_EQUINOX = "September Equinox"
DECEMBER_SOLSTICE = "December Solstice"


@dataclass(frozen=True)
class PhaseEvent:
    phase: str  # one of PRINCIPAL_PHASES
    when: datetime  # timezone-aware UTC


def _jd_to_utc(jde: float) -> datetime:
    utc = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=jde - 2440587.5)
    return utc - timedelta(seconds=_delta_t_seconds(utc.year + (utc.month - 0.5) / 12))


def _delta_t_seconds(year: float) -> float:
    """Espenak & Meeus polynomial for TT - UT, valid 2005-2050; outside that
    range the error grows but stays far below a minute for nearby years."""
    t = year - 2000
    return 62.92 + 0.32217 * t + 0.005589 * t * t


def _sin(deg: float) -> float:
    return math.sin(math.radians(deg))


def _cos(deg: float) -> float:
    return math.cos(math.radians(deg))


# (coefficient, E power, M multiple, M' multiple, F multiple, Omega multiple)
_NEW_TERMS = [
    (-0.40720, 0, 0, 1, 0, 0),
    (0.17241, 1, 1, 0, 0, 0),
    (0.01608, 0, 0, 2, 0, 0),
    (0.01039, 0, 0, 0, 2, 0),
    (0.00739, 1, -1, 1, 0, 0),
    (-0.00514, 1, 1, 1, 0, 0),
    (0.00208, 2, 2, 0, 0, 0),
    (-0.00111, 0, 0, 1, -2, 0),
    (-0.00057, 0, 0, 1, 2, 0),
    (0.00056, 1, 1, 2, 0, 0),
    (-0.00042, 0, 0, 3, 0, 0),
    (0.00042, 1, 1, 0, 2, 0),
    (0.00038, 1, 1, 0, -2, 0),
    (-0.00024, 1, -1, 2, 0, 0),
    (-0.00017, 0, 0, 0, 0, 1),
    (-0.00007, 0, 2, 1, 0, 0),
    (0.00004, 0, 0, 2, -2, 0),
    (0.00004, 0, 3, 0, 0, 0),
    (0.00003, 0, 1, 1, -2, 0),
    (0.00003, 0, 0, 2, 2, 0),
    (-0.00003, 0, 1, 1, 2, 0),
    (0.00003, 0, -1, 1, 2, 0),
    (-0.00002, 0, -1, 1, -2, 0),
    (-0.00002, 0, 1, 3, 0, 0),
    (0.00002, 0, 0, 4, 0, 0),
]

_FULL_TERMS = [
    (-0.40614, 0, 0, 1, 0, 0),
    (0.17302, 1, 1, 0, 0, 0),
    (0.01614, 0, 0, 2, 0, 0),
    (0.01043, 0, 0, 0, 2, 0),
    (0.00734, 1, -1, 1, 0, 0),
    (-0.00515, 1, 1, 1, 0, 0),
    (0.00209, 2, 2, 0, 0, 0),
    (-0.00111, 0, 0, 1, -2, 0),
    (-0.00057, 0, 0, 1, 2, 0),
    (0.00056, 1, 1, 2, 0, 0),
    (-0.00042, 0, 0, 3, 0, 0),
    (0.00042, 1, 1, 0, 2, 0),
    (0.00038, 1, 1, 0, -2, 0),
    (-0.00024, 1, -1, 2, 0, 0),
    (-0.00017, 0, 0, 0, 0, 1),
    (-0.00007, 0, 2, 1, 0, 0),
    (0.00004, 0, 0, 2, -2, 0),
    (0.00004, 0, 3, 0, 0, 0),
    (0.00003, 0, 1, 1, -2, 0),
    (0.00003, 0, 0, 2, 2, 0),
    (-0.00003, 0, 1, 1, 2, 0),
    (0.00003, 0, -1, 1, 2, 0),
    (-0.00002, 0, -1, 1, -2, 0),
    (-0.00002, 0, 1, 3, 0, 0),
    (0.00002, 0, 0, 4, 0, 0),
]

_QUARTER_TERMS = [
    (-0.62801, 0, 0, 1, 0, 0),
    (0.17172, 1, 1, 0, 0, 0),
    (-0.01183, 1, 1, 1, 0, 0),
    (0.00862, 0, 0, 2, 0, 0),
    (0.00804, 0, 0, 0, 2, 0),
    (0.00454, 1, -1, 1, 0, 0),
    (0.00204, 2, 2, 0, 0, 0),
    (-0.00180, 0, 0, 1, -2, 0),
    (-0.00070, 0, 0, 1, 2, 0),
    (-0.00040, 0, 0, 3, 0, 0),
    (-0.00034, 1, -1, 2, 0, 0),
    (0.00032, 1, 1, 0, 2, 0),
    (0.00032, 1, 1, 0, -2, 0),
    (-0.00028, 2, 2, 1, 0, 0),
    (0.00027, 1, 1, 2, 0, 0),
    (-0.00017, 0, 0, 0, 0, 1),
    (-0.00005, 0, -1, 1, -2, 0),
    (0.00004, 0, 0, 2, 2, 0),
    (-0.00004, 0, 1, 1, 2, 0),
    (0.00004, 0, -2, 1, 0, 0),
    (0.00003, 0, 1, 1, -2, 0),
    (0.00003, 0, 3, 0, 0, 0),
    (0.00002, 0, 0, 2, -2, 0),
    (0.00002, 0, -1, 1, 2, 0),
    (-0.00002, 0, 1, 3, 0, 0),
]

_PLANETARY = [
    (299.77, 0.107408, 325),
    (251.88, 0.016321, 165),
    (251.83, 26.651886, 164),
    (349.42, 36.412478, 126),
    (84.66, 18.206239, 110),
    (141.74, 53.303771, 62),
    (207.14, 2.453732, 60),
    (154.84, 7.306860, 56),
    (34.52, 27.261239, 47),
    (207.19, 0.121824, 42),
    (291.34, 1.844379, 40),
    (161.72, 24.198154, 37),
    (239.56, 25.513099, 35),
    (331.55, 3.592518, 23),
]


def _phase_jde(k: float) -> float:
    """JDE of the phase identified by k: an integer for a new moon, +0.25 for
    first quarter, +0.5 for full, +0.75 for last quarter (k=0 is the new
    moon of 2000-01-06)."""
    t = k / 1236.85
    jde = (
        2451550.09766
        + SYNODIC_MONTH * k
        + 0.00015437 * t**2
        - 0.000000150 * t**3
        + 0.00000000073 * t**4
    )
    e = 1 - 0.002516 * t - 0.0000074 * t**2
    m = 2.5534 + 29.10535670 * k - 0.0000014 * t**2 - 0.00000011 * t**3
    mp = 201.5643 + 385.81693528 * k + 0.0107582 * t**2 + 0.00001238 * t**3 - 0.000000058 * t**4
    f = 160.7108 + 390.67050284 * k - 0.0016118 * t**2 - 0.00000227 * t**3 + 0.000000011 * t**4
    om = 124.7746 - 1.56375588 * k + 0.0020672 * t**2 + 0.00000215 * t**3

    fraction = round((k % 1) * 4) / 4
    terms = {0.0: _NEW_TERMS, 0.5: _FULL_TERMS}.get(fraction, _QUARTER_TERMS)
    for coeff, e_pow, cm, cmp, cf, com in terms:
        jde += coeff * e**e_pow * _sin(cm * m + cmp * mp + cf * f + com * om)

    if fraction in (0.25, 0.75):
        w = (
            0.00306
            - 0.00038 * e * _cos(m)
            + 0.00026 * _cos(mp)
            - 0.00002 * _cos(mp - m)
            + 0.00002 * _cos(mp + m)
            + 0.00002 * _cos(2 * f)
        )
        jde += w if fraction == 0.25 else -w

    a1_quadratic = -0.009173 * t**2
    for i, (base, rate, coeff) in enumerate(_PLANETARY):
        arg = base + rate * k + (a1_quadratic if i == 0 else 0)
        jde += coeff * 1e-6 * _sin(arg)
    return jde


def moon_phases(start: datetime, end: datetime) -> list[PhaseEvent]:
    """Every principal phase whose instant falls in [start, end), in order.
    start/end must be timezone-aware."""
    phase_for_fraction = {0.0: NEW_MOON, 0.25: FIRST_QUARTER, 0.5: FULL_MOON, 0.75: LAST_QUARTER}
    years_from_2000 = (start - datetime(2000, 1, 6, tzinfo=timezone.utc)).days / 365.25
    k = math.floor(years_from_2000 * 12.3685) - 1
    events: list[PhaseEvent] = []
    while True:
        for quarter in (0.0, 0.25, 0.5, 0.75):
            when = _jd_to_utc(_phase_jde(k + quarter))
            if when >= end:
                return events
            if when >= start:
                events.append(PhaseEvent(phase_for_fraction[quarter], when))
        k += 1


_SEASON_TERMS = [
    (485, 324.96, 1934.136),
    (203, 337.23, 32964.467),
    (199, 342.08, 20.186),
    (182, 27.85, 445267.112),
    (156, 73.14, 45036.886),
    (136, 171.52, 22518.443),
    (77, 222.54, 65928.934),
    (74, 296.72, 3034.906),
    (70, 243.58, 9037.513),
    (58, 119.81, 33718.147),
    (52, 297.17, 150.678),
    (50, 21.02, 2281.226),
    (45, 247.54, 29929.562),
    (44, 325.15, 31555.956),
    (29, 60.93, 4443.417),
    (18, 155.12, 67555.328),
    (17, 288.79, 4562.452),
    (16, 198.04, 62894.029),
    (14, 199.76, 31436.921),
    (12, 95.39, 14577.848),
    (12, 287.11, 31931.756),
    (12, 320.81, 34777.259),
    (9, 227.73, 1222.114),
    (8, 15.45, 16859.074),
]

_SEASON_MEAN = {
    MARCH_EQUINOX: (2451623.80984, 365242.37404, 0.05169, -0.00411, -0.00057),
    JUNE_SOLSTICE: (2451716.56767, 365241.62603, 0.00325, 0.00888, -0.00030),
    SEPTEMBER_EQUINOX: (2451810.21715, 365242.01767, -0.11575, 0.00337, 0.00078),
    DECEMBER_SOLSTICE: (2451900.05952, 365242.74049, -0.06223, -0.00823, 0.00032),
}


def season_start(year: int, event: str) -> datetime:
    """UTC instant of an equinox or solstice (valid for years 1000-3000)."""
    y = (year - 2000) / 1000
    c0, c1, c2, c3, c4 = _SEASON_MEAN[event]
    jde0 = c0 + c1 * y + c2 * y**2 + c3 * y**3 + c4 * y**4
    t = (jde0 - 2451545.0) / 36525
    w = 35999.373 * t - 2.47
    dl = 1 + 0.0334 * _cos(w) + 0.0007 * _cos(2 * w)
    s = sum(a * _cos(b + c * t) for a, b, c in _SEASON_TERMS)
    return _jd_to_utc(jde0 + 0.00001 * s / dl)


def lunation_fraction(when: datetime, events: list[PhaseEvent]) -> float:
    """Where `when` sits in the lunar cycle (0 = new, 0.25 = first quarter,
    0.5 = full, 0.75 = last quarter), interpolated between the surrounding
    principal phases so a day's drawn moon always agrees with the phase
    events listed for it. `events` must bracket `when`."""
    for before, after in zip(events, events[1:]):
        if before.when <= when < after.when:
            span = (after.when - before.when).total_seconds()
            progress = (when - before.when).total_seconds() / span
            return (PHASE_FRACTION[before.phase] + 0.25 * progress) % 1.0
    raise ValueError(f"{when} is not bracketed by the given phase events")


def illumination(fraction: float) -> float:
    """Approximate illuminated fraction of the disk (0..1)."""
    return (1 - math.cos(2 * math.pi * fraction)) / 2

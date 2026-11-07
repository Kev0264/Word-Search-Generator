"""Tarot spread definitions.

Card positions are in "card units": one unit is a card's width, and a card
is CARD_ASPECT units tall. (x, y) is the card's center; y grows downward.
The renderer scales the whole layout to fit the page, so only relative
placement matters here.
"""

from __future__ import annotations

from dataclasses import dataclass

CARD_ASPECT = 1.7  # height / width -- standard tarot cards are ~2.75 x 4.75in


@dataclass(frozen=True)
class Position:
    label: str
    x: float
    y: float
    rotated: bool = False  # laid sideways, e.g. the Celtic Cross's crossing card


@dataclass(frozen=True)
class Spread:
    key: str
    name: str
    description: str
    positions: tuple[Position, ...]


def _row(labels: list[str], y: float = 0.0, spacing: float = 1.35) -> list[Position]:
    start = -spacing * (len(labels) - 1) / 2
    return [Position(label, start + i * spacing, y) for i, label in enumerate(labels)]


def _horseshoe() -> tuple[Position, ...]:
    labels = [
        "Past",
        "Present",
        "Hidden Influences",
        "Obstacles",
        "Others' Influence",
        "Best Course of Action",
        "Likely Outcome",
    ]
    spacing = 1.4  # > 1 card width, so neighbors never overlap
    half_span = spacing * (len(labels) - 1) / 2
    positions = []
    for i, label in enumerate(labels):
        # An arch: both ends low, the middle card highest.
        x = -half_span + i * spacing
        positions.append(Position(label, x, -1.9 * (1 - (x / half_span) ** 2)))
    return tuple(positions)


SPREADS: dict[str, Spread] = {
    s.key: s
    for s in [
        Spread(
            "daily",
            "Daily Draw",
            "One card to set the tone for the day ahead.",
            (Position("Card of the Day", 0, 0),),
        ),
        Spread(
            "three_card",
            "Past · Present · Future",
            "The classic three-card reading for any question.",
            tuple(_row(["Past", "Present", "Future"])),
        ),
        Spread(
            "mind_body_spirit",
            "Mind · Body · Spirit",
            "A check-in on where your energy is right now.",
            tuple(_row(["Mind", "Body", "Spirit"])),
        ),
        Spread(
            "celtic_cross",
            "Celtic Cross",
            "The traditional ten-card spread for a deep look at a situation.",
            (
                Position("The Present", 0, 0),
                Position("The Challenge", 0, 0, rotated=True),
                Position("The Foundation", 0, 1.95),
                Position("The Recent Past", -1.65, 0),
                Position("The Best Outcome", 0, -1.95),
                Position("The Near Future", 1.65, 0),
                Position("Your Attitude", 3.45, 2.85),
                Position("External Influences", 3.45, 0.95),
                Position("Hopes & Fears", 3.45, -0.95),
                Position("The Outcome", 3.45, -2.85),
            ),
        ),
        Spread(
            "horseshoe",
            "Horseshoe",
            "Seven cards tracing a situation from its roots to where it's headed.",
            _horseshoe(),
        ),
        Spread(
            "new_moon",
            "New Moon Intentions",
            "Plant seeds for the lunar cycle ahead.",
            tuple(
                _row(["What I'm Calling In", "Seed to Plant", "How to Nurture It"], y=0)
                + _row(["What Stands in the Way", "Guidance"], y=1.95)
            ),
        ),
        Spread(
            "full_moon",
            "Full Moon Release",
            "Reflect on what the cycle has brought, and what to let go.",
            tuple(
                _row(["What Is Illuminated", "What Has Grown", "What to Release"], y=0)
                + _row(["The Lesson", "Next Step"], y=1.95)
            ),
        ),
        Spread(
            "samhain",
            "Samhain Ancestor Spread",
            "When the veil is thin: a reading for reflection and remembrance.",
            (
                Position("A Message from the Ancestors", 0, -1.0),
                Position("What to Leave in the Old Year", -1.4, 1.0),
                Position("What to Carry Forward", 1.4, 1.0),
                Position("Guidance for the Dark Half", 0, 2.9),
            ),
        ),
    ]
}

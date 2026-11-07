"""`pagegen` command: one subcommand per page type.

pagegen wordsearch ...   (same options as the standalone `wordsearch` command)
pagegen moon --year 2027 --paper letter a4 -o moon_2027.pdf
pagegen tarot --spreads three_card celtic_cross --paper letter a4 -o spreads.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .layout import PAPER_FORMATS, output_path_for, save_pdf
from .theme import DEFAULT_THEME, THEMES, resolve_theme


def _add_common_options(parser: argparse.ArgumentParser, default_output: str) -> None:
    parser.add_argument(
        "--paper",
        nargs="+",
        choices=list(PAPER_FORMATS),
        default=["letter"],
        help="One or more output formats: 'kdp' (8.5x11 book interior with mirrored "
        "gutter margins, front matter and page numbers), 'letter' or 'a4' (home-printable "
        "downloads). Passing several writes one PDF per format, suffixed with its name. "
        "Default: letter",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=default_output,
        help=f"Output PDF path (default: {default_output})",
    )
    parser.add_argument("--title", help="Book title for the title page (kdp only)")
    parser.add_argument("--subtitle", help="Subtitle for the title page (kdp only)")
    parser.add_argument("--author", help="Author name for the title and copyright pages (kdp only)")
    parser.add_argument(
        "--theme",
        choices=list(THEMES),
        default=DEFAULT_THEME,
        help="Visual style: 'celestial' (Cinzel/Garamond type, framed pages, moon and star "
        f"ornaments) or 'plain' (system fonts, no ornaments). Default: {DEFAULT_THEME}",
    )
    parser.add_argument(
        "--grayscale",
        action="store_true",
        help="Printer-friendly black-and-white version of the theme for letter/a4 "
        "(kdp is always grayscale, for KDP's black-and-white interiors)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if the build produced warnings (files are still written)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pagegen",
        description="Generate printable pages and KDP book interiors.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "wordsearch",
        help="Word search puzzles and books (run `pagegen wordsearch --help` for options)",
        add_help=False,
    )

    moon = sub.add_parser("moon", help="Moon phase calendar for a year")
    moon.add_argument("--year", type=int, required=True, help="Calendar year, e.g. 2027")
    moon.add_argument(
        "--timezone",
        default="America/New_York",
        help="IANA time zone that phase dates/times are shown in (default: America/New_York)",
    )
    moon.add_argument(
        "--journal",
        action="store_true",
        help="Add a new-moon/full-moon journal page after each month "
        "(needed for a kdp book to reach KDP's 24-page minimum)",
    )
    moon.add_argument(
        "--week-start",
        choices=["sunday", "monday"],
        default="sunday",
        help="First day of each calendar week (default: sunday)",
    )
    _add_common_options(moon, "moon_calendar.pdf")

    from .tarot.spreads import SPREADS

    tarot = sub.add_parser("tarot", help="Fill-in tarot spread journal pages")
    tarot.add_argument(
        "--spreads",
        nargs="+",
        default=list(SPREADS),
        metavar="SPREAD",
        help=f"Spreads to include, in order (default: all). Choices: {', '.join(SPREADS)}",
    )
    tarot.add_argument(
        "--count",
        type=int,
        default=1,
        help="Repeat the spread sequence this many times, e.g. --spreads daily --count 60 "
        "for a 60-page daily-draw journal (default: 1)",
    )
    tarot.add_argument("--intro", help="Markdown file rendered as introduction page(s) (kdp only)")
    tarot.add_argument("--list", action="store_true", help="List the available spreads and exit")
    _add_common_options(tarot, "tarot_spreads.pdf")

    cover = sub.add_parser(
        "cover",
        help="KDP wraparound paperback cover (back, spine, front) around front-cover art",
    )
    cover.add_argument(
        "--art",
        required=True,
        help="Front-cover image, ideally 2625x3375px (8.75x11.25in with bleed at 300 DPI)",
    )
    pages = cover.add_mutually_exclusive_group(required=True)
    pages.add_argument("--pages", type=int, help="Interior page count (sets the spine width)")
    pages.add_argument("--interior", help="Interior PDF to read the page count from")
    cover.add_argument("--title", required=True, help='Book title; "|" forces a line break')
    cover.add_argument("--subtitle")
    cover.add_argument("--author")
    cover.add_argument(
        "--blurb",
        help="Back-cover text, or a path to a text file. Blank lines separate paragraphs; "
        "lines starting with '- ' become starred bullet points",
    )
    cover.add_argument("--paper", choices=["white", "cream"], default="white")
    cover.add_argument(
        "--art-scale",
        type=float,
        default=1.0,
        help="Shrink the art (e.g. 0.94) so a border drawn near its edge moves inside "
        "KDP's trim tolerance; the margin is filled from the art's own background",
    )
    cover.add_argument(
        "--title-top",
        type=float,
        default=0.75,
        help="Distance from the top trim to the title, in inches (default 0.75)",
    )
    cover.add_argument(
        "--title-size",
        type=float,
        default=0.8,
        help="Largest title cap height in inches; long titles shrink to fit (default 0.8)",
    )
    cover.add_argument(
        "--author-bottom",
        type=float,
        default=0.75,
        help="Distance from the bottom trim to the author line, in inches (default 0.75)",
    )
    cover.add_argument("--theme", choices=list(THEMES), default=DEFAULT_THEME)
    cover.add_argument(
        "--guides",
        action="store_true",
        help="Overlay trim, safe-zone, spine and barcode guides (for proofing only)",
    )
    cover.add_argument("--output", "-o", default="cover.pdf")
    cover.add_argument("--strict", action="store_true")
    return parser


def _write_outputs(build, args: argparse.Namespace) -> int:
    """Calls build(fmt) -> (pages, warnings) for each requested paper format
    and writes each to its own PDF."""
    formats = list(dict.fromkeys(args.paper))
    any_warnings = False
    for name in formats:
        fmt = PAPER_FORMATS[name]
        pages, warnings = build(fmt)
        for warning in warnings:
            print(f"Warning ({name}): {warning}", file=sys.stderr)
        any_warnings = any_warnings or bool(warnings)
        path = output_path_for(args.output, fmt, multiple=len(formats) > 1)
        save_pdf(pages, path, fmt.dpi)
        print(f"{name}: saved {path} ({len(pages)} pages)")
    return 1 if args.strict and any_warnings else 0


def run_moon(args: argparse.Namespace) -> int:
    from .moon.calendar import build_moon_calendar

    try:
        ZoneInfo(args.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        print(
            f"Error: unknown time zone {args.timezone!r} (use an IANA name like America/Chicago)",
            file=sys.stderr,
        )
        return 1
    week_start = 6 if args.week_start == "sunday" else 0
    return _write_outputs(
        lambda fmt: build_moon_calendar(
            args.year,
            fmt,
            tz_name=args.timezone,
            journal=args.journal,
            week_start=week_start,
            title=args.title,
            subtitle=args.subtitle,
            author=args.author,
            theme=resolve_theme(args.theme, args.grayscale),
        ),
        args,
    )


def run_tarot(args: argparse.Namespace) -> int:
    from .tarot.render import build_tarot_pages
    from .tarot.spreads import SPREADS

    if args.list:
        for spread in SPREADS.values():
            cards = len(spread.positions)
            print(f"{spread.key:18} {spread.name} ({cards} cards) -- {spread.description}")
        return 0
    unknown = [k for k in args.spreads if k not in SPREADS]
    if unknown:
        print(
            f"Error: unknown spread(s): {', '.join(unknown)}. Choices: {', '.join(SPREADS)}",
            file=sys.stderr,
        )
        return 1
    if args.count < 1:
        print("Error: --count must be at least 1", file=sys.stderr)
        return 1
    intro_text = Path(args.intro).read_text(encoding="utf-8") if args.intro else None
    return _write_outputs(
        lambda fmt: build_tarot_pages(
            args.spreads,
            fmt,
            count=args.count,
            title=args.title,
            subtitle=args.subtitle,
            author=args.author,
            intro_text=intro_text,
            theme=resolve_theme(args.theme, args.grayscale),
        ),
        args,
    )


def run_cover(args: argparse.Namespace) -> int:
    from .cover import build_cover, count_pdf_pages, describe

    pages = args.pages if args.pages is not None else count_pdf_pages(args.interior)
    blurb = args.blurb
    if blurb and Path(blurb).is_file():
        blurb = Path(blurb).read_text(encoding="utf-8")
    try:
        image, warnings = build_cover(
            args.art,
            pages,
            args.title,
            subtitle=args.subtitle,
            author=args.author,
            blurb=blurb,
            paper=args.paper,
            theme=THEMES[args.theme],
            art_scale=args.art_scale,
            title_top_in=args.title_top,
            author_bottom_in=args.author_bottom,
            title_size_in=args.title_size,
            guides=args.guides,
        )
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    path = output_path_for(args.output, PAPER_FORMATS["kdp"], multiple=False)
    save_pdf([image], path, quality=95)
    print(describe(pages, args.paper))
    print(f"Saved {path}")
    return 1 if args.strict and warnings else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Hand everything after `wordsearch` straight to its own parser, so its
    # existing options and --help work unchanged.
    if argv and argv[0] == "wordsearch":
        from .wordsearch.cli import main as wordsearch_main

        return wordsearch_main(argv[1:])

    args = build_parser().parse_args(argv)
    if args.command == "moon":
        return run_moon(args)
    if args.command == "tarot":
        return run_tarot(args)
    if args.command == "cover":
        return run_cover(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

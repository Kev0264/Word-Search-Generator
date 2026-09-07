from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .grid import WordSearchGenerationError, WordSearchGenerator
from .render import PuzzleRenderer


def parse_size(value: str) -> tuple[int, int]:
    if "x" in value.lower():
        rows_str, cols_str = value.lower().split("x", 1)
        return int(rows_str), int(cols_str)
    size = int(value)
    return size, size


def load_words(args: argparse.Namespace) -> list[str]:
    if args.words_file:
        text = Path(args.words_file).read_text(encoding="utf-8")
        return [line for line in text.splitlines() if line.strip()]
    if args.words:
        return [w for w in args.words.split(",") if w.strip()]
    raise SystemExit("Provide words with --words-file or --words")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wordsearch",
        description="Generate a word search puzzle and export it as PNG or PDF.",
    )
    parser.add_argument("--words-file", "-f", help="Path to a text file with one word per line")
    parser.add_argument("--words", "-w", help="Comma-separated list of words")
    parser.add_argument(
        "--size", "-s", default="15", help="Grid size, e.g. 15 or 15x20 (ROWSxCOLS)"
    )
    parser.add_argument(
        "--output", "-o", default="puzzle.png", help="Output path for the puzzle (.png or .pdf)"
    )
    parser.add_argument("--answer-key", "-a", help="Optional output path for the answer key")
    parser.add_argument("--title", default="Word Search", help="Puzzle title")
    parser.add_argument("--seed", type=int, help="Random seed for reproducible puzzles")
    parser.add_argument(
        "--no-backwards",
        dest="allow_backwards",
        action="store_false",
        help="Disallow reversed words",
    )
    parser.add_argument(
        "--straight-only",
        action="store_true",
        help="Only place words horizontally and vertically (no diagonals)",
    )
    parser.add_argument("--cell-size", type=int, default=40, help="Pixel size of each grid cell")
    parser.set_defaults(allow_backwards=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    words = load_words(args)
    rows, cols = parse_size(args.size)
    directions = ["N", "S", "E", "W"] if args.straight_only else None

    generator = WordSearchGenerator(
        words,
        rows=rows,
        cols=cols,
        allow_backwards=args.allow_backwards,
        directions=directions,
        seed=args.seed,
    )

    try:
        generator.generate()
    except WordSearchGenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if generator.skipped:
        print(
            f"Warning: could not place {len(generator.skipped)} word(s): "
            f"{', '.join(generator.skipped)}",
            file=sys.stderr,
        )

    renderer = PuzzleRenderer(generator, title=args.title, cell_size=args.cell_size)
    renderer.save_puzzle(args.output)
    print(f"Puzzle saved to {args.output}")

    if args.answer_key:
        renderer.save_answer_key(args.answer_key)
        print(f"Answer key saved to {args.answer_key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .difficulty import DIFFICULTY_PRESETS, word_count_warning
from .grid import WordSearchGenerationError, WordSearchGenerator
from .render import PuzzleRenderer


def parse_size(value: str) -> tuple[int, int]:
    if "x" in value.lower():
        rows_str, cols_str = value.lower().split("x", 1)
        return int(rows_str), int(cols_str)
    size = int(value)
    return size, size


def title_from_filename(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title()


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
        description="Generate word search puzzles and export them as PNG or PDF.",
    )
    parser.add_argument("--words-file", "-f", help="Path to a text file with one word per line")
    parser.add_argument("--words", "-w", help="Comma-separated list of words")
    parser.add_argument(
        "--words-dir",
        "-d",
        help="Directory of .txt word list files; generates a puzzle and answer key "
        "for every file found",
    )
    parser.add_argument(
        "--csv",
        help="CSV file with a header row, then one puzzle per row (title, trivia "
        "[blank if none], then words); builds a single print-ready, multi-page KDP book PDF",
    )
    parser.add_argument(
        "--intro",
        help="Path to a text/markdown file rendered as the book's introduction "
        "page(s) (used with --csv)",
    )
    parser.add_argument(
        "--instructions",
        help="Path to a text/markdown file rendered as the book's instructions "
        "page(s) (used with --csv)",
    )
    parser.add_argument(
        "--book-title",
        help="Title for the book's title page (used with --csv; default: the CSV filename)",
    )
    parser.add_argument("--author", help="Author name printed on the title page (used with --csv)")
    parser.add_argument(
        "--year",
        type=int,
        help="Copyright year on the title page's copyright notice (used with --csv; "
        "default: the current year)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with a non-zero status if the build produced any warnings (used with "
        "--csv) -- the book is still saved either way, this just makes issues easy to "
        "catch in a script before publishing",
    )
    parser.add_argument(
        "--output-dir",
        default="generated_puzzles",
        help="Directory to write output into when using --words-dir (default: generated_puzzles)",
    )
    parser.add_argument(
        "--format",
        choices=["png", "pdf"],
        default="png",
        help="Output image format when using --words-dir (default: png)",
    )
    parser.add_argument(
        "--difficulty",
        choices=list(DIFFICULTY_PRESETS.keys()),
        help="Difficulty preset controlling grid size and allowed directions "
        "(overridden by explicit --size/--straight-only/--no-backwards)",
    )
    parser.add_argument(
        "--size",
        "-s",
        default=None,
        help="Grid size, e.g. 15 or 15x20 (ROWSxCOLS); default 15, or the "
        "--difficulty preset's size",
    )
    parser.add_argument(
        "--output", "-o", default="puzzle.png", help="Output path for the puzzle (.png or .pdf)"
    )
    parser.add_argument("--answer-key", "-a", help="Optional output path for the answer key")
    parser.add_argument(
        "--title", help="Puzzle title (default: 'Word Search', or the filename in --words-dir mode)"
    )
    parser.add_argument("--seed", type=int, help="Random seed for reproducible puzzles")
    parser.add_argument(
        "--no-backwards",
        dest="allow_backwards",
        action="store_false",
        default=None,
        help="Disallow reversed words",
    )
    parser.add_argument(
        "--straight-only",
        action="store_true",
        default=None,
        help="Only place words horizontally and vertically (no diagonals)",
    )
    parser.add_argument("--cell-size", type=int, default=40, help="Pixel size of each grid cell")
    return parser


def apply_difficulty(args: argparse.Namespace) -> None:
    """Fills in --size/--straight-only/--no-backwards from the --difficulty
    preset wherever the user didn't pass them explicitly."""
    preset = DIFFICULTY_PRESETS.get(args.difficulty, {})
    if args.size is None:
        args.size = preset.get("size", "15")
    if args.straight_only is None:
        args.straight_only = preset.get("straight_only", False)
    if args.allow_backwards is None:
        args.allow_backwards = preset.get("allow_backwards", True)


def build_generator(words: list[str], args: argparse.Namespace) -> WordSearchGenerator:
    rows, cols = parse_size(args.size)
    directions = ["N", "S", "E", "W"] if args.straight_only else None
    return WordSearchGenerator(
        words,
        rows=rows,
        cols=cols,
        allow_backwards=args.allow_backwards,
        directions=directions,
        seed=args.seed,
    )


def run_single(args: argparse.Namespace) -> int:
    words = load_words(args)
    generator = build_generator(words, args)

    warning = word_count_warning(args.difficulty, len(generator.words))
    if warning:
        print(f"Warning: {warning}", file=sys.stderr)

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

    if generator.blocked_words_found:
        print(
            "Warning: could not avoid blocked word(s) in the grid: "
            f"{', '.join(generator.blocked_words_found)}",
            file=sys.stderr,
        )

    if generator.duplicate_words_found:
        print(
            "Warning: word(s) accidentally appear more than once in the grid: "
            f"{', '.join(generator.duplicate_words_found)}",
            file=sys.stderr,
        )

    renderer = PuzzleRenderer(generator, title=args.title or "Word Search", cell_size=args.cell_size)
    renderer.save_puzzle(args.output)
    print(f"Puzzle saved to {args.output}")

    if args.answer_key:
        renderer.save_answer_key(args.answer_key)
        print(f"Answer key saved to {args.answer_key}")

    return 0


def run_batch(args: argparse.Namespace) -> int:
    words_dir = Path(args.words_dir)
    if not words_dir.is_dir():
        print(f"Error: {words_dir} is not a directory", file=sys.stderr)
        return 1

    txt_files = sorted(words_dir.glob("*.txt"))
    if not txt_files:
        print(f"Error: no .txt files found in {words_dir}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    exit_code = 0

    for txt_file in txt_files:
        words = [
            line for line in txt_file.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        generator = build_generator(words, args)

        warning = word_count_warning(args.difficulty, len(generator.words))
        if warning:
            print(f"Warning ({txt_file.name}): {warning}", file=sys.stderr)

        try:
            generator.generate()
        except WordSearchGenerationError as exc:
            print(f"Error generating {txt_file.name}: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        if generator.skipped:
            print(
                f"Warning ({txt_file.name}): could not place {len(generator.skipped)} "
                f"word(s): {', '.join(generator.skipped)}",
                file=sys.stderr,
            )

        if generator.blocked_words_found:
            print(
                f"Warning ({txt_file.name}): could not avoid blocked word(s) in the grid: "
                f"{', '.join(generator.blocked_words_found)}",
                file=sys.stderr,
            )

        if generator.duplicate_words_found:
            print(
                f"Warning ({txt_file.name}): word(s) accidentally appear more than once "
                f"in the grid: {', '.join(generator.duplicate_words_found)}",
                file=sys.stderr,
            )

        title = args.title or title_from_filename(txt_file)
        renderer = PuzzleRenderer(generator, title=title, cell_size=args.cell_size)

        puzzle_path = output_dir / f"{txt_file.stem}_puzzle.{args.format}"
        answer_path = output_dir / f"{txt_file.stem}_answer_key.{args.format}"
        renderer.save_puzzle(puzzle_path)
        renderer.save_answer_key(answer_path)
        print(f"{txt_file.name} -> {puzzle_path}, {answer_path}")

    return exit_code


def run_book(args: argparse.Namespace) -> int:
    from .book import build_book, read_puzzle_csv, save_book

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        print(f"Error: {csv_path} is not a file", file=sys.stderr)
        return 1

    specs = read_puzzle_csv(csv_path)
    if not specs:
        print(f"Error: no puzzles found in {csv_path}", file=sys.stderr)
        return 1

    rows, cols = parse_size(args.size)
    directions = ["N", "S", "E", "W"] if args.straight_only else None

    intro_text = Path(args.intro).read_text(encoding="utf-8") if args.intro else None
    instructions_text = (
        Path(args.instructions).read_text(encoding="utf-8") if args.instructions else None
    )
    book_title = args.book_title or title_from_filename(csv_path)

    pages, warnings = build_book(
        specs,
        rows=rows,
        cols=cols,
        allow_backwards=args.allow_backwards,
        directions=directions,
        seed=args.seed,
        book_title=book_title,
        author=args.author,
        intro_text=intro_text,
        instructions_text=instructions_text,
        difficulty=args.difficulty,
        year=args.year,
    )

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    output = args.output
    if output == "puzzle.png":
        output = "book.pdf"

    save_book(pages, output)
    warning_note = f", {len(warnings)} warning(s)" if warnings else ""
    print(f"Book saved to {output} ({len(pages)} pages, {len(specs)} puzzles{warning_note})")

    if args.strict and warnings:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_difficulty(args)

    if args.csv:
        return run_book(args)

    if args.words_dir:
        return run_batch(args)

    return run_single(args)


if __name__ == "__main__":
    raise SystemExit(main())

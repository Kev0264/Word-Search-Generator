# Word Search Generator

Generate word search puzzles from a word list and export them as PNG or PDF,
with an optional answer key.

## Features

- Places words in all 8 directions (horizontal, vertical, diagonal), forwards
  or backwards
- Configurable grid size and random fill letters
- Answer key export with placed words highlighted
- Reproducible output via `--seed`
- Word list loaded from a text file or the command line

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
python -m word_search.cli --words-file words.txt --size 15 --output puzzle.png --answer-key answer_key.png
```

Or with an editable install (`pip install -e .`), use the `wordsearch` command:

```bash
wordsearch -f words.txt -s 15x20 -o puzzle.pdf -a answer_key.pdf --title "My Puzzle" --seed 42
```

### Batch mode

Point `--words-dir` at a folder of `.txt` word lists to generate a puzzle and
answer key for every file in it:

```bash
wordsearch --words-dir word_lists --output-dir generated_puzzles --format png
```

Each `word_lists/animals.txt` produces `generated_puzzles/animals_puzzle.png`
and `generated_puzzles/animals_answer_key.png`. The title for each puzzle
defaults to the filename (`animals.txt` → "Animals") unless `--title` is set,
in which case it's used for every puzzle in the batch.

### Difficulty presets

`--difficulty {easy,medium,hard}` sets the grid size and allowed directions
to common word-search-book conventions:

| Difficulty | Grid size | Directions | Recommended word count |
| --- | --- | --- | --- |
| `easy` | 12×12 | horizontal/vertical only, no backwards | 8-12 |
| `medium` | 15×15 (default) | all 8 directions, backwards allowed | 12-18 |
| `hard` | 20×20 | all 8 directions, backwards allowed | 20-28 |

Any explicit `--size`, `--straight-only`, or `--no-backwards` flag overrides
the preset's value for that setting. If your word list falls outside the
recommended count for the chosen difficulty, a warning is printed (the
puzzle is still generated).

```bash
wordsearch -f words.txt --difficulty hard -o puzzle.png -a answer_key.png
```

### Book mode (KDP-ready PDF)

Point `--csv` at a spreadsheet of puzzles to build a single, print-ready,
multi-page PDF sized for KDP paperback (8.5×11in interior at 300 DPI, no
bleed, mirrored inside/outside margins, page numbers, and an even final page
count padded automatically):

```bash
wordsearch --csv puzzles.csv --intro intro.md --instructions instructions.md \
  --book-title "Themed Word Search Collection" --author "Jane Doe" \
  --difficulty medium -o book.pdf
```

**CSV format**: one puzzle per row — first column is the puzzle's title
(leave blank for an auto-numbered "Puzzle 1", "Puzzle 2", ...), remaining
columns are that puzzle's words:

```csv
Animals,TIGER,ELEPHANT,GIRAFFE,DOLPHIN,PENGUIN
Space,MOON,STAR,PLANET,COMET,GALAXY
```

**`--intro`/`--instructions`**: plain text or a tiny markdown subset —
`# Heading`, `## Subheading`, blank-line-separated paragraphs, and `- `/`* `
bullets. Content that overflows one page automatically flows onto the next.
Both are optional; omit either flag to skip that section.

The book is assembled as: title page → intro pages → instructions pages →
one full page per puzzle → an "Answer Keys" divider → 4-up answer key pages
(2×2 mini grids per page, with every solution cell shaded in translucent
gray rather than full color, so it stays legible and print-safe in a
black & white KDP interior). A warning is printed if the assembled book
comes in under KDP's 24-page paperback minimum.

`--csv` accepts the same `--size`, `--difficulty`, `--seed`,
`--no-backwards`, and `--straight-only` flags as single-puzzle mode, applied
to every puzzle in the book.

### Options

| Flag | Description |
| --- | --- |
| `--words-file, -f` | Text file with one word per line |
| `--words, -w` | Comma-separated words (alternative to `-f`) |
| `--words-dir, -d` | Directory of `.txt` word lists; batch-generates a puzzle + answer key per file |
| `--output-dir` | Output directory for `--words-dir` mode (default: `generated_puzzles`) |
| `--format` | Output format for `--words-dir` mode: `png` or `pdf` (default: `png`) |
| `--csv` | CSV of puzzles (one per row); builds a single KDP-ready multi-page book PDF |
| `--intro` | Text/markdown file rendered as the book's introduction page(s) (`--csv` mode) |
| `--instructions` | Text/markdown file rendered as the book's instructions page(s) (`--csv` mode) |
| `--book-title` | Title page text (`--csv` mode; default: the CSV filename) |
| `--author` | Author name on the title page (`--csv` mode) |
| `--difficulty` | `easy`, `medium`, or `hard` preset for size/directions (see above) |
| `--size, -s` | Grid size: `15` (square) or `15x20` (rows x cols) |
| `--output, -o` | Output path — puzzle `.png`/`.pdf` in single-file mode, or the book PDF in `--csv` mode (default: `book.pdf`) |
| `--answer-key, -a` | Optional answer key output path (single-file mode) |
| `--title` | Puzzle title text (single-file/batch mode) |
| `--seed` | Random seed for reproducible puzzles |
| `--no-backwards` | Disallow reversed words |
| `--straight-only` | Only horizontal/vertical placement (no diagonals) |
| `--cell-size` | Pixel size of each grid cell (single-file/batch mode; book mode sizes cells automatically) |

## Word list formatting

- One word per line in a word list file; blank lines are ignored.
- Case doesn't matter — everything is uppercased automatically.
- Non-letter characters (dashes, apostrophes, spaces, digits, punctuation) are
  stripped out before the word is hidden in the grid, e.g. `mother-in-law` is
  placed as `MOTHERINLAW`. The original spelling is preserved in the printed
  "Find these words" list, so it still reads as `MOTHER-IN-LAW`.
- If two entries clean down to the same letters (e.g. `Cat` and `CAT!`), only
  the first is kept.
- A word longer than the grid in both dimensions raises an error; a word that
  just can't find a free spot after many attempts is skipped with a warning.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

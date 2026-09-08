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
- Random filler letters are checked against a profanity blocklist and
  automatically rerolled if they happen to spell something out

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
| `large-print` | 10×10 | horizontal/vertical only, no backwards | 6-10 |

`large-print` is a genuine accessibility preset for `--csv` book mode, not
just "easy" relabeled: on the fixed 8.5×11in page, a smaller grid means much
bigger cells, and every other text element (title, word list, table of
contents) is also scaled up about 35%, so the whole book — not just the
grid — reads large.

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

**CSV format**: a required header row, then one puzzle per row with fixed
columns — title, trivia, then words. The header row's own text is ignored
(it's just skipped), but it must be present. Words always start at the same
column whether or not a given puzzle has trivia, which keeps a spreadsheet's
columns lined up; there's no fixed limit on how many word columns a row can
have, and the header doesn't need a `Word1`/`Word2`/... label for each one —
"Words" (or nothing at all) is enough:

```csv
Title,Trivia,Words
Animals,,TIGER,ELEPHANT,GIRAFFE,DOLPHIN,PENGUIN
Space,,MOON,STAR,PLANET,COMET,GALAXY
```

Leave the title blank for an auto-numbered "Puzzle 1", "Puzzle 2", ....

**Trivia blurbs (optional)**: leave the trivia cell blank if a puzzle
doesn't have one. When present, it's rendered as a "Did You Know?" fact
page facing that puzzle (see below) — one bullet per fact, so you can
write a single theme-level tidbit or one fact per word, whatever fits.
Quote the cell if a fact contains a comma; put a blank line inside the
(quoted) cell to separate multiple facts into their own bullets:

```csv
Animals,"An elephant's trunk has over 40,000 muscles.",TIGER,ELEPHANT,GIRAFFE
```

**`--intro`/`--instructions`**: plain text or a tiny markdown subset —
`# Heading`, `## Subheading`, blank-line-separated paragraphs, and `- `/`* `
bullets. Content that overflows one page automatically flows onto the next.
Both are optional; omit either flag to skip that section.

The book is assembled as: title page → intro pages → instructions pages → a
combined table of contents / progress checklist (a checkbox, number, and
dot-leadered page number per puzzle, so you can both jump to a puzzle and
mark it done in the same list) → one two-page spread per puzzle → an
"Answer Keys" divider → 4-up answer key pages (2×2 mini grids per page,
with every solution cell shaded in translucent gray rather than full
color, so it stays legible and print-safe in a black & white KDP
interior). Every puzzle gets a dedicated left-hand (verso) page immediately
before its own right-hand (recto) page: if that puzzle has a trivia blurb
it's rendered there as a "Did You Know?" fact list facing the puzzle,
otherwise that page is simply left blank. This is deliberate, not a page
count minimization -- it guarantees a puzzle with trivia always has
somewhere to put it, and keeps every puzzle's spread starting in the same
place regardless of what precedes it. The "Answer Keys" divider is
similarly always pushed to a recto page. A warning is printed if the
assembled book comes in under KDP's 24-page paperback minimum.

Each puzzle page is headed "Puzzle N: Title" in a serif heading font with a
rule underneath, matching the title page and section divider, so the book
reads as one designed system rather than a bare grid-plus-list. Grid lines
throughout (including the mini answer keys) are thin gray rather than bold
black, and word lists/paragraphs use a regular-weight font instead of bold,
so headings, body text, and puzzle letters each have their own visual
weight.

Margins are generous since these are pages meant to be written on, not just
read: 1.0in on the inside (gutter) edge, 0.75in outside, 0.75in top, 0.85in
bottom, plus a small extra buffer between the margin and the grid itself.

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
| `--difficulty` | `easy`, `medium`, `hard`, or `large-print` preset for size/directions (see above) |
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

## Blocked-word filter

Since the leftover grid cells are filled with random letters, they can
occasionally spell out something unintended in one of the 8 directions.
After generating each puzzle, the whole grid is scanned (every row, column,
and diagonal, forwards and backwards) against a filtered profanity
wordlist from the [`better-profanity`](https://pypi.org/project/better-profanity/)
package, and the random filler letters are rerolled (the placed words
themselves are never touched) until the grid is clean — this reliably
takes just one or two attempts in practice.

The filter only cares about *accidental* occurrences — a blocklist word
that's simply a substring of a word you deliberately typed (e.g. `ORAL`
inside `CORAL`, or `PECKER` inside `WOODPECKER`) is recognized as
that word's own spelling and ignored, not flagged. It also ignores an
exact match to one of your own chosen words outright (your word list is
your choice, not something this tool second-guesses). What it does still
report — because rerolling filler can't fix it — is the rare case where a
blocked word is assembled from two of your *different* placed words
crossing paths at an intersection; a warning like `could not avoid
blocked word(s) in the grid: ...` means exactly that, and identifies which
puzzle and word so you can adjust your word list if you want to.

Entries shorter than 4 letters are excluded from the blocklist entirely —
short fragments turn up by pure chance in almost any grid of random
letters, so checking them would flag nearly every puzzle for no
meaningful reason.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

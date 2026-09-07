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

### Options

| Flag | Description |
| --- | --- |
| `--words-file, -f` | Text file with one word per line |
| `--words, -w` | Comma-separated words (alternative to `-f`) |
| `--words-dir, -d` | Directory of `.txt` word lists; batch-generates a puzzle + answer key per file |
| `--output-dir` | Output directory for `--words-dir` mode (default: `generated_puzzles`) |
| `--format` | Output format for `--words-dir` mode: `png` or `pdf` (default: `png`) |
| `--size, -s` | Grid size: `15` (square) or `15x20` (rows x cols) |
| `--output, -o` | Puzzle output path, `.png` or `.pdf` (single-file mode) |
| `--answer-key, -a` | Optional answer key output path (single-file mode) |
| `--title` | Puzzle title text |
| `--seed` | Random seed for reproducible puzzles |
| `--no-backwards` | Disallow reversed words |
| `--straight-only` | Only horizontal/vertical placement (no diagonals) |
| `--cell-size` | Pixel size of each grid cell |

## Tests

```bash
pip install -e ".[dev]"
pytest
```

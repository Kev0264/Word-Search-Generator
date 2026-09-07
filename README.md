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

### Options

| Flag | Description |
| --- | --- |
| `--words-file, -f` | Text file with one word per line |
| `--words, -w` | Comma-separated words (alternative to `-f`) |
| `--size, -s` | Grid size: `15` (square) or `15x20` (rows x cols) |
| `--output, -o` | Puzzle output path, `.png` or `.pdf` |
| `--answer-key, -a` | Optional answer key output path |
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

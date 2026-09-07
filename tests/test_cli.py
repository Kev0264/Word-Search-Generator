from pathlib import Path

from word_search.cli import main


def test_batch_mode_generates_puzzle_and_answer_key_per_file(tmp_path):
    words_dir = tmp_path / "word_lists"
    words_dir.mkdir()
    (words_dir / "animals.txt").write_text("TIGER\nLION\nBEAR\n")
    (words_dir / "colors.txt").write_text("RED\nBLUE\nGREEN\n")

    output_dir = tmp_path / "generated_puzzles"

    exit_code = main(
        [
            "--words-dir",
            str(words_dir),
            "--output-dir",
            str(output_dir),
            "--size",
            "10",
            "--seed",
            "1",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "animals_puzzle.png").exists()
    assert (output_dir / "animals_answer_key.png").exists()
    assert (output_dir / "colors_puzzle.png").exists()
    assert (output_dir / "colors_answer_key.png").exists()


def test_batch_mode_reports_error_for_missing_directory(tmp_path, capsys):
    exit_code = main(["--words-dir", str(tmp_path / "does-not-exist")])
    assert exit_code == 1
    assert "not a directory" in capsys.readouterr().err


def test_batch_mode_reports_error_for_empty_directory(tmp_path, capsys):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    exit_code = main(["--words-dir", str(empty_dir)])
    assert exit_code == 1
    assert "no .txt files found" in capsys.readouterr().err.lower()


def test_title_defaults_to_filename(tmp_path):
    words_dir = tmp_path / "word_lists"
    words_dir.mkdir()
    (words_dir / "space_animals.txt").write_text("MOON\nSTAR\n")
    output_dir = tmp_path / "out"

    exit_code = main(
        ["--words-dir", str(words_dir), "--output-dir", str(output_dir), "--size", "10"]
    )

    assert exit_code == 0
    assert (output_dir / "space_animals_puzzle.png").exists()

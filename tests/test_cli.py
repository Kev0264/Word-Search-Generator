from pathlib import Path

from word_search.cli import apply_difficulty, build_parser, main, word_count_warning


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


def test_difficulty_preset_fills_in_size_and_directions():
    parser = build_parser()
    args = parser.parse_args(["--words", "CAT", "--difficulty", "easy"])
    apply_difficulty(args)
    assert args.size == "12"
    assert args.straight_only is True
    assert args.allow_backwards is False


def test_explicit_flags_override_difficulty_preset():
    parser = build_parser()
    args = parser.parse_args(
        ["--words", "CAT", "--difficulty", "easy", "--size", "20", "--no-backwards"]
    )
    apply_difficulty(args)
    # --size was explicit, so it wins over the "easy" preset's "12".
    assert args.size == "20"
    # --no-backwards was explicit too, agreeing with the preset here.
    assert args.allow_backwards is False
    # straight_only wasn't passed explicitly, so the "easy" preset still applies.
    assert args.straight_only is True


def test_no_difficulty_keeps_original_defaults():
    parser = build_parser()
    args = parser.parse_args(["--words", "CAT"])
    apply_difficulty(args)
    assert args.size == "15"
    assert args.straight_only is False
    assert args.allow_backwards is True


def test_word_count_warning_only_fires_with_difficulty():
    assert word_count_warning(None, 50) is None
    assert word_count_warning("easy", 5) is not None
    assert word_count_warning("easy", 50) is not None
    assert word_count_warning("easy", 10) is None


def test_csv_mode_builds_a_book_pdf(tmp_path):
    csv_path = tmp_path / "puzzles.csv"
    csv_path.write_text("Animals,TIGER,LION,BEAR\nColors,RED,BLUE,GREEN\n")
    output_path = tmp_path / "my_book.pdf"

    exit_code = main(
        [
            "--csv",
            str(csv_path),
            "--output",
            str(output_path),
            "--size",
            "10",
            "--seed",
            "1",
        ]
    )

    assert exit_code == 0
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_csv_mode_reports_error_for_missing_file(tmp_path, capsys):
    exit_code = main(["--csv", str(tmp_path / "missing.csv")])
    assert exit_code == 1
    assert "not a file" in capsys.readouterr().err


def test_batch_mode_warns_on_word_count_outside_difficulty_range(tmp_path, capsys):
    words_dir = tmp_path / "word_lists"
    words_dir.mkdir()
    (words_dir / "big.txt").write_text("\n".join(f"WORD{i}" for i in range(30)))
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--words-dir",
            str(words_dir),
            "--output-dir",
            str(output_dir),
            "--difficulty",
            "easy",
        ]
    )

    assert exit_code == 0
    err = capsys.readouterr().err
    assert "big.txt" in err
    assert "easy" in err

from pagegen.cli import main
from pagegen.layout import A4, LETTER, output_path_for


def test_output_path_suffixes_only_when_writing_several_formats():
    assert output_path_for("moon.pdf", LETTER, multiple=False).name == "moon.pdf"
    assert output_path_for("moon.pdf", A4, multiple=True).name == "moon_a4.pdf"
    assert output_path_for("moon", LETTER, multiple=False).name == "moon.pdf"


def test_moon_command_writes_one_pdf_per_paper(tmp_path):
    out = tmp_path / "moon.pdf"
    assert main(["moon", "--year", "2027", "--paper", "letter", "a4", "-o", str(out)]) == 0
    assert (tmp_path / "moon_letter.pdf").is_file()
    assert (tmp_path / "moon_a4.pdf").is_file()


def test_moon_command_rejects_bad_timezone(tmp_path):
    assert (
        main(["moon", "--year", "2027", "--timezone", "Not/AZone", "-o", str(tmp_path / "x.pdf")])
        == 1
    )


def test_moon_strict_fails_on_short_kdp_book(tmp_path):
    out = tmp_path / "book.pdf"
    assert main(["moon", "--year", "2027", "--paper", "kdp", "--strict", "-o", str(out)]) == 1
    assert out.is_file()  # still written


def test_tarot_command(tmp_path, capsys):
    out = tmp_path / "spreads.pdf"
    assert main(["tarot", "--spreads", "daily", "celtic_cross", "-o", str(out)]) == 0
    assert out.is_file()
    assert main(["tarot", "--spreads", "bogus", "-o", str(out)]) == 1
    assert main(["tarot", "--list"]) == 0
    assert "celtic_cross" in capsys.readouterr().out


def test_wordsearch_subcommand_delegates(tmp_path):
    out = tmp_path / "ws.png"
    assert main(["wordsearch", "--words", "MOON,STAR,CANDLE", "--seed", "1", "-o", str(out)]) == 0
    assert out.is_file()


def test_theme_and_grayscale_options(tmp_path):
    out = tmp_path / "plain.pdf"
    assert main(["tarot", "--spreads", "daily", "--theme", "plain", "-o", str(out)]) == 0
    assert out.is_file()
    out = tmp_path / "gray.pdf"
    assert main(["tarot", "--spreads", "daily", "--grayscale", "-o", str(out)]) == 0
    assert out.is_file()

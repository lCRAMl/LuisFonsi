import pytest

from palletizer.cli import main
from palletizer.report import find_browser


def test_cli_list(capsys):
    assert main(["list"]) == 0
    assert "EU36" in capsys.readouterr().out


def test_cli_calc(capsys):
    assert main(["calc", "--pattern", "EU36", "--box", "680x260", "--origin", "2"]) == 0
    out = capsys.readouterr().out
    assert "Variante X" in out and "A.1.3" in out


def test_cli_config_file(tmp_path, capsys):
    config = tmp_path / "job.toml"
    config.write_text('pattern = "EU03"\nbox_length_conv = 580\nbox_width_conv = 390\n',
                      encoding="utf-8")
    assert main(["calc", "--config", str(config)]) == 0
    assert "EU03" in capsys.readouterr().out


def test_cli_error_exit_code(capsys):
    assert main(["calc", "--pattern", "EU99", "--box", "400x300"]) == 1
    assert "FEHLER 103" in capsys.readouterr().out


def test_cli_missing_box(capsys):
    assert main(["calc", "--pattern", "EU03"]) == 2


@pytest.mark.skipif(find_browser() is None, reason="kein Edge/Chrome installiert")
def test_cli_docs(tmp_path, capsys):
    assert main(["docs", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "formelsammlung.pdf").read_bytes().startswith(b"%PDF")


def test_cli_suggest(capsys):
    assert main(["suggest", "--box", "680x260", "--top", "3"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 4 and "EU36" in lines[1]

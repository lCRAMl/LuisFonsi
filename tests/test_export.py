import json
from pathlib import Path

import pytest

from conftest import make_inputs
from palletizer.calculator import calculate
from palletizer.cli import main
from palletizer.export import (ExportOptions, boxes_csv, layer_scl, parse_formats, patterns_scl,
                               run_suite, to_json, write_exports)

PROJECT = Path(__file__).resolve().parents[1]


def test_parse_formats():
    assert parse_formats("json, csv") == {"json", "csv"}
    assert parse_formats("none") == set()
    assert "pdf" in parse_formats("all")
    with pytest.raises(ValueError):
        parse_formats("json,xml")


def test_export_options_from_config():
    options = ExportOptions.from_dict({"json": True, "csv": False, "dir": "x", "csv_decimal": "."})
    assert options.formats == {"json"}
    assert options.out_dir == Path("x")
    assert options.csv_decimal == "."
    with pytest.raises(ValueError):
        ExportOptions.from_dict({"xlsx": True})


def test_only_selected_formats_are_written(library, tmp_path):
    result = calculate(make_inputs("EU36", 680, 260), library)
    written = write_exports(result, ExportOptions(formats={"json", "scl"}, out_dir=tmp_path), library)
    assert sorted(p.name for p in written) == ["EU36_680x260_E1.json", "EU36_680x260_E1.scl"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["EU36_680x260_E1.json", "EU36_680x260_E1.scl"]
    assert write_exports(result, ExportOptions(out_dir=tmp_path / "none"), library) == []
    assert not (tmp_path / "none").exists()


def test_file_name_keeps_decimals(library, tmp_path):
    result = calculate(make_inputs("EU96", 640.5, 200), library)
    written = write_exports(result, ExportOptions(formats={"csv"}, out_dir=tmp_path), library)
    assert written[0].name == "EU96_640.5x200_E1.csv"


def test_csv_decimal_and_delimiter(library):
    result = calculate(make_inputs("EU36", 680, 260), library)
    text = boxes_csv(result, ";", ",")
    lines = text.splitlines()
    assert lines[0].startswith("No;BlockId;Col;Row;X;Y;Rot")
    assert lines[1] == "1;A;1;3;340;660;0;135;-21,2132;21,2132;20;0;0;0"
    assert boxes_csv(result, ",", ".").splitlines()[1].startswith("1,A,1,3,340,660")


def test_json_contains_everything(library):
    data = json.loads(to_json(calculate(make_inputs("EU36", 680, 260), library)))
    assert data["pattern_id"] == "EU36"
    assert len(data["boxes"]) == 5
    assert data["boxes"][0]["key"] == "A.1.3"
    assert data["boxes"][0]["approach"]["mask"] == 0
    assert len(data["variants"]) == 2


def test_layer_scl(library):
    text = layer_scl(calculate(make_inputs("EU36", 680, 260, origin_corner=3), library))
    assert 'TYPE "typPalBox"' in text and 'DATA_BLOCK "DB_PalLayer"' in text
    assert "Boxes : Array[1..100] of \"typPalBox\";" in text
    assert "   Input.PatternNo := 36;" in text
    assert "   Input.OriginCorner := 3;" in text
    assert "   Layer.Boxes[1].X := 860.0000;" in text
    assert "   Layer.Boxes[1].ApproachAngle := 315;" in text
    assert "   Layer.Boxes[2].Warnings := 16#0000;" in text
    assert "   Layer.Boxes[4].NeighborMask := 16#30;" in text
    assert "   Layer.Boxes[5].ExtendPlate := FALSE;" in text
    assert "Layer.Boxes[6]" not in text


def test_patterns_scl(library):
    text = patterns_scl(library)
    assert "   Count := 18;" in text
    assert "   Patterns[18].Id := 'EU96';" in text
    assert "Nicht enthalten (Python-Plugin): EX01" in text


def test_testvectors_match_reference(library, tmp_path):
    """Die abgelegten Testvektoren müssen zum aktuellen Algorithmus passen.

    Schlägt dieser Test nach einer gewollten Änderung fehl:
    `python -m palletizer testvectors` ausführen und die Änderungen im Git-Diff prüfen.
    """
    reference = PROJECT / "examples" / "testvectors"
    run_suite(PROJECT / "examples" / "testvectors.toml", tmp_path, library)
    new_files = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.csv"))
    ref_files = sorted(p.relative_to(reference) for p in reference.rglob("*.csv"))
    assert new_files == ref_files
    for rel in new_files:
        assert (tmp_path / rel).read_text(encoding="utf-8") == \
               (reference / rel).read_text(encoding="utf-8"), rel


def test_cli_export_selection(tmp_path, capsys):
    config = tmp_path / "job.toml"
    config.write_text('pattern = "EU03"\nbox_length_conv = 580\nbox_width_conv = 390\n'
                      '[export]\ncsv = true\njson = true\n', encoding="utf-8")
    out = tmp_path / "out"
    assert main(["calc", "--config", str(config), "--out", str(out)]) == 0
    assert sorted(p.suffix for p in out.iterdir()) == [".csv", ".json"]

    out2 = tmp_path / "out2"
    assert main(["calc", "--config", str(config), "--out", str(out2), "--export", "none"]) == 0
    assert not out2.exists()

    assert main(["calc", "--config", str(config), "--out", str(out2), "--export", "scl",
                 "--name", "auftrag"]) == 0
    assert [p.name for p in out2.iterdir()] == ["auftrag.scl"]

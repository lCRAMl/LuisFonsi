import pytest

from palletizer.patterns import PatternError, PatternLibrary, load_pattern_file

# Kartonanzahl laut PDF
PDF_COUNTS = {
    "EU01": 1, "EU02": 2, "EU03": 4, "EU04": 6, "EU05": 8, "EU06": 2, "EU07": 3,
    "EU09": 9, "EU11": 6, "EU13": 3, "EU15": 7, "EU16": 10, "EU20": 4, "EU26": 5,
    "EU28": 9, "EU29": 5, "EU36": 5, "EU96": 6,
}


def test_all_pdf_patterns_loaded(library):
    for pattern_id, count in PDF_COUNTS.items():
        pattern = library.find(pattern_id)
        assert pattern is not None, pattern_id
        assert pattern.fixed_count == count, pattern_id


def test_find_by_number_and_id(library):
    assert library.find("36").id == "EU36"
    assert library.find(36).id == "EU36"
    assert library.find("eu36").id == "EU36"
    assert library.find("EU99") is None


def test_plugin_pattern_loaded(library):
    pattern = library.find("EX01")
    assert pattern.plugin is not None
    blocks = pattern.build_blocks(600, 200, 0)
    assert len(blocks) == 4
    assert pattern.build_blocks(200, 600, 0) is None   # Arme würden sich überlappen


def test_standard_blocks_top_aligned(library):
    # EU13 mit 600 x 400: Block A 600 x 800, Block B (gedreht) 400 x 600, oben bündig
    blocks = library.find("EU13").build_blocks(600, 400, 0)
    a, b = blocks
    assert (a.x0, a.y0, a.rotated) == (0, 0, False)
    assert (b.x0, b.y0, b.rotated) == (600, 200, True)


def test_duplicate_number_rejected(tmp_path):
    for name in ("P1", "P2"):
        (tmp_path / f"{name}.toml").write_text(
            f'id = "{name}"\nnumber = 1\nname = "x"\nblock_a = {{ cols = 1, rows = 1 }}\n',
            encoding="utf-8")
    with pytest.raises(PatternError):
        PatternLibrary.load(tmp_path)


def test_missing_block_rejected(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text('id = "BAD"\nnumber = 5\nname = "x"\n', encoding="utf-8")
    with pytest.raises(PatternError):
        load_pattern_file(path)

import itertools

import pytest

from conftest import make_inputs
from palletizer.calculator import calculate
from palletizer.constants import (ERR_BOX_SIZE, ERR_ORIGIN_CORNER, ERR_PATTERN_UNKNOWN,
                                  ERR_SEQUENCE_OVERRIDE, ERR_TOO_MANY_BOXES,
                                  WARN_BOX_LARGER_THAN_PALLET, WARN_EXTEND_BLOCKED,
                                  WARN_OVERHANG, WARN_SHORT_SIDE_LEADING)
from palletizer.geometry import rect_overlap
from palletizer.model import Inputs
from palletizer.patterns import PatternLibrary


def test_eu36_full_result(library):
    result = calculate(make_inputs("EU36", 680, 260), library)
    assert result.ok
    assert result.variant == "X"
    assert result.sequence.start_corner == 4        # gegenüber B (links) und Lücke (oben)
    table = [(b.key, b.x, b.y, b.rot, b.approach_angle, b.extend_plate) for b in result.boxes]
    assert table == [
        ("A.1.3", 340, 660, 0, 135, False),
        ("A.1.2", 340, 400, 0, 270, False),
        ("A.1.1", 340, 140, 0, 270, False),
        ("B.1.1", 810, 450, 90, 0, False),
        ("B.2.1", 1070, 450, 90, 0, False),
    ]
    assert result.warnings == 0


def test_eu36_origin_e3(library):
    result = calculate(make_inputs("EU36", 680, 260, origin_corner=3), library)
    first = result.boxes[0]
    assert (first.x, first.y, first.rot, first.approach_angle) == (860, 140, 0, 315)
    assert first.pre_dx == pytest.approx(21.213203)
    assert first.pre_dy == pytest.approx(-21.213203)


def test_gripper_extension_first_box_only(library):
    # EU02 mit 500 (Förderrichtung) x 780 (quer): Karton quer länger als 400 -> ausfahren nötig
    result = calculate(make_inputs("EU02", 500, 780), library)
    assert result.variant == "Y"
    first, second = result.boxes
    assert first.gripper.needed and first.extend_plate
    assert second.gripper.needed and not second.extend_plate
    assert second.warnings & WARN_EXTEND_BLOCKED
    assert first.approach_angle == 180 and second.approach_angle == 0


def test_extension_not_needed_along_conveyor(library):
    # Karton nur in Förderrichtung länger als 600 -> Platte fährt quer aus, hilft nicht
    result = calculate(make_inputs("EU01", 700, 300), library)
    assert not result.boxes[0].gripper.needed


def test_box_larger_than_pallet(library):
    result = calculate(make_inputs("EU01", 1300, 900), library)
    assert result.ok
    box = result.boxes[0]
    assert (box.x, box.y) == (600, 400)
    assert result.warnings & WARN_BOX_LARGER_THAN_PALLET
    assert result.warnings & WARN_OVERHANG


def test_overhang_within_limit_no_warning(library):
    result = calculate(make_inputs("EU96", 640, 205, max_overhang=10), library)
    assert not result.warnings & WARN_OVERHANG
    result = calculate(make_inputs("EU96", 640, 205), library)
    assert result.warnings & WARN_OVERHANG


def test_short_side_leading_hint(library):
    result = calculate(make_inputs("EU36", 260, 680), library)
    assert result.warnings & WARN_SHORT_SIDE_LEADING
    # gleiche Lage wie mit 680 x 260, aber Drehungen vertauscht
    assert [b.rot for b in result.boxes] == [90, 90, 90, 0, 0]


def test_square_box_never_rotated(library):
    result = calculate(make_inputs("EU03", 400, 400), library)
    assert all(b.rot == 0 for b in result.boxes)


@pytest.mark.parametrize("kwargs, code", [
    ({"box_length_conv": 0}, ERR_BOX_SIZE),
    ({"pattern": "EU99"}, ERR_PATTERN_UNKNOWN),
    ({"origin_corner": 5}, ERR_ORIGIN_CORNER),
])
def test_input_errors(library, kwargs, code):
    values = {"pattern": "EU03", "box_length_conv": 400, "box_width_conv": 300} | kwargs
    assert calculate(Inputs(**values), library).error_code == code


def test_too_many_boxes(tmp_path):
    (tmp_path / "big.toml").write_text(
        'id = "BIG"\nnumber = 1\nname = "11x10"\nblock_a = { cols = 11, rows = 10 }\n',
        encoding="utf-8")
    result = calculate(make_inputs("BIG", 50, 50), PatternLibrary.load(tmp_path))
    assert result.error_code == ERR_TOO_MANY_BOXES


def test_sequence_override(tmp_path):
    (tmp_path / "p.toml").write_text(
        'id = "P"\nnumber = 1\nname = "2x1"\nblock_a = { cols = 2, rows = 1 }\n'
        '[sequence]\norder = ["A.2.1", "A.1.1"]\n', encoding="utf-8")
    library = PatternLibrary.load(tmp_path)
    result = calculate(make_inputs("P", 400, 600), library)
    assert [b.key for b in result.boxes] == ["A.2.1", "A.1.1"]

    (tmp_path / "p.toml").write_text(
        'id = "P"\nnumber = 1\nname = "2x1"\nblock_a = { cols = 2, rows = 1 }\n'
        '[sequence]\norder = ["A.2.1"]\n', encoding="utf-8")
    result = calculate(make_inputs("P", 400, 600), PatternLibrary.load(tmp_path))
    assert result.error_code == ERR_SEQUENCE_OVERRIDE


# Kartons, die zum jeweiligen Muster auf der EU-Palette passen (Förderrichtung x quer)
FITTING_BOXES = {
    "EU01": (1100, 700), "EU02": (780, 580), "EU03": (580, 390), "EU04": (400, 300),
    "EU05": (390, 290), "EU06": (1150, 390), "EU07": (780, 390), "EU09": (390, 260),
    "EU11": (590, 260), "EU13": (600, 400), "EU15": (450, 260), "EU16": (390, 230),
    "EU20": (780, 290), "EU26": (450, 300), "EU28": (500, 200), "EU29": (660, 240),
    "EU36": (680, 260), "EU96": (640, 200), "EX01": (500, 250),
}


@pytest.mark.parametrize("pattern_id, corner",
                         list(itertools.product(sorted(FITTING_BOXES), [1, 2, 3, 4])))
def test_all_patterns_all_corners(library, pattern_id, corner):
    conv, cross = FITTING_BOXES[pattern_id]
    result = calculate(make_inputs(pattern_id, conv, cross, origin_corner=corner), library)
    assert result.ok, result.error_code
    pattern = library.find(pattern_id)
    if pattern.fixed_count is not None:
        assert result.box_count == pattern.fixed_count
    assert not result.warnings & WARN_OVERHANG
    assert [b.no for b in result.boxes] == list(range(1, result.box_count + 1))

    for b in result.boxes:
        assert b.rot in (0, 90)
        assert b.approach_angle in range(0, 360, 45)
        # Koordinaten liegen im Ausgabesystem innerhalb der Palette
        assert 0 <= b.x <= 1200 and 0 <= b.y <= 800
        # Rückrechnung auf das Grundsystem ergibt die Grundkoordinaten
        back_x = b.x if corner in (1, 4) else 1200 - b.x
        back_y = b.y if corner in (1, 2) else 800 - b.y
        assert back_x == pytest.approx(b.x_base) and back_y == pytest.approx(b.y_base)

    boxes = result.boxes
    for p, q in itertools.combinations(boxes, 2):
        assert not rect_overlap(p.x_base - p.size_x / 2, p.x_base + p.size_x / 2,
                                p.y_base - p.size_y / 2, p.y_base + p.size_y / 2,
                                q.x_base - q.size_x / 2, q.x_base + q.size_x / 2,
                                q.y_base - q.size_y / 2, q.y_base + q.size_y / 2, 0.1)


def test_result_independent_of_corner_in_base_system(library):
    """Das Muster ist physikalisch fest: Grundkoordinaten hängen nicht vom Nullpunkt ab,
    nur die Startecke der Ablage kann sich bei Mustern ohne Lücke ändern."""
    base = calculate(make_inputs("EU36", 680, 260, origin_corner=1), library)
    other = calculate(make_inputs("EU36", 680, 260, origin_corner=3), library)
    assert [(b.key, b.x_base, b.y_base) for b in base.boxes] == \
           [(b.key, b.x_base, b.y_base) for b in other.boxes]

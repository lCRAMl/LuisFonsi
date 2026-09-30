from conftest import make_inputs
from palletizer.layout import build_variant, choose_variant


def test_eu36_positions(library):
    inp = make_inputs("EU36", 680, 260)
    layout = build_variant(library.find("EU36"), "X", inp)
    assert layout.valid
    assert (layout.layer_size_x, layout.layer_size_y) == (1200, 780)
    centers = {box.key: (box.cx, box.cy, box.rot) for box in layout.boxes}
    assert centers == {
        "A.1.1": (340, 140, 0),
        "A.1.2": (340, 400, 0),
        "A.1.3": (340, 660, 0),
        "B.1.1": (810, 450, 90),
        "B.2.1": (1070, 450, 90),
    }
    assert layout.overhang_sum == 0
    assert layout.rotated_count == 2


def test_orientation_less_overhang_wins(library):
    inp = make_inputs("EU36", 680, 260)
    pattern = library.find("EU36")
    vx = build_variant(pattern, "X", inp)
    vy = build_variant(pattern, "Y", inp)
    chosen, reason = choose_variant(vx, vy, inp, pattern.drawn_long_side)
    assert chosen.name == "X"
    assert reason == "weniger Überstand"


def test_orientation_fewer_rotations_wins(library):
    # EU04 mit 400 x 300: beide Varianten passen ohne Überstand
    pattern = library.find("EU04")
    inp = make_inputs("EU04", 400, 300)     # Langseite in Förderrichtung
    vx, vy = build_variant(pattern, "X", inp), build_variant(pattern, "Y", inp)
    assert vx.overhang_sum == vy.overhang_sum == 0
    chosen, _ = choose_variant(vx, vy, inp, pattern.drawn_long_side)
    assert chosen.name == "X" and chosen.rotated_count == 0

    inp = make_inputs("EU04", 300, 400)     # Kurzseite in Förderrichtung
    vx, vy = build_variant(pattern, "X", inp), build_variant(pattern, "Y", inp)
    chosen, _ = choose_variant(vx, vy, inp, pattern.drawn_long_side)
    assert chosen.name == "Y" and chosen.rotated_count == 0


def test_orientation_manual_override(library):
    pattern = library.find("EU36")
    inp = make_inputs("EU36", 680, 260, orientation_mode=2)
    vx, vy = build_variant(pattern, "X", inp), build_variant(pattern, "Y", inp)
    chosen, _ = choose_variant(vx, vy, inp, pattern.drawn_long_side)
    assert chosen.name == "Y"


def test_gap_is_applied(library):
    inp = make_inputs("EU03", 590, 390, gap=10)
    layout = build_variant(library.find("EU03"), "X", inp)
    assert (layout.layer_size_x, layout.layer_size_y) == (1190, 790)
    xs = sorted({box.cx for box in layout.boxes})
    assert xs == [5 + 295, 5 + 590 + 10 + 295]


def test_overhang_eu96(library):
    # SKU aus dem PDF: 64 x 20,5 cm -> 4 Reihen = 820 mm auf 800 mm
    inp = make_inputs("EU96", 640, 205)
    layout = build_variant(library.find("EU96"), "X", inp)
    assert layout.layer_size_y == 820
    assert layout.overhang_y == 10

from conftest import make_inputs
from palletizer.approach import choose_approach, free_mask, neighbor_mask
from palletizer.model import Box


def box(cx, cy, sx=200, sy=100):
    return Box("A", 1, 1, cx, cy, sx, sy, 0)


INP = make_inputs("EU01", 200, 100, approach_dist=30)


def test_free_mask_diagonal_needs_both_sides():
    mask = 1 << 4                      # nur West belegt
    free = free_mask(mask)
    assert not free & (1 << 4)         # West blockiert
    assert not free & (1 << 3)         # Nordwest blockiert (braucht West frei)
    assert not free & (1 << 5)         # Südwest blockiert
    assert free & (1 << 0) and free & (1 << 1) and free & (1 << 7)


def test_mask_detects_edge_and_corner_neighbors():
    target = box(300, 300)                         # x 200..400, y 250..350
    west = box(100, 300)                           # berührt links
    south_west = box(100, 200)                     # berührt nur die Ecke links unten
    mask = neighbor_mask(target, [west, south_west], 30, 0.1)
    assert mask == (1 << 4) | (1 << 5)


def test_far_neighbor_not_detected():
    target = box(300, 300)
    far = box(100 - 50, 300)                       # 50 mm Abstand > 30 mm Prüftiefe
    assert neighbor_mask(target, [far], 30, 0.1) == 0


def test_slides_into_corner():
    target = box(300, 300)
    west, south = box(100, 300), box(300, 200)
    info = choose_approach(target, [west, south], INP)
    assert info.angle == 45                        # kommt von Nordost


def test_single_neighbor_opposite_side():
    target = box(300, 300)
    info = choose_approach(target, [box(300, 400)], INP)   # Nachbar im Norden
    assert info.angle == 270


def test_no_neighbors_uses_outward_direction():
    # Karton links unten auf der Palette -> von außen (Südwest) anfahren
    info = choose_approach(box(100, 50), [], INP)
    assert info.used_outward
    assert info.angle == 225


def test_enclosed_box_reports_no_free_direction():
    target = box(300, 300)
    ring = [box(100, 300), box(500, 300), box(300, 400), box(300, 200)]
    info = choose_approach(target, ring, INP)
    assert info.no_free

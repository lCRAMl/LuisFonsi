from conftest import make_inputs
from palletizer.assistant import suggest


def test_best_pattern_for_eu36_box(library):
    suggestions = suggest(library, make_inputs("", 680, 260))
    assert suggestions[0].pattern_id == "EU36"
    assert suggestions[0].fits and suggestions[0].box_count == 5
    # alle passenden Muster stehen vor den unpassenden
    fits = [s.fits for s in suggestions]
    assert fits == sorted(fits, reverse=True)


def test_best_pattern_fills_pallet(library):
    best = suggest(library, make_inputs("", 400, 300))[0]
    assert best.pattern_id == "EU05"
    assert best.result.area_usage == 100.0


def test_allowed_overhang_changes_fit(library):
    strict = {s.pattern_id: s.fits for s in suggest(library, make_inputs("", 640, 205))}
    loose = {s.pattern_id: s.fits for s in suggest(library, make_inputs("", 640, 205, max_overhang=10))}
    assert not strict["EU96"] and loose["EU96"]

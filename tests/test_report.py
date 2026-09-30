import json
import re

import pytest

from conftest import make_inputs
from palletizer.calculator import calculate
from palletizer.report import build_report, find_browser, html_to_pdf
from palletizer.viz import render_layer, zone_names


def test_report_contains_all_sections(library):
    html = build_report(calculate(make_inputs("EU36", 680, 260, origin_corner=3), library))
    for text in ("Lagenbild", "Ausgabe an die SPS", "Variantenvergleich",
                 "Ablage Schritt für Schritt", "Rechenweg", "S8 · Umrechnung"):
        assert text in html
    # Rechenweg mit eingesetzten Zahlen: Spiegelung von Karton 1 auf E3
    assert "-1·(340.0 − 1200) = <b>860.0</b>" in html


def test_report_box_data_is_valid_json(library):
    html = build_report(calculate(make_inputs("EU15", 450, 260), library))
    raw = re.search(r'<script type="application/json" id="box-data">(.*?)</script>', html, re.S)
    data = json.loads(raw.group(1).replace("<\\/", "</"))
    assert [d["no"] for d in data] == list(range(1, 8))


def test_report_for_error(library):
    html = build_report(calculate(make_inputs("EU99", 400, 300), library))
    assert "Fehler 103" in html


def test_svg_has_one_group_per_box(library):
    result = calculate(make_inputs("EU05", 390, 290), library)
    svg = render_layer(result)
    assert svg.count('class="box ') == 8
    assert svg.count('class="zones') == 8


def test_zone_names():
    assert zone_names(0) == "–"
    assert zone_names(0b00110000) == "W, SW"


@pytest.mark.skipif(find_browser() is None, reason="kein Edge/Chrome installiert")
def test_pdf_export(library, tmp_path):
    html_path = tmp_path / "r.html"
    html_path.write_text(build_report(calculate(make_inputs("EU03", 580, 390), library)),
                         encoding="utf-8")
    pdf = html_to_pdf(html_path, tmp_path / "r.pdf")
    assert pdf.read_bytes().startswith(b"%PDF")

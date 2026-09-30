"""HTML-Report einer berechneten Lage (eine Datei, keine externen Abhängigkeiten).

Inhalt:
    1. Lagenbild mit Schritt-für-Schritt-Steuerung und Detailanzeige je Karton
    2. Ausgabe an die SPS (Tabelle)
    3. Variantenvergleich (Orientierung X / Y)
    4. Ablage Schritt für Schritt (kleine Bilder, auch für den Druck)
    5. Rechenweg mit eingesetzten Zahlen (Stufen S0-S8)
"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape

from .. import __version__
from ..constants import (DIR_X, DIR_Y, ERROR_TEXTS, WARNING_TEXTS, warning_texts)
from ..gripper import extension_needed, plate_size
from ..model import BoxResult, Inputs, LayerResult
from ..transform import CORNER_SIGNS, corner_point
from ..viz.svg import ZONE_NAMES, render_layer, render_variant, zone_names

CORNER_NAMES = {1: "E1 (unten links)", 2: "E2 (unten rechts)",
                3: "E3 (oben rechts)", 4: "E4 (oben links)"}
MAX_STEP_IMAGES = 30   # darüber entfällt der Abschnitt "Schritt für Schritt"

INPUT_LABELS = [
    ("pattern", "Layerpattern", ""),
    ("box_length_conv", "Karton in Förderrichtung", "mm"),
    ("box_width_conv", "Karton quer zur Förderrichtung", "mm"),
    ("pallet_length", "Palette Länge (X)", "mm"),
    ("pallet_width", "Palette Breite (Y)", "mm"),
    ("origin_corner", "Palettennullpunkt", ""),
    ("orientation_mode", "Orientierung (0 auto, 1 X, 2 Y)", ""),
    ("gap", "Spaltmaß", "mm"),
    ("max_overhang", "erlaubter Überstand je Seite", "mm"),
    ("plate_conv", "Saugplatte in Förderrichtung", "mm"),
    ("plate_cross", "Saugplatte quer", "mm"),
    ("plate_ext_conv", "ausgefahren in Förderrichtung", "mm"),
    ("plate_ext_cross", "ausgefahren quer", "mm"),
    ("approach_dist", "Vorposition Abstand X/Y", "mm"),
    ("approach_height", "Vorposition Höhe Z", "mm"),
    ("tolerance", "Toleranz ε", "mm"),
]


def f1(value: float) -> str:
    """Zahl mit einer Nachkommastelle, ohne "-0.0"."""
    text = f"{value:.1f}"
    return "0.0" if text == "-0.0" else text


def f2(value: float) -> str:
    text = f"{value:.2f}"
    return "0.00" if text == "-0.00" else text


def yes_no(flag: bool) -> str:
    return "ja" if flag else "nein"


def build_report(result: LayerResult, header: bool = True) -> str:
    """Erzeugt den kompletten HTML-Report als Text.

    header=False lässt Titel und Kennzahlen weg (z. B. eingebettet in die Oberfläche).
    """
    inp = result.inputs
    title = f"Palettierung {result.pattern_id or inp.pattern}"
    body = [_header(result)] if header else []
    if not result.ok:
        body.append(f'<section><p class="error">⛔ Fehler {result.error_code}: '
                    f'{escape(ERROR_TEXTS.get(result.error_code, "?"))}</p>'
                    f'{_inputs_table(inp)}</section>')
    else:
        body += [
            _section_layer(result),
            _section_table(result),
            _section_variants(result),
            _section_steps(result),
            _section_calculation(result),
        ]
    return _page(title, "\n".join(body), _box_data(result) if result.ok else "[]")


# --- Kopf und Kennzahlen ------------------------------------------------------

def _header(result: LayerResult) -> str:
    inp = result.inputs
    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    head = (f'<header><h1>Palettierung {escape(result.pattern_id or str(inp.pattern))}'
            f'{" · " + escape(result.pattern_name) if result.pattern_name else ""}</h1>'
            f'<p class="sub">Karton {inp.box_length_conv:g} × {inp.box_width_conv:g} mm '
            f'(Förderrichtung × quer) · Palette {inp.pallet_length:g} × {inp.pallet_width:g} mm · '
            f'Nullpunkt {CORNER_NAMES.get(inp.origin_corner, inp.origin_corner)} · '
            f'erstellt {stamp} · palletizer {__version__}</p>')
    if not result.ok:
        return head + "</header>"

    count_warn = len(warning_texts(result.warnings))
    if count_warn:
        warn_tile = (f'<div class="tile warn"><span class="k">Warnungen</span>'
                     f'<span class="v">⚠ {count_warn}</span></div>')
    else:
        warn_tile = ('<div class="tile ok"><span class="k">Warnungen</span>'
                     '<span class="v">✓ keine</span></div>')
    tiles = [
        ("Kartons", str(result.box_count)),
        ("davon gedreht", str(result.rotated_count)),
        ("Variante", result.variant),
        ("Lagenmaß", f"{f1(result.layer_size_x)} × {f1(result.layer_size_y)}"),
        ("Überstand je Seite X / Y", f"{f1(result.overhang_x)} / {f1(result.overhang_y)}"),
        ("Flächennutzung", f"{result.area_usage:.1f} %"),
    ]
    tiles_html = "".join(f'<div class="tile"><span class="k">{escape(k)}</span>'
                         f'<span class="v">{escape(v)}</span></div>' for k, v in tiles)
    notes = ""
    texts = warning_texts(result.warnings)
    if texts:
        notes = '<ul class="warnings">' + "".join(f"<li>⚠ {escape(t)}</li>" for t in texts) + "</ul>"
    return head + f'<div class="tiles">{tiles_html}{warn_tile}</div>{notes}</header>'


# --- 1. Lagenbild -------------------------------------------------------------

def _section_layer(result: LayerResult) -> str:
    svg = render_layer(result, prefix="main", step=None, interactive=True)
    legend = """
<ul class="legend">
  <li><span class="sw rot0"></span>0° – wie auf dem Förderband</li>
  <li><span class="sw rot90"></span>90° gedreht</li>
  <li><span class="sym">➜</span>Anfahrrichtung (Karton kommt aus Pfeilrichtung)</li>
  <li><span class="line dash"></span>Förderachse des Kartons</li>
  <li><span class="line block"></span>Blockgrenze</li>
  <li><span class="sw over"></span>⚠ Überstand</li>
  <li><span class="sym">●</span>Palettennullpunkt mit Achsen X / Y</li>
  <li class="screen"><span class="sw zone"></span>belegte Prüfzone (gewählter Karton)</li>
  <li class="screen"><span class="line pre"></span>Vorposition (gewählter Karton)</li>
  <li class="screen"><span class="line plate"></span>Grundplatte · <span class="line ext"></span>ausgefahren
    · <span class="line blocked"></span>ausfahren blockiert</li>
</ul>"""
    controls = f"""
<div class="controls">
  <button type="button" id="btn-prev" aria-label="vorheriger Karton">◀</button>
  <input type="range" id="step" min="1" max="{result.box_count}" value="{result.box_count}"
         aria-label="Ablageschritt">
  <button type="button" id="btn-next" aria-label="nächster Karton">▶</button>
  <button type="button" id="btn-all">Gesamtansicht</button>
  <span id="step-label">Gesamtansicht</span>
  <label><input type="checkbox" id="show-zones" checked> Prüfzonen</label>
  <label><input type="checkbox" id="show-plates" checked> Saugplatte</label>
  <label><input type="checkbox" id="show-blocks" checked> Blöcke</label>
</div>"""
    panel = ('<aside id="panel" class="panel"><p class="hint">Karton anklicken oder Schritt '
             'wählen, um die Berechnung für diesen Karton zu sehen.</p></aside>')
    return (f'<section class="first"><h2>Lagenbild</h2>{controls}'
            f'<div class="layer-grid"><div class="drawing">{svg}</div>{panel}</div>{legend}</section>')


# --- 2. Ausgabe an die SPS ----------------------------------------------------

def _section_table(result: LayerResult) -> str:
    rows = []
    for b in result.boxes:
        warn = "; ".join(warning_texts(b.warnings)) or "–"
        cls = ' class="warnrow"' if b.warnings else ""
        rows.append(
            f'<tr data-no="{b.no}"{cls}><td>{b.no}</td><td>{escape(b.key)}</td>'
            f'<td class="n">{f1(b.x)}</td><td class="n">{f1(b.y)}</td><td class="n">{b.rot}</td>'
            f'<td class="n">{b.approach_angle}</td><td class="n">{f1(b.pre_dx)}</td>'
            f'<td class="n">{f1(b.pre_dy)}</td><td class="n">{f1(b.pre_dz)}</td>'
            f'<td class="n">{int(b.extend_plate)}</td><td class="mono">{b.neighbor_mask:08b}</td>'
            f'<td class="n">{b.warnings}</td><td>{escape(warn)}</td></tr>')
    return f"""
<section><h2>Ausgabe an die SPS</h2>
<p>Koordinaten bezogen auf den Palettennullpunkt {CORNER_NAMES[result.inputs.origin_corner]},
Kartonmittelpunkt in mm. Anfahrt = Richtung, aus der der Karton kommt; Vorposition = Ziel + (dX, dY, dZ).</p>
<table class="data" id="box-table">
<thead><tr><th>Nr</th><th>Karton</th><th>X</th><th>Y</th><th>Rot</th><th>Anfahrt °</th>
<th>dX</th><th>dY</th><th>dZ</th><th>Ausfahren</th><th>Maske</th><th>Warnbits</th><th>Warnungen</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></section>"""


# --- 3. Variantenvergleich -----------------------------------------------------

def _section_variants(result: LayerResult) -> str:
    inp = result.inputs
    cards = []
    for layout in result.variants:
        chosen = layout.name == result.variant
        long_axis = "X" if layout.name == "X" else "Y"
        if layout.valid:
            drawing = render_variant(layout, inp, chosen)
            facts = (f"Lagenmaß {f1(layout.layer_size_x)} × {f1(layout.layer_size_y)} mm<br>"
                     f"Überstand gesamt {f1(layout.overhang_sum)} mm<br>"
                     f"{layout.rotated_count} von {layout.count} Kartons gedreht")
        else:
            drawing = '<p class="hint">In dieser Orientierung nicht darstellbar.</p>'
            facts = ""
        badge = '<span class="badge">gewählt</span>' if chosen else ""
        cards.append(f'<div class="card{" chosen" if chosen else ""}"><h3>Variante {layout.name} '
                     f'{badge}</h3><p class="sub">Block A mit der Langseite in {long_axis}</p>'
                     f'{drawing}<p>{facts}</p></div>')
    return f"""
<section><h2>Variantenvergleich</h2>
<p>Gewählt: <b>Variante {result.variant}</b> – {escape(result.variant_reason)}.
Rangfolge: 1. weniger Überstand, 2. weniger gedrehte Kartons, 3. Orientierung laut Zeichnung.</p>
<div class="cards">{"".join(cards)}</div></section>"""


# --- 4. Schritt für Schritt ----------------------------------------------------

def _section_steps(result: LayerResult) -> str:
    if result.box_count > MAX_STEP_IMAGES:
        return ""
    items = []
    for b in result.boxes:
        svg = render_layer(result, prefix=f"step{b.no}", step=b.no, interactive=False, compact=True)
        items.append(f'<figure>{svg}<figcaption>{b.no}: {escape(b.key)} · Anfahrt '
                     f'{b.approach_angle}°{" · ausfahren" if b.extend_plate else ""}</figcaption></figure>')
    return (f'<section><h2>Ablage Schritt für Schritt</h2>'
            f'<p>Hervorgehoben ist der jeweils abgelegte Karton, gestrichelt die noch freien Plätze. '
            f'Winkel im Ausgabesystem.</p><div class="steps">{"".join(items)}</div></section>')


# --- 5. Rechenweg -----------------------------------------------------------------

def _section_calculation(result: LayerResult) -> str:
    inp = result.inputs
    parts = ['<section><h2>Rechenweg</h2>'
             '<p>Alle Stufen mit den Zahlen dieses Auftrags. Koordinaten im Grundsystem '
             '(E1 unten links, X nach rechts, Y nach oben), bis zur Umrechnung in Stufe S8.</p>']
    parts.append(f"<h3>S0 · Eingaben</h3>{_inputs_table(inp)}"
                 f'<p>Eingabeprüfung: Fehlercode {result.error_code} (OK).</p>')
    parts.append(_calc_s1(result))
    parts.append(_calc_s2_s4(result))
    parts.append(_calc_s5(result))
    parts.append(_calc_s6(result))
    parts.append(_calc_s7(result))
    parts.append(_calc_s8(result))
    parts.append(_calc_warnings(result))
    parts.append("</section>")
    return "\n".join(parts)


def _inputs_table(inp: Inputs) -> str:
    rows = []
    for key, label, unit in INPUT_LABELS:
        value = getattr(inp, key)
        if key == "origin_corner":
            value = CORNER_NAMES.get(value, value)
        rows.append(f"<tr><td>{escape(label)}</td><td class='mono'>{key}</td>"
                    f"<td class='n'>{escape(str(value))}</td><td>{unit}</td></tr>")
    return ('<table class="data inputs"><thead><tr><th>Größe</th><th>Bezeichner</th>'
            f'<th>Wert</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table>')


def _calc_s1(result: LayerResult) -> str:
    inp = result.inputs
    note = ""
    if inp.box_length_conv < inp.box_width_conv - inp.tolerance:
        note = "<p>⚠ Hinweis: Der Karton kommt mit der Kurzseite voran.</p>"
    return f"""
<h3>S1 · Lang- und Kurzseite</h3>
<div class="formula">
l = max(a<sub>F</sub>, b<sub>F</sub>) = max({inp.box_length_conv:g}, {inp.box_width_conv:g}) = <b>{result.box_long:g}</b><br>
k = min(a<sub>F</sub>, b<sub>F</sub>) = min({inp.box_length_conv:g}, {inp.box_width_conv:g}) = <b>{result.box_short:g}</b>
</div>{note}"""


def _calc_s2_s4(result: LayerResult) -> str:
    inp = result.inputs
    g = inp.gap
    rows = []
    for layout in result.variants:
        px, py = (result.box_long, result.box_short) if layout.name == "X" else \
                 (result.box_short, result.box_long)
        if layout.valid:
            rows.append(f"<tr><td>{layout.name}</td><td class='n'>{px:g} × {py:g}</td>"
                        f"<td class='n'>{f1(layout.layer_size_x)} × {f1(layout.layer_size_y)}</td>"
                        f"<td class='n'>max(0, {f1(layout.layer_size_x)} − {inp.pallet_length:g}) + "
                        f"max(0, {f1(layout.layer_size_y)} − {inp.pallet_width:g}) = "
                        f"<b>{f1(layout.overhang_sum)}</b></td>"
                        f"<td class='n'>{layout.rotated_count}</td></tr>")
        else:
            rows.append(f"<tr><td>{layout.name}</td><td class='n'>{px:g} × {py:g}</td>"
                        f"<td colspan='3'>nicht darstellbar</td></tr>")

    layout = result.chosen_layout
    block_rows = []
    for block in layout.blocks:
        block_rows.append(
            f"<tr><td>{escape(block.id)}</td><td class='n'>{block.cols}</td><td class='n'>{block.rows}</td>"
            f"<td>{yes_no(block.rotated)}</td><td class='n'>{block.size_x:g}</td><td class='n'>{block.size_y:g}</td>"
            f"<td class='n'>{block.cols}·{block.size_x:g} + {block.cols - 1}·{g:g} = {f1(block.width)}</td>"
            f"<td class='n'>{block.rows}·{block.size_y:g} + {block.rows - 1}·{g:g} = {f1(block.height)}</td>"
            f"<td class='n'>{f1(block.x0)}</td><td class='n'>{f1(block.y0)}</td></tr>")

    e_x = (inp.pallet_length - layout.layer_size_x) / 2
    e_y = (inp.pallet_width - layout.layer_size_y) / 2
    first = result.boxes[0]
    block = next(b for b in layout.blocks if b.id == first.block_id)
    i, j = first.col - 1, first.row - 1
    return f"""
<h3>S2–S4 · Blockliste, Positionen, Variante</h3>
<p>Beide Orientierungen werden vollständig berechnet. Variante X: Block A mit der Langseite in X,
(p<sub>x</sub>, p<sub>y</sub>) = (l, k); Variante Y: (p<sub>x</sub>, p<sub>y</sub>) = (k, l).
Gedrehte Blöcke verwenden (p<sub>y</sub>, p<sub>x</sub>).</p>
<table class="data"><thead><tr><th>Variante</th><th>(p<sub>x</sub>, p<sub>y</sub>)</th>
<th>Lagenmaß W<sub>X</sub> × W<sub>Y</sub></th><th>Überstand Ü</th><th>gedreht</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<p>Gewählt: <b>Variante {result.variant}</b> ({escape(result.variant_reason)}).</p>

<p>Blockliste der gewählten Variante (Ecke x0/y0 nach dem Zentrieren).
Blockmaß D(n, a) = n·a + (n − 1)·g:</p>
<table class="data"><thead><tr><th>Block</th><th>Spalten</th><th>Reihen</th><th>gedreht</th>
<th>a (X)</th><th>c (Y)</th><th>Breite D</th><th>Höhe D</th><th>x0</th><th>y0</th></tr></thead>
<tbody>{"".join(block_rows)}</tbody></table>

<p>Zentrieren und Überstand:</p>
<div class="formula">
e<sub>X</sub> = (L<sub>P</sub> − W<sub>X</sub>) / 2 = ({inp.pallet_length:g} − {f1(layout.layer_size_x)}) / 2 = <b>{f1(e_x)}</b><br>
e<sub>Y</sub> = (B<sub>P</sub> − W<sub>Y</sub>) / 2 = ({inp.pallet_width:g} − {f1(layout.layer_size_y)}) / 2 = <b>{f1(e_y)}</b><br>
Überstand je Seite: X = max(0, −e<sub>X</sub>) = <b>{f1(result.overhang_x)}</b>,
Y = max(0, −e<sub>Y</sub>) = <b>{f1(result.overhang_y)}</b>
</div>
<p>Kartonmittelpunkt (Beispiel: Karton {first.no} = {escape(first.key)}, Spalte i = {i}, Reihe j = {j}, ab 0 gezählt):</p>
<div class="formula">
x = x0 + i·(a + g) + a/2 = {f1(block.x0)} + {i}·({block.size_x:g} + {g:g}) + {block.size_x:g}/2 = <b>{f1(first.x_base)}</b><br>
y = y0 + j·(c + g) + c/2 = {f1(block.y0)} + {j}·({block.size_y:g} + {g:g}) + {block.size_y:g}/2 = <b>{f1(first.y_base)}</b><br>
Rot = 0, wenn a = a<sub>F</sub> und c = b<sub>F</sub> (Förderrichtung parallel X), sonst 90 → <b>{first.rot}</b>
</div>"""


def _calc_s5(result: LayerResult) -> str:
    inp = result.inputs
    seq = result.sequence
    layout = result.chosen_layout
    cx, cy = inp.pallet_length / 2, inp.pallet_width / 2
    area_layer = layout.layer_size_x * layout.layer_size_y
    loose = (f"{seq.loose_count} Kartons, Schwerpunkt ({f1(seq.loose_cx)}, {f1(seq.loose_cy)})"
             if seq.loose_count else "keiner (alle Blöcke gleich groß)")
    if seq.gap_area > inp.tolerance * (layout.layer_size_x + layout.layer_size_y):
        gap = (f"A<sub>Lücke</sub> = W<sub>X</sub>·W<sub>Y</sub> − ΣA<sub>i</sub> = "
               f"{f1(area_layer)} − {f1(area_layer - seq.gap_area)} = <b>{f1(seq.gap_area)}</b> mm², "
               f"Schwerpunkt ({f1(seq.gap_cx)}, {f1(seq.gap_cy)})")
    else:
        gap = "keine Lücke"
    block_order = []
    for b in result.boxes:
        if b.block_id not in block_order:
            block_order.append(b.block_id)
    order = " → ".join(escape(b.key) for b in result.boxes)
    return f"""
<h3>S5 · Ablagereihenfolge</h3>
<p>Regel „dichter Teil zuerst“: Blöcke mit mehr Kartons zuerst; Startecke X-seitig gegenüber dem
lockeren Teil, Y-seitig gegenüber der Lücke; innerhalb eines Blocks spaltenweise von der Startecke weg.</p>
<div class="formula">
Lagenmitte = Palettenmitte = ({f1(cx)}, {f1(cy)})<br>
Lockerer Teil (Blöcke mit weniger Kartons): {loose}<br>
Lücke: {gap}<br>
X-Seite: {escape(seq.source_x)} · Y-Seite: {escape(seq.source_y)}<br>
Startecke: <b>{CORNER_NAMES[seq.start_corner]}</b> · Blockfolge: {" → ".join(block_order)}
</div>
<p>Reihenfolge: {order}</p>"""


def _calc_s6(result: LayerResult) -> str:
    inp = result.inputs
    rows = []
    for b in result.boxes:
        a = b.approach
        free = [ZONE_NAMES[k] for k in range(8) if a.free & (1 << k)]
        remark = []
        if a.used_outward:
            remark.append("keine Nachbarn → von außen")
        if a.no_free:
            remark.append("⚠ keine Richtung frei")
        rows.append(
            f"<tr><td>{b.no}</td><td>{escape(b.key)}</td><td class='mono'>{a.mask:08b}</td>"
            f"<td>{zone_names(a.mask)}</td><td>{', '.join(free) or '–'}</td>"
            f"<td class='n'>({f2(a.vx)}, {f2(a.vy)})</td>"
            f"<td class='n'>{b.approach_angle_base}° ({ZONE_NAMES[a.direction]})</td>"
            f"<td class='n'>{b.approach_angle}°</td><td>{'; '.join(remark) or '–'}</td></tr>")
    return f"""
<h3>S6 · Annäherungsrichtung</h3>
<p>Um jeden Karton liegen 8 Prüfzonen der Tiefe s = {inp.approach_dist:g} mm. Eine Zone ist belegt,
wenn ein <i>bereits abgelegter</i> Karton sie mit einer Fläche &gt; ε überlappt (Bit k = Richtung k·45°,
Bit 0 = Ost). Eine gerade Richtung ist frei, wenn ihre Zone frei ist; eine Diagonale zusätzlich nur,
wenn beide Nachbarzonen frei sind.</p>
<div class="formula">
v = − Σ u<sub>k</sub> über alle belegten Zonen, u<sub>k</sub> = (cos k·45°, sin k·45°)<br>
Ist v = 0: v = w = normierter Vektor Palettenmitte → Karton (von außen anfahren)<br>
Gewählt: freie Richtung mit größtem u<sub>k</sub>·v, dann größtem u<sub>k</sub>·w, dann Rangfolge 45°, 135°, 225°, 315°, 0°, 90°, 180°, 270°<br>
Vorposition = Ziel + s·u<sub>k</sub> + (0, 0, {inp.approach_height:g})
</div>
<table class="data"><thead><tr><th>Nr</th><th>Karton</th><th>Maske</th><th>belegt</th><th>frei</th>
<th>v</th><th>Winkel Grundsystem</th><th>Winkel Ausgabe</th><th>Bemerkung</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>"""


def _calc_s7(result: LayerResult) -> str:
    inp = result.inputs
    tol = inp.tolerance
    checks = []
    if inp.plate_ext_cross > inp.plate_cross + tol:
        checks.append(f"quer: b<sub>F</sub> = {inp.box_width_conv:g} &gt; {inp.plate_cross:g} → "
                      f"{yes_no(inp.box_width_conv > inp.plate_cross + tol)}")
    if inp.plate_ext_conv > inp.plate_conv + tol:
        checks.append(f"in Förderrichtung: a<sub>F</sub> = {inp.box_length_conv:g} &gt; {inp.plate_conv:g} → "
                      f"{yes_no(inp.box_length_conv > inp.plate_conv + tol)}")
    needed = extension_needed(inp)
    rows = []
    for b in result.boxes:
        px, py = plate_size(b.rot, inp.plate_conv, inp.plate_cross)
        ex, ey = plate_size(b.rot, inp.plate_ext_conv, inp.plate_ext_cross)
        gr = b.gripper
        rows.append(f"<tr><td>{b.no}</td><td>{escape(b.key)}</td><td class='n'>{b.rot}</td>"
                    f"<td class='n'>{px:g} × {py:g}</td><td class='n'>{ex:g} × {ey:g}</td>"
                    f"<td>{yes_no(gr.needed)}</td><td>{yes_no(gr.allowed)}</td>"
                    f"<td class='n'><b>{int(gr.extend)}</b></td></tr>")
    return f"""
<h3>S7 · Saugplatte</h3>
<p>Die Platte sitzt mittig auf dem Karton und dreht sich mit ihm (Grundplatte
{inp.plate_conv:g} in × {inp.plate_cross:g} quer zur Förderrichtung, ausgefahren
{inp.plate_ext_conv:g} × {inp.plate_ext_cross:g}).</p>
<div class="formula">
nötig = Karton in einer Ausfahrachse länger als die Grundplatte: {"; ".join(checks) or "Platte fährt nicht aus"} → <b>{yes_no(needed)}</b><br>
erlaubt = ausgefahrene Platte überdeckt keinen bereits abgelegten Karton<br>
Ausfahren = nötig UND erlaubt
</div>
<table class="data"><thead><tr><th>Nr</th><th>Karton</th><th>Rot</th><th>Grundplatte X × Y</th>
<th>ausgefahren X × Y</th><th>nötig</th><th>erlaubt</th><th>Ausfahren</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>"""


def _calc_s8(result: LayerResult) -> str:
    inp = result.inputs
    corner = inp.origin_corner
    sx, sy = CORNER_SIGNS[corner]
    ex, ey = corner_point(corner, inp.pallet_length, inp.pallet_width)
    angle_rule = {1: "θ' = θ", 2: "θ' = 180° − θ", 3: "θ' = θ + 180°", 4: "θ' = 360° − θ"}[corner]
    b = result.boxes[0]
    k = b.approach_angle_base // 45
    return f"""
<h3>S8 · Umrechnung auf den Palettennullpunkt</h3>
<p>Das Muster liegt physikalisch fest; die Koordinaten werden auf den Nullpunkt
{CORNER_NAMES[corner]} gespiegelt. Die Drehung 0°/90° ändert sich dabei nicht.</p>
<div class="formula">
Nullpunkt ({ex:g}, {ey:g}), s<sub>x</sub> = {sx:+d}, s<sub>y</sub> = {sy:+d}, Winkel: {angle_rule} (mod 360)<br>
Beispiel Karton {b.no}: x' = s<sub>x</sub>·(x − x<sub>E</sub>) = {sx:+d}·({f1(b.x_base)} − {ex:g}) = <b>{f1(b.x)}</b>,
y' = {sy:+d}·({f1(b.y_base)} − {ey:g}) = <b>{f1(b.y)}</b><br>
Anfahrt: θ = {b.approach_angle_base}° → θ' = <b>{b.approach_angle}°</b>;
Vorposition dX = s<sub>x</sub>·s·cos θ = {sx:+d}·{f2(inp.approach_dist * DIR_X[k])} = <b>{f1(b.pre_dx)}</b>,
dY = {sy:+d}·{f2(inp.approach_dist * DIR_Y[k])} = <b>{f1(b.pre_dy)}</b>
</div>"""


def _calc_warnings(result: LayerResult) -> str:
    rows = []
    for bit, text in WARNING_TEXTS.items():
        boxes = [str(b.no) for b in result.boxes if b.warnings & bit]
        active = bool(result.warnings & bit)
        rows.append(f"<tr><td class='mono'>{bit.bit_length() - 1}</td><td>{escape(text)}</td>"
                    f"<td>{'⚠ ja' if active else 'nein'}</td><td>{', '.join(boxes) or '–'}</td></tr>")
    return ('<h3>Warnbits</h3><table class="data"><thead><tr><th>Bit</th><th>Bedeutung</th>'
            f'<th>aktiv</th><th>Kartons</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')


# --- Daten für die Detailanzeige ------------------------------------------------

def _box_data(result: LayerResult) -> str:
    data = []
    for b in result.boxes:
        a = b.approach
        data.append({
            "no": b.no, "key": b.key, "x": f1(b.x), "y": f1(b.y), "xb": f1(b.x_base), "yb": f1(b.y_base),
            "rot": b.rot, "angle": b.approach_angle, "angleBase": b.approach_angle_base,
            "pre": [f1(b.pre_dx), f1(b.pre_dy), f1(b.pre_dz)],
            "mask": f"{a.mask:08b}", "occupied": zone_names(a.mask),
            "free": ", ".join(ZONE_NAMES[k] for k in range(8) if a.free & (1 << k)) or "–",
            "v": [f2(a.vx), f2(a.vy)], "outward": a.used_outward, "noFree": a.no_free,
            "needed": b.gripper.needed, "allowed": b.gripper.allowed, "extend": b.gripper.extend,
            "warnings": warning_texts(b.warnings),
        })
    # "</" im JSON verhindern, damit der Script-Block nicht vorzeitig endet
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


# --- Seitenrahmen ---------------------------------------------------------------

def _page(title: str, body: str, box_data: str) -> str:
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<main>
{body}
</main>
<script type="application/json" id="box-data">{box_data}</script>
<script>{JS}</script>
</body>
</html>
"""


CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --pallet: #efeee9;
  --rot0: #2a78d6; --rot0-fill: #cde2fb; --rot90: #eb6834; --rot90-fill: #fbdccf;
  --critical: #d03b3b; --good: #0ca30c;
}
@media screen and (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --pallet: #242422;
    --rot0: #3987e5; --rot0-fill: #1a3352; --rot90: #d95926; --rot90-fill: #472415;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1280px; margin: 0 auto; padding: 16px; }
header h1 { font-size: 22px; margin: 8px 0 2px; }
.sub { color: var(--ink2); margin: 0 0 12px; }
h2 { font-size: 18px; margin: 0 0 10px; }
h3 { font-size: 15px; margin: 20px 0 6px; }
section { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
          padding: 16px; margin: 16px 0; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }
.tile { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; }
.tile .k { display: block; color: var(--ink2); font-size: 12px; }
.tile .v { display: block; font-size: 18px; font-weight: 600; }
.tile.warn .v { color: var(--critical); }
.tile.ok .v { color: var(--good); }
ul.warnings { color: var(--critical); margin: 10px 0 0; padding-left: 18px; }
.error { color: var(--critical); font-weight: 600; }
.hint { color: var(--muted); }

.controls { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 8px; }
.controls input[type=range] { flex: 1 1 160px; }
.controls button { font: inherit; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--axis);
                   background: var(--surface); color: var(--ink); cursor: pointer; }
#step-label { min-width: 150px; font-weight: 600; }
.layer-grid { display: grid; grid-template-columns: minmax(0, 3fr) minmax(220px, 1fr); gap: 16px; align-items: start; }
@media (max-width: 800px) { .layer-grid { grid-template-columns: 1fr; } }
.panel { border-left: 3px solid var(--axis); padding-left: 12px; }
.panel table { border-collapse: collapse; width: 100%; }
.panel td { padding: 2px 4px; border-bottom: 1px solid var(--grid); vertical-align: top; }
.panel td:first-child { color: var(--ink2); white-space: nowrap; }

.legend { list-style: none; padding: 0; margin: 10px 0 0; display: flex; flex-wrap: wrap; gap: 6px 18px;
          color: var(--ink2); font-size: 13px; }
.legend li { display: flex; align-items: center; gap: 6px; }
.legend .sw { width: 16px; height: 12px; border-radius: 2px; border: 1.5px solid; display: inline-block; }
.legend .sw.rot0 { background: var(--rot0-fill); border-color: var(--rot0); }
.legend .sw.rot90 { background: var(--rot90-fill); border-color: var(--rot90); }
.legend .sw.over { background: transparent; border: 2.5px solid var(--critical); }
.legend .sw.zone { background: var(--critical); opacity: .55; border-color: transparent; }
.legend .line { width: 22px; height: 0; border-top: 2px dashed var(--ink2); display: inline-block; }
.legend .line.block { border-top: 1px dashed var(--ink2); }
.legend .line.plate { border-top: 2px dashed var(--ink); }
.legend .line.ext { border-top: 2px dotted var(--good); }
.legend .line.blocked { border-top: 2px dotted var(--critical); }
.legend .line.pre { border-top: 1px dashed var(--ink2); }
.legend .sym { color: var(--ink); }

table.data { border-collapse: collapse; width: 100%; font-size: 13px; }
table.data th { text-align: left; color: var(--ink2); font-weight: 600; border-bottom: 1px solid var(--axis);
                padding: 4px 6px; }
table.data td { border-bottom: 1px solid var(--grid); padding: 3px 6px; }
table.data td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.data tr.warnrow td:last-child { color: var(--critical); }
table.data tr.selected td { background: var(--rot0-fill); }
table.inputs { width: auto; }
#box-table tbody tr { cursor: pointer; }
.mono { font-family: ui-monospace, Consolas, monospace; }
.formula { font-family: ui-monospace, Consolas, monospace; background: var(--page); border-left: 3px solid var(--axis);
           padding: 8px 12px; margin: 6px 0; line-height: 1.7; overflow-x: auto; }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.card { border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.card.chosen { border: 2px solid var(--ink); }
.card h3 { margin: 0; }
.card svg.layer { max-height: 300px; }
.badge { font-size: 12px; background: var(--ink); color: var(--surface); border-radius: 10px; padding: 1px 8px; margin-left: 6px; }
.steps { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.steps figure { margin: 0; }
.steps figcaption { font-size: 12px; color: var(--ink2); text-align: center; }

/* Zeichnung */
svg.layer { width: 100%; height: auto; display: block; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
svg .pallet { fill: var(--pallet); stroke: var(--axis); stroke-width: 1.5px; vector-effect: non-scaling-stroke; }
svg .dim, svg .corner { fill: var(--muted); }
svg .block-outline { fill: none; stroke: var(--ink2); stroke-width: 1px; stroke-dasharray: 6 4; vector-effect: non-scaling-stroke; }
svg .block-label { fill: var(--ink2); }
svg.hide-blocks .block-outline, svg.hide-blocks .block-label { display: none; }
svg .box .body { stroke-width: 1.5px; vector-effect: non-scaling-stroke; }
svg .box.rot0 .body { fill: var(--rot0-fill); stroke: var(--rot0); }
svg .box.rot90 .body { fill: var(--rot90-fill); stroke: var(--rot90); }
svg .box.overhang .body { stroke: var(--critical); stroke-width: 3px; }
svg .box.current .body { stroke: var(--ink); stroke-width: 3px; }
svg .box.ghost .body { fill: none; stroke: var(--muted); stroke-dasharray: 4 4; }
svg .box.ghost .num, svg .box.ghost .label, svg .box.ghost .approach,
svg .box.ghost .center, svg .box.ghost .conv-axis { opacity: .22; }
svg .num { fill: var(--ink); font-weight: 600; }
svg .label { fill: var(--ink2); }
svg .conv-axis { stroke: var(--ink2); stroke-width: 1px; stroke-dasharray: 8 6; opacity: .6; vector-effect: non-scaling-stroke; }
svg .center { fill: none; stroke: var(--ink); stroke-width: 1.5px; vector-effect: non-scaling-stroke; }
svg .approach line, svg .axis line { stroke: var(--ink); stroke-width: 2px; vector-effect: non-scaling-stroke; }
svg .approach polygon, svg .axis polygon { fill: var(--ink); }
svg .origin, svg .axis-label { fill: var(--ink); }
svg .axis-label { font-weight: 600; }
svg .zones, svg .plates { display: none; }
svg .zones.visible, svg .plates.visible { display: inline; }
svg.hide-zones .zones.visible, svg.hide-plates .plates.visible { display: none; }
svg .zone.occupied { fill: var(--critical); opacity: .55; }
svg .zone.free { fill: none; stroke: var(--muted); stroke-width: .75px; stroke-dasharray: 2 3; vector-effect: non-scaling-stroke; }
svg .pre-position { fill: none; stroke: var(--ink2); stroke-width: 1px; stroke-dasharray: 3 3; vector-effect: non-scaling-stroke; }
svg .plate { fill: none; stroke-width: 2px; vector-effect: non-scaling-stroke; }
svg .plate.base { stroke: var(--ink); stroke-dasharray: 10 5; }
svg .plate.ext-ok { stroke: var(--good); stroke-dasharray: 2 4; }
svg .plate.ext-blocked { stroke: var(--critical); stroke-dasharray: 2 4; }
#main-svg .box { cursor: pointer; }
svg.compact .box.current .body { stroke-width: 2.5px; }

@page { size: A4 landscape; margin: 10mm; }
@media print {
  body { background: #fff; font-size: 11px; }
  main { max-width: none; padding: 0; }
  section { border: none; padding: 0; margin: 0; break-before: page; }
  section.first { break-before: avoid; }
  .controls, .panel, .screen { display: none !important; }
  .layer-grid { display: block; }
  .drawing svg { max-height: 150mm; }
  svg .zones.visible, svg .plates.visible { display: none; }
  table.data tr, .formula, figure, .card { break-inside: avoid; }
  .steps { grid-template-columns: repeat(5, 1fr); }
}
"""

JS = r"""
(function () {
  const data = JSON.parse(document.getElementById('box-data').textContent);
  const svg = document.getElementById('main-svg');
  if (!svg || !data.length) return;
  const n = data.length;
  const slider = document.getElementById('step');
  const label = document.getElementById('step-label');
  const panel = document.getElementById('panel');
  const rows = document.querySelectorAll('#box-table tbody tr');
  let step = null;

  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
  function yn(b) { return b ? 'ja' : 'nein'; }

  function render() {
    svg.querySelectorAll('.box').forEach(g => {
      const no = +g.dataset.no;
      g.classList.toggle('ghost', step !== null && no > step);
      g.classList.toggle('current', step !== null && no === step);
    });
    svg.querySelectorAll('.zones, .plates').forEach(g => {
      g.classList.toggle('visible', step !== null && +g.dataset.no === step);
    });
    rows.forEach(r => r.classList.toggle('selected', step !== null && +r.dataset.no === step));
    if (step === null) {
      slider.value = n;
      label.textContent = 'Gesamtansicht';
      panel.innerHTML = '<p class="hint">Karton anklicken oder Schritt wählen, um die Berechnung für diesen Karton zu sehen.</p>';
      return;
    }
    slider.value = step;
    const d = data[step - 1];
    label.textContent = 'Schritt ' + step + ' von ' + n + ' · ' + d.key;
    const warn = d.warnings.length ? d.warnings.map(w => '⚠ ' + esc(w)).join('<br>') : '–';
    panel.innerHTML =
      '<h3>Karton ' + d.no + ' · ' + esc(d.key) + '</h3><table>' +
      '<tr><td>X / Y (Ausgabe)</td><td>' + d.x + ' / ' + d.y + '</td></tr>' +
      '<tr><td>X / Y (Grundsystem)</td><td>' + d.xb + ' / ' + d.yb + '</td></tr>' +
      '<tr><td>Drehung</td><td>' + d.rot + '°</td></tr>' +
      '<tr><td>Anfahrt</td><td>' + d.angle + '° (Grundsystem ' + d.angleBase + '°)</td></tr>' +
      '<tr><td>Vorposition dX/dY/dZ</td><td>' + d.pre.join(' / ') + '</td></tr>' +
      '<tr><td>Nachbarmaske</td><td class="mono">' + d.mask + '</td></tr>' +
      '<tr><td>belegte Zonen</td><td>' + esc(d.occupied) + '</td></tr>' +
      '<tr><td>freie Richtungen</td><td>' + esc(d.free) + '</td></tr>' +
      '<tr><td>Wunschvektor v</td><td>(' + d.v.join(', ') + ')' + (d.outward ? ' – von außen' : '') + '</td></tr>' +
      '<tr><td>Saugplatte</td><td>nötig ' + yn(d.needed) + ', erlaubt ' + yn(d.allowed) +
        ' → <b>' + (d.extend ? '1 ausfahren' : '0 nicht ausfahren') + '</b></td></tr>' +
      '<tr><td>Warnungen</td><td>' + warn + '</td></tr></table>';
  }

  function setStep(s) { step = s === null ? null : Math.max(1, Math.min(n, s)); render(); }

  slider.addEventListener('input', () => setStep(+slider.value));
  document.getElementById('btn-prev').addEventListener('click', () => setStep(step === null ? n : step - 1));
  document.getElementById('btn-next').addEventListener('click', () => setStep(step === null ? 1 : step + 1));
  document.getElementById('btn-all').addEventListener('click', () => setStep(null));
  svg.querySelectorAll('.box').forEach(g => g.addEventListener('click', () => setStep(+g.dataset.no)));
  rows.forEach(r => r.addEventListener('click', () => {
    setStep(+r.dataset.no);
    svg.scrollIntoView({behavior: 'smooth', block: 'center'});
  }));
  [['show-zones', 'hide-zones'], ['show-plates', 'hide-plates'], ['show-blocks', 'hide-blocks']].forEach(([id, cls]) => {
    const box = document.getElementById(id);
    box.addEventListener('change', () => svg.classList.toggle(cls, !box.checked));
  });
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' && e.target.type !== 'range') return;
    if (e.key === 'ArrowRight') setStep(step === null ? 1 : step + 1);
    if (e.key === 'ArrowLeft') setStep(step === null ? n : step - 1);
    if (e.key === 'Escape') setStep(null);
  });
  window.addEventListener('beforeprint', () => setStep(null));
  render();
})();
"""

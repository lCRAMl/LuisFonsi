"""Stufen S2-S4: Musterauflösung, Kartonpositionen, Zentrieren und Wahl der Variante.

Für jedes Muster werden zwei Orientierungsvarianten berechnet:
    Variante "X": Kartons von Block A mit der Langseite in X  -> (px, py) = (l, k)
    Variante "Y": Kartons von Block A mit der Langseite in Y  -> (px, py) = (k, l)
"""

from __future__ import annotations

from .constants import (ERR_PATTERN_OVERLAP, ERR_TOO_MANY_BLOCKS, ERR_TOO_MANY_BOXES,
                        MAX_BLOCKS, MAX_BOXES)
from .geometry import extent, rect_overlap
from .model import Block, Box, Inputs, VariantLayout
from .patterns import Pattern


def primary_footprint(variant: str, box_long: float, box_short: float) -> tuple[float, float]:
    """Kartonmaß (px, py) in der Grundorientierung der Variante."""
    if variant == "X":
        return box_long, box_short
    return box_short, box_long


def box_rotation(size_x: float, size_y: float, inp: Inputs) -> int:
    """Drehung bezogen auf die Lage auf dem Förderband (Förderrichtung parallel X bei 0°).

    0  = Kartonmaß in Förderrichtung liegt in X
    90 = Karton ist gedreht
    Quadratischer Karton: immer 0.
    """
    tol = inp.tolerance
    if abs(size_x - inp.box_length_conv) <= tol and abs(size_y - inp.box_width_conv) <= tol:
        return 0
    return 90


def build_variant(pattern: Pattern, variant: str, inp: Inputs) -> VariantLayout:
    """Berechnet die komplette Lage für eine Variante im Grundsystem."""
    layout = VariantLayout(name=variant)
    box_long = max(inp.box_length_conv, inp.box_width_conv)
    box_short = min(inp.box_length_conv, inp.box_width_conv)
    px, py = primary_footprint(variant, box_long, box_short)
    gap = inp.gap
    tol = inp.tolerance

    # S2: Musterauflösung -> Blockliste
    block_defs = pattern.build_blocks(px, py, gap)
    if block_defs is None:
        layout.valid = False
        return layout
    if len(block_defs) > MAX_BLOCKS:
        layout.valid = False
        layout.error_code = ERR_TOO_MANY_BLOCKS
        return layout

    blocks: list[Block] = []
    total = 0
    for d in block_defs:
        if d.rotated:
            size_x, size_y = py, px
        else:
            size_x, size_y = px, py
        blocks.append(Block(id=d.id, x0=d.x0, y0=d.y0, cols=d.cols, rows=d.rows,
                            rotated=d.rotated, size_x=size_x, size_y=size_y,
                            width=extent(d.cols, size_x, gap),
                            height=extent(d.rows, size_y, gap)))
        total += d.cols * d.rows
    if total > MAX_BOXES:
        layout.valid = False
        layout.error_code = ERR_TOO_MANY_BOXES
        return layout

    # S4 (vorgezogen): Lagenmaß und Versatz zum Zentrieren
    min_x = blocks[0].x0
    max_x = blocks[0].x0 + blocks[0].width
    min_y = blocks[0].y0
    max_y = blocks[0].y0 + blocks[0].height
    for b in blocks:
        min_x = min(min_x, b.x0)
        max_x = max(max_x, b.x0 + b.width)
        min_y = min(min_y, b.y0)
        max_y = max(max_y, b.y0 + b.height)
    layout.layer_size_x = max_x - min_x
    layout.layer_size_y = max_y - min_y
    offset_x = (inp.pallet_length - layout.layer_size_x) / 2 - min_x
    offset_y = (inp.pallet_width - layout.layer_size_y) / 2 - min_y

    # S3: Kartonmittelpunkte (Doppelschleife je Block)
    #   x = x0 + i * (a + g) + a / 2,   y = y0 + j * (c + g) + c / 2
    for b in blocks:
        b.x0 += offset_x
        b.y0 += offset_y
        for i in range(b.cols):
            for j in range(b.rows):
                cx = b.x0 + i * (b.size_x + gap) + b.size_x / 2
                cy = b.y0 + j * (b.size_y + gap) + b.size_y / 2
                rot = box_rotation(b.size_x, b.size_y, inp)
                layout.boxes.append(Box(block_id=b.id, col=i + 1, row=j + 1, cx=cx, cy=cy,
                                        size_x=b.size_x, size_y=b.size_y, rot=rot))
                if rot == 90:
                    layout.rotated_count += 1
    layout.blocks = blocks

    # Plausibilität: keine zwei Kartons dürfen sich überlappen (schützt vor fehlerhaften Plugins)
    boxes = layout.boxes
    for m in range(len(boxes)):
        for n in range(m + 1, len(boxes)):
            p, q = boxes[m], boxes[n]
            if rect_overlap(p.x1, p.x2, p.y1, p.y2, q.x1, q.x2, q.y1, q.y2, tol):
                layout.valid = False
                layout.error_code = ERR_PATTERN_OVERLAP
                return layout

    # Überstand
    excess_x = max(0.0, layout.layer_size_x - inp.pallet_length)
    excess_y = max(0.0, layout.layer_size_y - inp.pallet_width)
    layout.overhang_x = excess_x / 2
    layout.overhang_y = excess_y / 2
    layout.overhang_sum = excess_x + excess_y
    return layout


def choose_variant(vx: VariantLayout, vy: VariantLayout, inp: Inputs,
                   drawn_long_side: str) -> tuple[VariantLayout | None, str]:
    """Wählt die Variante nach der festgelegten Rangfolge.

    1. weniger Überstand (overhang_sum)
    2. weniger gedrehte Kartons (rotated_count)
    3. Orientierung laut Zeichnung
    Mit orientation_mode 1/2 wird die Variante fest vorgegeben.
    """
    tol = inp.tolerance
    if inp.orientation_mode == 1:
        return (vx if vx.valid else None), "manuell vorgegeben (Variante X)"
    if inp.orientation_mode == 2:
        return (vy if vy.valid else None), "manuell vorgegeben (Variante Y)"

    if not vx.valid and not vy.valid:
        return None, "keine Variante gültig"
    if not vy.valid:
        return vx, "nur Variante X darstellbar"
    if not vx.valid:
        return vy, "nur Variante Y darstellbar"

    if vx.overhang_sum < vy.overhang_sum - tol:
        return vx, "weniger Überstand"
    if vy.overhang_sum < vx.overhang_sum - tol:
        return vy, "weniger Überstand"
    if vx.rotated_count < vy.rotated_count:
        return vx, "gleicher Überstand, weniger Drehungen"
    if vy.rotated_count < vx.rotated_count:
        return vy, "gleicher Überstand, weniger Drehungen"
    if drawn_long_side == "y":
        return vy, "Gleichstand, Orientierung laut Zeichnung"
    return vx, "Gleichstand, Orientierung laut Zeichnung"

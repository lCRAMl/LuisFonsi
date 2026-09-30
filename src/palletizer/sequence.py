"""Stufe S5: Ablagereihenfolge.

Regel "dichter Teil zuerst":
1. Blöcke mit mehr Kartons zuerst (bei Gleichstand: näher an der Startecke zuerst).
2. Startecke
   X-Seite: gegenüber dem "lockeren" Teil (Blöcke mit weniger Kartons),
            ersatzweise gegenüber der Lücke, sonst Seite des Palettennullpunkts.
   Y-Seite: gegenüber der Lücke,
            ersatzweise gegenüber dem lockeren Teil, sonst Seite des Palettennullpunkts.
3. Innerhalb eines Blocks spaltenweise (bzw. reihenweise) von der Startecke weg.
Im Pattern können Startecke, Füllrichtung oder die komplette Reihenfolge vorgegeben werden.
"""

from __future__ import annotations

from .constants import ERR_SEQUENCE_OVERRIDE
from .model import Box, Inputs, SequenceInfo, VariantLayout
from .patterns import Pattern


def corner_sides(corner: int) -> tuple[bool, bool]:
    """(x_max, y_max) einer Ecke: E1 (min,min), E2 (max,min), E3 (max,max), E4 (min,max)."""
    return corner in (2, 3), corner in (3, 4)


def corner_from_sides(x_max: bool, y_max: bool) -> int:
    if x_max:
        return 3 if y_max else 2
    return 4 if y_max else 1


def determine_start_corner(layout: VariantLayout, inp: Inputs, pattern: Pattern) -> SequenceInfo:
    """Bestimmt die Startecke der Ablage im Grundsystem."""
    info = SequenceInfo()
    tol = inp.tolerance
    center_x = inp.pallet_length / 2   # Lage ist zentriert -> Lagenmitte = Palettenmitte
    center_y = inp.pallet_width / 2

    # Lockerer Teil: alle Kartons aus Blöcken mit weniger Kartons als der größte Block
    max_count = 0
    for block in layout.blocks:
        max_count = max(max_count, block.count)
    loose_blocks = {block.id for block in layout.blocks if block.count < max_count}
    sum_x = 0.0
    sum_y = 0.0
    for box in layout.boxes:
        if box.block_id in loose_blocks:
            info.loose_count += 1
            sum_x += box.cx
            sum_y += box.cy
    if info.loose_count > 0:
        info.loose_cx = sum_x / info.loose_count
        info.loose_cy = sum_y / info.loose_count

    # Lücke: Lagenmaß-Rechteck minus Kartonflächen
    #   A_Lücke = W_X * W_Y - Summe(A_i)
    #   Schwerpunkt = (A_Lage * Mitte - Summe(A_i * Mitte_i)) / A_Lücke
    area_layer = layout.layer_size_x * layout.layer_size_y
    moment_x = area_layer * center_x
    moment_y = area_layer * center_y
    area_boxes = 0.0
    for box in layout.boxes:
        area = box.size_x * box.size_y
        area_boxes += area
        moment_x -= area * box.cx
        moment_y -= area * box.cy
    info.gap_area = area_layer - area_boxes
    has_gap = info.gap_area > tol * (layout.layer_size_x + layout.layer_size_y)
    if has_gap:
        info.gap_cx = moment_x / info.gap_area
        info.gap_cy = moment_y / info.gap_area
    has_loose = info.loose_count > 0

    if pattern.start_corner is not None:
        info.start_corner = pattern.start_corner
        info.source_x = info.source_y = "Vorgabe im Pattern"
        return info

    x_max, y_max = corner_sides(inp.origin_corner)
    info.source_x = info.source_y = "Seite des Palettennullpunkts"

    if has_loose and info.loose_cx > center_x + tol:
        x_max, info.source_x = False, "gegenüber dem lockeren Teil"
    elif has_loose and info.loose_cx < center_x - tol:
        x_max, info.source_x = True, "gegenüber dem lockeren Teil"
    elif has_gap and info.gap_cx > center_x + tol:
        x_max, info.source_x = False, "gegenüber der Lücke"
    elif has_gap and info.gap_cx < center_x - tol:
        x_max, info.source_x = True, "gegenüber der Lücke"

    if has_gap and info.gap_cy < center_y - tol:
        y_max, info.source_y = True, "gegenüber der Lücke"
    elif has_gap and info.gap_cy > center_y + tol:
        y_max, info.source_y = False, "gegenüber der Lücke"
    elif has_loose and info.loose_cy > center_y + tol:
        y_max, info.source_y = False, "gegenüber dem lockeren Teil"
    elif has_loose and info.loose_cy < center_y - tol:
        y_max, info.source_y = True, "gegenüber dem lockeren Teil"

    info.start_corner = corner_from_sides(x_max, y_max)
    return info


def order_boxes(layout: VariantLayout, info: SequenceInfo, inp: Inputs,
                pattern: Pattern) -> tuple[list[Box], int]:
    """Sortiert die Kartons in Ablagereihenfolge. Rückgabe: (Liste, Fehlercode)."""
    by_key = {box.key: box for box in layout.boxes}

    if pattern.order is not None:
        if sorted(pattern.order) != sorted(by_key):
            return [], ERR_SEQUENCE_OVERRIDE
        return [by_key[key] for key in pattern.order], 0

    x_max, y_max = corner_sides(info.start_corner)
    start_x = inp.pallet_length if x_max else 0.0
    start_y = inp.pallet_width if y_max else 0.0

    # Blockreihenfolge: mehr Kartons zuerst, dann geringerer Abstand zur Startecke
    ranked = []
    for index, block in enumerate(layout.blocks):
        block_cx = block.x0 + block.width / 2
        block_cy = block.y0 + block.height / 2
        distance = abs(block_cx - start_x) + abs(block_cy - start_y)
        ranked.append((-block.count, distance, index, block))
    ranked.sort(key=lambda item: item[:3])

    ordered: list[Box] = []
    for _, _, _, block in ranked:
        cols = list(range(1, block.cols + 1))
        rows = list(range(1, block.rows + 1))
        if x_max:
            cols.reverse()
        if y_max:
            rows.reverse()
        if pattern.fill == "columns":
            for col in cols:
                for row in rows:
                    ordered.append(by_key[f"{block.id}.{col}.{row}"])
        else:
            for row in rows:
                for col in cols:
                    ordered.append(by_key[f"{block.id}.{col}.{row}"])
    return ordered, 0

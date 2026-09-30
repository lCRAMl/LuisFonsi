"""Gesamtablauf der Berechnung (Stufen S0-S8).

    S0  Eingaben prüfen                      validate.validate_inputs
    S1  Normieren (Lang-/Kurzseite)          hier
    S2  Musterauflösung -> Blockliste        layout.build_variant
    S3  Kartonpositionen im Lagen-System     layout.build_variant
    S4  Zentrieren, Überstand, Variante      layout.build_variant / choose_variant
    S5  Ablagereihenfolge                    sequence
    S6  Annäherungsrichtung                  approach
    S7  Saugplatte                           gripper
    S8  Umrechnung auf den Nullpunkt         transform
"""

from __future__ import annotations

from .approach import choose_approach
from .constants import (DIR_X, DIR_Y, ERR_NO_VALID_VARIANT, WARN_BOX_LARGER_THAN_PALLET,
                        WARN_EXTEND_BLOCKED, WARN_NO_FREE_APPROACH, WARN_OVERHANG,
                        WARN_PLATE_OVER_NEIGHBOR, WARN_SHORT_SIDE_LEADING)
from .gripper import evaluate_gripper
from .layout import build_variant, choose_variant
from .model import Box, BoxResult, Inputs, LayerResult
from .patterns import PatternLibrary
from .sequence import determine_start_corner, order_boxes
from .transform import angle_to_output, point_to_output, vector_to_output
from .validate import validate_inputs


def calculate(inp: Inputs, library: PatternLibrary) -> LayerResult:
    """Berechnet eine komplette Lage inkl. aller Zwischenergebnisse."""
    result = LayerResult(inputs=inp)

    # S0: Eingaben prüfen
    result.error_code = validate_inputs(inp, library)
    if result.error_code:
        return result
    pattern = library.find(inp.pattern)
    result.pattern_id = pattern.id
    result.pattern_no = pattern.number
    result.pattern_name = pattern.name
    tol = inp.tolerance

    # S1: Normieren
    result.box_long = max(inp.box_length_conv, inp.box_width_conv)
    result.box_short = min(inp.box_length_conv, inp.box_width_conv)
    if inp.box_length_conv < inp.box_width_conv - tol:
        result.warnings |= WARN_SHORT_SIDE_LEADING

    # S2-S4: beide Varianten berechnen und auswählen
    variant_x = build_variant(pattern, "X", inp)
    variant_y = build_variant(pattern, "Y", inp)
    result.variants = [variant_x, variant_y]
    chosen, result.variant_reason = choose_variant(variant_x, variant_y, inp,
                                                   pattern.drawn_long_side)
    if chosen is None:
        result.error_code = (variant_x.error_code or variant_y.error_code
                             or ERR_NO_VALID_VARIANT)
        return result
    result.variant = chosen.name
    result.layer_size_x = chosen.layer_size_x
    result.layer_size_y = chosen.layer_size_y
    result.overhang_x = chosen.overhang_x
    result.overhang_y = chosen.overhang_y
    result.rotated_count = chosen.rotated_count
    area_boxes = 0.0
    for box in chosen.boxes:
        area_boxes += box.size_x * box.size_y
    result.area_usage = 100.0 * area_boxes / (inp.pallet_length * inp.pallet_width)

    if (chosen.count == 1 and (chosen.boxes[0].size_x > inp.pallet_length + tol
                               or chosen.boxes[0].size_y > inp.pallet_width + tol)):
        result.warnings |= WARN_BOX_LARGER_THAN_PALLET

    # S5: Ablagereihenfolge
    result.sequence = determine_start_corner(chosen, inp, pattern)
    ordered, error = order_boxes(chosen, result.sequence, inp, pattern)
    if error:
        result.error_code = error
        return result

    # S6-S8 je Karton in Ablagereihenfolge
    placed: list[Box] = []
    corner = inp.origin_corner
    for index, box in enumerate(ordered):
        warnings = 0
        if box_overhangs(box, inp):
            warnings |= WARN_OVERHANG

        approach = choose_approach(box, placed, inp)
        if approach.no_free:
            warnings |= WARN_NO_FREE_APPROACH

        gripper = evaluate_gripper(box, placed, inp)
        if gripper.needed and not gripper.allowed:
            warnings |= WARN_EXTEND_BLOCKED
        if gripper.plate_over_neighbor:
            warnings |= WARN_PLATE_OVER_NEIGHBOR

        # Vorposition im Grundsystem, danach Umrechnung auf den Nullpunkt
        pre_dx = inp.approach_dist * DIR_X[approach.direction]
        pre_dy = inp.approach_dist * DIR_Y[approach.direction]
        x, y = point_to_output(box.cx, box.cy, corner, inp.pallet_length, inp.pallet_width)
        out_dx, out_dy = vector_to_output(pre_dx, pre_dy, corner)

        result.boxes.append(BoxResult(
            no=index + 1,
            block_id=box.block_id, col=box.col, row=box.row,
            x=clean(x), y=clean(y), rot=box.rot,
            approach_angle=angle_to_output(approach.angle, corner),
            pre_dx=clean(out_dx), pre_dy=clean(out_dy), pre_dz=inp.approach_height,
            extend_plate=gripper.extend,
            neighbor_mask=approach.mask,
            warnings=warnings,
            x_base=clean(box.cx), y_base=clean(box.cy),
            size_x=box.size_x, size_y=box.size_y,
            approach_angle_base=approach.angle,
            approach=approach, gripper=gripper,
        ))
        result.warnings |= warnings
        placed.append(box)
    return result


def box_overhangs(box: Box, inp: Inputs) -> bool:
    """True, wenn der Karton weiter als erlaubt über den Palettenrand ragt."""
    limit = inp.max_overhang + inp.tolerance
    return (box.x1 < -limit or box.y1 < -limit
            or box.x2 > inp.pallet_length + limit or box.y2 > inp.pallet_width + limit)


def clean(value: float, digits: int = 6) -> float:
    """Rundet Rechenrauschen weg (auf 1e-6 mm) und vermeidet -0.0 in der Ausgabe."""
    value = round(value, digits)
    return 0.0 if value == 0 else value

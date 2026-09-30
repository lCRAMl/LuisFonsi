"""Stufe S0: Prüfung der Eingaben. Liefert den ersten gefundenen Fehlercode (0 = OK)."""

from .constants import (ERR_APPROACH, ERR_BOX_SIZE, ERR_GAP, ERR_OK, ERR_ORIENTATION_MODE,
                        ERR_ORIGIN_CORNER, ERR_PALLET_SIZE, ERR_PATTERN_UNKNOWN, ERR_PLATE,
                        ERR_TOLERANCE)
from .model import Inputs
from .patterns import PatternLibrary


def validate_inputs(inp: Inputs, library: PatternLibrary) -> int:
    if inp.tolerance <= 0:
        return ERR_TOLERANCE
    if inp.pallet_length <= 0 or inp.pallet_width <= 0:
        return ERR_PALLET_SIZE
    if inp.box_length_conv <= 0 or inp.box_width_conv <= 0:
        return ERR_BOX_SIZE
    if library.find(inp.pattern) is None:
        return ERR_PATTERN_UNKNOWN
    if inp.origin_corner not in (1, 2, 3, 4):
        return ERR_ORIGIN_CORNER
    if inp.orientation_mode not in (0, 1, 2):
        return ERR_ORIENTATION_MODE
    if inp.gap < 0 or inp.max_overhang < 0:
        return ERR_GAP
    if inp.approach_dist <= 0 or inp.approach_height < 0:
        return ERR_APPROACH
    if (inp.plate_conv <= 0 or inp.plate_cross <= 0
            or inp.plate_ext_conv < inp.plate_conv or inp.plate_ext_cross < inp.plate_cross):
        return ERR_PLATE
    return ERR_OK

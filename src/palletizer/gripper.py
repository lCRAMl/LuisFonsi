"""Stufe S7: Saugplatte ausfahren.

Die Saugplatte sitzt mittig auf dem Karton und dreht sich mit ihm, ist also fest
auf das Förderband-System bezogen (Grundplatte 600 in / 400 quer zur Förderrichtung,
ausgefahren symmetrisch auf 1400 quer).

    nötig   = Karton ist in einer Ausfahrachse länger als die Grundplatte
    erlaubt = ausgefahrene Platte überdeckt keinen bereits abgelegten Karton
    Ausfahren = nötig UND erlaubt      (nötig UND NICHT erlaubt -> Warnung)
"""

from __future__ import annotations

from .geometry import rect_overlap
from .model import Box, GripperInfo, Inputs


def plate_size(rot: int, size_conv: float, size_cross: float) -> tuple[float, float]:
    """Plattenmaß in X/Y. Bei Rot = 0 liegt die Förderrichtung in X."""
    if rot == 0:
        return size_conv, size_cross
    return size_cross, size_conv


def extension_needed(inp: Inputs) -> bool:
    """Karton ist in einer Achse, in der die Platte ausfährt, länger als die Grundplatte."""
    tol = inp.tolerance
    needed = False
    if inp.plate_ext_conv > inp.plate_conv + tol and inp.box_length_conv > inp.plate_conv + tol:
        needed = True
    if inp.plate_ext_cross > inp.plate_cross + tol and inp.box_width_conv > inp.plate_cross + tol:
        needed = True
    return needed


def covers_placed(box: Box, size_x: float, size_y: float, placed: list[Box], eps: float) -> bool:
    """True, wenn eine Platte (size_x x size_y) mittig auf `box` einen abgelegten Karton überdeckt."""
    x1 = box.cx - size_x / 2
    x2 = box.cx + size_x / 2
    y1 = box.cy - size_y / 2
    y2 = box.cy + size_y / 2
    for other in placed:
        if rect_overlap(x1, x2, y1, y2, other.x1, other.x2, other.y1, other.y2, eps):
            return True
    return False


def evaluate_gripper(box: Box, placed: list[Box], inp: Inputs) -> GripperInfo:
    """Bestimmt für einen Karton, ob die Saugplatte ausfahren soll."""
    info = GripperInfo()
    info.needed = extension_needed(inp)

    ext_x, ext_y = plate_size(box.rot, inp.plate_ext_conv, inp.plate_ext_cross)
    info.allowed = not covers_placed(box, ext_x, ext_y, placed, inp.tolerance)
    info.extend = info.needed and info.allowed
    return info

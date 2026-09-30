"""Stufe S8: Umrechnung vom Grundsystem auf den gewählten Palettennullpunkt (Spiegeln).

Ecken im Grundsystem: E1 (0, 0), E2 (L_P, 0), E3 (L_P, B_P), E4 (0, B_P).
    x' = s_x * (x - x_E)        y' = s_y * (y - y_E)
    E1: s = (+1, +1)   E2: s = (-1, +1)   E3: s = (-1, -1)   E4: s = (+1, -1)

Die Kartondrehung (0°/90°) ändert sich beim Spiegeln nicht.
Winkel:  E2: θ' = 180° - θ    E3: θ' = θ + 180°    E4: θ' = 360° - θ    (mod 360)
"""

CORNER_SIGNS = {1: (1, 1), 2: (-1, 1), 3: (-1, -1), 4: (1, -1)}


def corner_point(corner: int, pallet_length: float, pallet_width: float) -> tuple[float, float]:
    x = pallet_length if corner in (2, 3) else 0.0
    y = pallet_width if corner in (3, 4) else 0.0
    return x, y


def point_to_output(x: float, y: float, corner: int,
                    pallet_length: float, pallet_width: float) -> tuple[float, float]:
    sx, sy = CORNER_SIGNS[corner]
    ex, ey = corner_point(corner, pallet_length, pallet_width)
    return sx * (x - ex), sy * (y - ey)


def vector_to_output(dx: float, dy: float, corner: int) -> tuple[float, float]:
    sx, sy = CORNER_SIGNS[corner]
    return sx * dx, sy * dy


def angle_to_output(angle: int, corner: int) -> int:
    if corner == 2:
        return (180 - angle) % 360
    if corner == 3:
        return (angle + 180) % 360
    if corner == 4:
        return (360 - angle) % 360
    return angle % 360

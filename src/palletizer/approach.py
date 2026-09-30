"""Stufe S6: Annäherungsrichtung (Modell "Nachbarzonen").

Der Winkel gibt an, AUS welcher Richtung der Karton kommt:
    Vorposition = Ziel + s * (cos θ, sin θ)

1. Um den Karton liegen 8 Prüfzonen der Tiefe s (Abstand der Vorposition).
   Zone k liegt in Richtung k * 45°.
2. Zone k ist belegt, wenn ein bereits abgelegter Karton sie mit Fläche > 0 überlappt
   -> Nachbarmaske (8 Bit).
3. Richtung k ist frei:
     gerade Richtung (0°, 90°, ...): Zone k frei
     Diagonale (45°, 135°, ...):     Zone k und beide Nachbarzonen frei
4. Wunschvektor v = -Summe(u_k) über alle belegten Zonen (weg von den Nachbarn).
   Ist v = 0, wird der Vektor w "Palettenmitte -> Karton" verwendet (von außen anfahren).
5. Gewählt wird die freie Richtung mit dem größten Skalarprodukt u_k * v,
   bei Gleichstand das größere u_k * w, danach die feste Rangfolge APPROACH_PRIORITY.
   Ist keine Richtung frei: Richtung mit den wenigsten belegten Zonen + Warnung.
"""

from __future__ import annotations

import math

from .constants import APPROACH_PRIORITY, DIR_X, DIR_Y, DOT_EPS
from .geometry import rect_overlap
from .model import ApproachInfo, Box, Inputs


def zones(box: Box, depth: float) -> list[tuple[float, float, float, float]]:
    """Die 8 Prüfzonen (x1, x2, y1, y2) um einen Karton, Index k = Richtung k * 45°."""
    x1, x2, y1, y2 = box.x1, box.x2, box.y1, box.y2
    s = depth
    return [
        (x2, x2 + s, y1, y2),           # 0: Ost
        (x2, x2 + s, y2, y2 + s),       # 1: Nordost
        (x1, x2, y2, y2 + s),           # 2: Nord
        (x1 - s, x1, y2, y2 + s),       # 3: Nordwest
        (x1 - s, x1, y1, y2),           # 4: West
        (x1 - s, x1, y1 - s, y1),       # 5: Südwest
        (x1, x2, y1 - s, y1),           # 6: Süd
        (x2, x2 + s, y1 - s, y1),       # 7: Südost
    ]


def neighbor_mask(box: Box, placed: list[Box], depth: float, eps: float) -> int:
    """Nachbarmaske: Bit k = 1, wenn Zone k von einem abgelegten Karton belegt ist."""
    mask = 0
    zone_list = zones(box, depth)
    for k in range(8):
        zx1, zx2, zy1, zy2 = zone_list[k]
        for other in placed:
            if rect_overlap(zx1, zx2, zy1, zy2, other.x1, other.x2, other.y1, other.y2, eps):
                mask |= 1 << k
                break
    return mask


def zone_bits(k: int) -> int:
    """Zonen, die für Richtung k frei sein müssen (Diagonale: auch beide Nachbarzonen)."""
    bits = 1 << k
    if k % 2 == 1:
        bits |= 1 << ((k + 7) % 8)
        bits |= 1 << ((k + 1) % 8)
    return bits


def free_mask(mask: int) -> int:
    """Bit k = 1, wenn Richtung k frei ist."""
    free = 0
    for k in range(8):
        if mask & zone_bits(k) == 0:
            free |= 1 << k
    return free


def blocked_count(mask: int, k: int) -> int:
    """Anzahl belegter Zonen im Weg der Richtung k."""
    return bin(mask & zone_bits(k)).count("1")


def choose_approach(box: Box, placed: list[Box], inp: Inputs) -> ApproachInfo:
    """Bestimmt die Annäherungsrichtung eines Kartons im Grundsystem."""
    info = ApproachInfo()
    info.mask = neighbor_mask(box, placed, inp.approach_dist, inp.tolerance)
    info.free = free_mask(info.mask)

    # Wunschvektor weg von den belegten Zonen
    vx = 0.0
    vy = 0.0
    for k in range(8):
        if info.mask & (1 << k):
            vx -= DIR_X[k]
            vy -= DIR_Y[k]

    # Vektor Palettenmitte -> Karton, normiert
    wx = box.cx - inp.pallet_length / 2
    wy = box.cy - inp.pallet_width / 2
    length = math.hypot(wx, wy)
    if length > inp.tolerance:
        wx /= length
        wy /= length
    else:
        wx = wy = 0.0
    info.wx, info.wy = wx, wy

    if math.hypot(vx, vy) <= DOT_EPS:
        vx, vy = wx, wy
        info.used_outward = True
    info.vx, info.vy = vx, vy

    # Kandidaten: freie Richtungen, sonst die mit den wenigsten belegten Zonen
    candidates = [k for k in range(8) if info.free & (1 << k)]
    if not candidates:
        info.no_free = True
        fewest = min(blocked_count(info.mask, k) for k in range(8))
        candidates = [k for k in range(8) if blocked_count(info.mask, k) == fewest]

    best_k = -1
    best_v = 0.0
    best_w = 0.0
    for k in APPROACH_PRIORITY:
        if k not in candidates:
            continue
        score_v = DIR_X[k] * vx + DIR_Y[k] * vy
        score_w = DIR_X[k] * wx + DIR_Y[k] * wy
        if (best_k < 0
                or score_v > best_v + DOT_EPS
                or (abs(score_v - best_v) <= DOT_EPS and score_w > best_w + DOT_EPS)):
            best_k, best_v, best_w = k, score_v, score_w
    info.direction = best_k
    return info

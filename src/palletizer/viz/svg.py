"""SVG-Zeichnung einer Lage – ohne externe Pakete.

Die Zeichnung zeigt das Grundsystem von oben (wie die PDF-Zeichnung):
E1 unten links, X nach rechts, Y nach oben. Das Muster liegt physikalisch fest,
der gewählte Palettennullpunkt wird mit seinen Achsen X/Y eingezeichnet.

Farben und Linienstärken kommen aus CSS-Klassen (siehe report/html.py),
damit heller/dunkler Modus und Druck an einer Stelle gesteuert werden.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from ..approach import zones as zone_rects
from ..constants import DIR_X, DIR_Y, WARN_OVERHANG
from ..gripper import plate_size
from ..model import Box, BoxResult, Inputs, LayerResult, VariantLayout
from ..transform import CORNER_SIGNS, corner_point

ZONE_NAMES = ("O", "NO", "N", "NW", "W", "SW", "S", "SO")


@dataclass
class Frame:
    """Umrechnung Grundsystem (mm, Y nach oben) -> SVG-Koordinaten (Y nach unten)."""
    min_x: float
    max_y: float
    width: float
    height: float

    @classmethod
    def around(cls, x1: float, y1: float, x2: float, y2: float, margin: float) -> "Frame":
        return cls(min_x=x1 - margin, max_y=y2 + margin,
                   width=x2 - x1 + 2 * margin, height=y2 - y1 + 2 * margin)

    def x(self, x: float) -> float:
        return x - self.min_x

    def y(self, y: float) -> float:
        return self.max_y - y

    def rect(self, x1: float, y1: float, x2: float, y2: float) -> str:
        return (f'x="{self.x(x1):.2f}" y="{self.y(y2):.2f}" '
                f'width="{x2 - x1:.2f}" height="{y2 - y1:.2f}"')


def _arrow(frame: Frame, x1: float, y1: float, x2: float, y2: float,
           head: float, cls: str) -> str:
    """Pfeil von (x1, y1) nach (x2, y2) im Grundsystem, Spitze als gefülltes Dreieck."""
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 0:
        return ""
    ux, uy = dx / length, dy / length
    bx, by = x2 - ux * head, y2 - uy * head          # Basis der Spitze
    px, py = -uy * head * 0.45, ux * head * 0.45     # halbe Breite der Spitze
    points = " ".join(f"{frame.x(px_):.2f},{frame.y(py_):.2f}" for px_, py_ in (
        (x2, y2), (bx + px, by + py), (bx - px, by - py)))
    return (f'<g class="{cls}"><line x1="{frame.x(x1):.2f}" y1="{frame.y(y1):.2f}" '
            f'x2="{frame.x(bx):.2f}" y2="{frame.y(by):.2f}"/>'
            f'<polygon points="{points}"/></g>')


def _frame_for(inp: Inputs, boxes: list[tuple[float, float, float, float]],
               margin: float) -> Frame:
    x1, y1, x2, y2 = 0.0, 0.0, inp.pallet_length, inp.pallet_width
    for bx1, by1, bx2, by2 in boxes:
        x1, y1 = min(x1, bx1), min(y1, by1)
        x2, y2 = max(x2, bx2), max(y2, by2)
    return Frame.around(x1, y1, x2, y2, margin)


def _pallet(frame: Frame, inp: Inputs, font: float, corner_labels: bool) -> list[str]:
    L, B = inp.pallet_length, inp.pallet_width
    parts = [f'<rect class="pallet" {frame.rect(0, 0, L, B)}/>']
    if corner_labels:
        parts.append(f'<text class="dim" x="{frame.x(L / 2):.2f}" y="{frame.y(0) + font * 1.6:.2f}" '
                     f'text-anchor="middle" font-size="{font:.1f}">{L:g} mm (X)</text>')
        parts.append(f'<text class="dim" x="{frame.x(0) - font * 1.0:.2f}" y="{frame.y(B / 2):.2f}" '
                     f'text-anchor="middle" font-size="{font:.1f}" '
                     f'transform="rotate(-90 {frame.x(0) - font * 1.0:.2f} {frame.y(B / 2):.2f})">'
                     f'{B:g} mm (Y)</text>')
        offset = font * 0.9
        for corner in (1, 2, 3, 4):
            cx, cy = corner_point(corner, L, B)
            sx = -1 if corner in (1, 4) else 1
            sy = -1 if corner in (1, 2) else 1
            anchor = "end" if sx < 0 else "start"
            parts.append(f'<text class="corner" x="{frame.x(cx + sx * offset):.2f}" '
                         f'y="{frame.y(cy + sy * offset) + font * 0.35:.2f}" text-anchor="{anchor}" '
                         f'font-size="{font * 0.8:.1f}">E{corner}</text>')
    return parts


def _origin(frame: Frame, inp: Inputs, font: float) -> list[str]:
    """Palettennullpunkt mit den Achsen des Ausgabesystems."""
    corner = inp.origin_corner
    ox, oy = corner_point(corner, inp.pallet_length, inp.pallet_width)
    sx, sy = CORNER_SIGNS[corner]
    axis = min(inp.pallet_length, inp.pallet_width) * 0.2
    head = font * 0.7
    parts = [
        _arrow(frame, ox, oy, ox + sx * axis, oy, head, "axis"),
        _arrow(frame, ox, oy, ox, oy + sy * axis, head, "axis"),
        f'<circle class="origin" cx="{frame.x(ox):.2f}" cy="{frame.y(oy):.2f}" r="{font * 0.35:.2f}"/>',
        f'<text class="axis-label" x="{frame.x(ox + sx * (axis + font * 0.8)):.2f}" '
        f'y="{frame.y(oy) + font * 0.35:.2f}" text-anchor="middle" font-size="{font:.1f}">X</text>',
        f'<text class="axis-label" x="{frame.x(ox):.2f}" '
        f'y="{frame.y(oy + sy * (axis + font * 0.8)) + font * 0.35:.2f}" text-anchor="middle" '
        f'font-size="{font:.1f}">Y</text>',
    ]
    return parts


def render_layer(result: LayerResult, *, prefix: str = "main", step: int | None = None,
                 interactive: bool = True, compact: bool = False, max_width: str = "100%") -> str:
    """Zeichnet die berechnete Lage.

    step        : nur Kartons mit Nr <= step gelten als abgelegt, Nr == step ist hervorgehoben
                  (None = alle abgelegt, kein Karton hervorgehoben)
    interactive : Prüfzonen und Saugplatten für jeden Karton mitschreiben (per JS umschaltbar)
    compact     : kleine Darstellung ohne Beschriftungen (für "Schritt für Schritt")
    """
    inp = result.inputs
    boxes = result.boxes
    extents = [(b.x_base - b.size_x / 2, b.y_base - b.size_y / 2,
                b.x_base + b.size_x / 2, b.y_base + b.size_y / 2) for b in boxes]
    for b in boxes:
        if b.gripper.needed:
            px, py = plate_size(b.rot, inp.plate_ext_conv, inp.plate_ext_cross)
            extents.append((b.x_base - px / 2, b.y_base - py / 2,
                            b.x_base + px / 2, b.y_base + py / 2))
    font = max(inp.pallet_length, inp.pallet_width) / 40
    frame = _frame_for(inp, extents, font * (1.2 if compact else 3.2))

    parts = [f'<svg class="layer{" compact" if compact else ""}" id="{prefix}-svg" '
             f'viewBox="0 0 {frame.width:.2f} {frame.height:.2f}" '
             f'style="max-width:{max_width}" role="img" '
             f'aria-label="Lagenbild {escape(result.pattern_id)}" xmlns="http://www.w3.org/2000/svg">']
    parts += _pallet(frame, inp, font, corner_labels=not compact)

    layout = result.chosen_layout
    if layout is not None and not compact:
        for block in layout.blocks:
            parts.append(f'<rect class="block-outline" {frame.rect(block.x0, block.y0, block.x0 + block.width, block.y0 + block.height)}/>')
            parts.append(f'<text class="block-label" x="{frame.x(block.x0) + font * 0.3:.2f}" '
                         f'y="{frame.y(block.y0 + block.height) - font * 0.3:.2f}" '
                         f'font-size="{font * 0.7:.1f}">Block {escape(block.id)}</text>')

    for b in boxes:
        parts.append(_box(frame, b, inp, step, compact))

    if interactive and not compact:
        for b in boxes:
            parts.append(_zones(frame, b, inp, step))
            parts.append(_plates(frame, b, inp, step))

    if not compact:
        parts += _origin(frame, inp, font)
    parts.append("</svg>")
    return "\n".join(parts)


def _edge_distance(half_x: float, half_y: float, ux: float, uy: float) -> float:
    """Abstand von der Kartonmitte bis zum Rand in Richtung (ux, uy)."""
    distance = float("inf")
    if abs(ux) > 1e-9:
        distance = min(distance, half_x / abs(ux))
    if abs(uy) > 1e-9:
        distance = min(distance, half_y / abs(uy))
    return distance


def _box_state(no: int, step: int | None) -> str:
    if step is None:
        return "placed"
    if no < step:
        return "placed"
    if no == step:
        return "placed current"
    return "ghost"


def _box(frame: Frame, b: BoxResult, inp: Inputs, step: int | None, compact: bool) -> str:
    x1, x2 = b.x_base - b.size_x / 2, b.x_base + b.size_x / 2
    y1, y2 = b.y_base - b.size_y / 2, b.y_base + b.size_y / 2
    small = min(b.size_x, b.size_y)
    classes = f"box rot{b.rot} {_box_state(b.no, step)}"
    if b.warnings & WARN_OVERHANG:
        classes += " overhang"
    title = (f"Nr {b.no} ({b.key}): X {b.x:.1f}, Y {b.y:.1f}, Rot {b.rot}°, "
             f"Anfahrt {b.approach_angle}°, Saugplatte {'aus' if b.extend_plate else 'ein'}gefahren")
    parts = [f'<g class="{classes}" data-no="{b.no}"><title>{escape(title)}</title>',
             f'<rect class="body" {frame.rect(x1, y1, x2, y2)}/>']

    num_font = max(min(small * 0.28, 90.0), 18.0)
    if compact:
        num_font = max(min(small * 0.45, 140.0), 30.0)
        parts.append(f'<text class="num" x="{frame.x(b.x_base):.2f}" y="{frame.y(b.y_base) + num_font * 0.35:.2f}" '
                     f'text-anchor="middle" font-size="{num_font:.1f}">{b.no}</text></g>')
        return "".join(parts)

    # Förderachse des Kartons (gestrichelt): zeigt die Orientierung
    if b.rot == 0:
        ax1, ay1, ax2, ay2 = x1 + b.size_x * 0.1, b.y_base, x2 - b.size_x * 0.1, b.y_base
    else:
        ax1, ay1, ax2, ay2 = b.x_base, y1 + b.size_y * 0.1, b.x_base, y2 - b.size_y * 0.1
    parts.append(f'<line class="conv-axis" x1="{frame.x(ax1):.2f}" y1="{frame.y(ay1):.2f}" '
                 f'x2="{frame.x(ax2):.2f}" y2="{frame.y(ay2):.2f}"/>')

    # Anfahrpfeil am Rand der Anfahrseite: kommt aus Richtung θ, zeigt zur Kartonmitte
    k = b.approach_angle_base // 45
    edge = _edge_distance(b.size_x / 2, b.size_y / 2, DIR_X[k], DIR_Y[k])
    tail = edge * 0.96
    tip = edge * 0.56
    parts.append(_arrow(frame, b.x_base + DIR_X[k] * tail, b.y_base + DIR_Y[k] * tail,
                        b.x_base + DIR_X[k] * tip, b.y_base + DIR_Y[k] * tip,
                        max(small * 0.08, 12.0), "approach"))

    # Mittelpunkt
    c = max(small * 0.05, 6.0)
    parts.append(f'<path class="center" d="M{frame.x(b.x_base - c):.2f} {frame.y(b.y_base):.2f} '
                 f'H{frame.x(b.x_base + c):.2f} M{frame.x(b.x_base):.2f} {frame.y(b.y_base - c):.2f} '
                 f'V{frame.y(b.y_base + c):.2f}"/>')

    # Nummer und Beschriftung (oberhalb bzw. unterhalb der Mitte)
    label_font = num_font * 0.42
    warn = " ⚠" if b.warnings & WARN_OVERHANG else ""
    parts.append(f'<text class="num" x="{frame.x(b.x_base):.2f}" y="{frame.y(b.y_base) - c * 1.6:.2f}" '
                 f'text-anchor="middle" font-size="{num_font:.1f}">{b.no}</text>')
    parts.append(f'<text class="label" x="{frame.x(b.x_base):.2f}" '
                 f'y="{frame.y(b.y_base) + c * 1.6 + label_font:.2f}" text-anchor="middle" '
                 f'font-size="{label_font:.1f}">{escape(b.key)} · {b.rot}°{warn}</text>')
    parts.append("</g>")
    return "".join(parts)


def _zones(frame: Frame, b: BoxResult, inp: Inputs, step: int | None) -> str:
    """Belegte Prüfzonen und Vorposition (nur für den hervorgehobenen Karton sichtbar)."""
    box =Box(b.block_id, b.col, b.row, b.x_base, b.y_base, b.size_x, b.size_y, b.rot)
    visible = " visible" if step == b.no else ""
    parts = [f'<g class="zones{visible}" data-no="{b.no}">']
    rects = zone_rects(box, inp.approach_dist)
    for k in range(8):
        zx1, zx2, zy1, zy2 = rects[k]
        state = "occupied" if b.neighbor_mask & (1 << k) else "free"
        parts.append(f'<rect class="zone {state}" {frame.rect(zx1, zy1, zx2, zy2)}/>')
    # Vorposition als Umriss
    k = b.approach_angle_base // 45
    dx, dy = inp.approach_dist * DIR_X[k], inp.approach_dist * DIR_Y[k]
    parts.append(f'<rect class="pre-position" {frame.rect(box.x1 + dx, box.y1 + dy, box.x2 + dx, box.y2 + dy)}/>')
    parts.append("</g>")
    return "".join(parts)


def _plates(frame: Frame, b: BoxResult, inp: Inputs, step: int | None) -> str:
    """Grundplatte (gestrichelt) und ggf. ausgefahrene Platte (gepunktet)."""
    visible = " visible" if step == b.no else ""
    parts = [f'<g class="plates{visible}" data-no="{b.no}">']
    px, py = plate_size(b.rot, inp.plate_conv, inp.plate_cross)
    parts.append(f'<rect class="plate base" {frame.rect(b.x_base - px / 2, b.y_base - py / 2, b.x_base + px / 2, b.y_base + py / 2)}/>')
    if b.gripper.needed:
        ex, ey = plate_size(b.rot, inp.plate_ext_conv, inp.plate_ext_cross)
        state = "ext-ok" if b.extend_plate else "ext-blocked"
        parts.append(f'<rect class="plate {state}" {frame.rect(b.x_base - ex / 2, b.y_base - ey / 2, b.x_base + ex / 2, b.y_base + ey / 2)}/>')
    parts.append("</g>")
    return "".join(parts)


def render_variant(layout: VariantLayout, inp: Inputs, chosen: bool) -> str:
    """Kleine Zeichnung einer Orientierungsvariante (für den Variantenvergleich)."""
    font = max(inp.pallet_length, inp.pallet_width) / 40
    extents = [(b.x1, b.y1, b.x2, b.y2) for b in layout.boxes]
    frame = _frame_for(inp, extents, font * 1.5)
    parts = [f'<svg class="layer variant{" chosen" if chosen else ""}" '
             f'viewBox="0 0 {frame.width:.2f} {frame.height:.2f}" role="img" '
             f'aria-label="Variante {layout.name}" xmlns="http://www.w3.org/2000/svg">']
    parts += _pallet(frame, inp, font, corner_labels=False)
    for b in layout.boxes:
        over = (b.x1 < -inp.max_overhang - inp.tolerance or b.y1 < -inp.max_overhang - inp.tolerance
                or b.x2 > inp.pallet_length + inp.max_overhang + inp.tolerance
                or b.y2 > inp.pallet_width + inp.max_overhang + inp.tolerance)
        classes = f"box rot{b.rot} placed" + (" overhang" if over else "")
        small = min(b.size_x, b.size_y)
        size = max(min(small * 0.3, 90.0), 20.0)
        parts.append(f'<g class="{classes}"><title>{escape(b.key)}: {b.rot}°</title>'
                     f'<rect class="body" {frame.rect(b.x1, b.y1, b.x2, b.y2)}/>'
                     f'<text class="label" x="{frame.x(b.cx):.2f}" y="{frame.y(b.cy) + size * 0.35:.2f}" '
                     f'text-anchor="middle" font-size="{size:.1f}">{escape(b.key)}</text></g>')
    parts.append("</svg>")
    return "\n".join(parts)


def zone_names(mask: int) -> str:
    """Klartext einer Nachbarmaske, z. B. "W, SW" (leer = "–")."""
    names = [ZONE_NAMES[k] for k in range(8) if mask & (1 << k)]
    return ", ".join(names) if names else "–"

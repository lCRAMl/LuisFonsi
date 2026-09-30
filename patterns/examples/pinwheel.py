"""Beispiel-Plugin: Windmühle (Pinwheel).

Vier Arme liegen gegen den Uhrzeigersinn um ein Loch in der Mitte:

    +----+-----------+
    | D  |     C     |
    |    +-----+-----+
    |    | Loch|     |
    +----+-----+  B  |
    |     A    |     |
    +----------+-----+

Jeder Arm besteht aus `arm_boxes` Kartons nebeneinander.
Arm A und C liegen in Grundorientierung, Arm B und D um 90° gedreht.
"""

from palletizer.model import BlockDef


def build(px: float, py: float, gap: float, params: dict) -> list[BlockDef] | None:
    n = int(params.get("arm_boxes", 1))
    arm_length = px                      # Länge eines Arms
    arm_width = n * py + (n - 1) * gap   # Breite eines Arms
    if arm_length < arm_width:
        return None                      # Arme würden sich überlappen
    return [
        BlockDef("A", 0.0, 0.0, 1, n, False),
        BlockDef("B", arm_length + gap, 0.0, n, 1, True),
        BlockDef("C", arm_width + gap, arm_length + gap, 1, n, False),
        BlockDef("D", 0.0, arm_width + gap, n, 1, True),
    ]

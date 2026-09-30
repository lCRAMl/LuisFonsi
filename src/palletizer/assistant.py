"""Musterassistent: schlägt zu einem Karton die passenden Layerpatterns vor.

Jedes Muster der Bibliothek wird mit den gegebenen Eingaben komplett berechnet.
Rangfolge:
    1. passt (kein Fehler, kein Überstand über dem erlaubten Maß)
    2. mehr Kartons
    3. höhere Flächennutzung
    4. weniger gedrehte Kartons
    5. kleinere Musternummer
Der Assistent ist nur eine Hilfe in Python; die SPS braucht ihn nicht.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .calculator import calculate
from .constants import WARN_OVERHANG
from .model import Inputs, LayerResult
from .patterns import PatternLibrary


@dataclass
class Suggestion:
    pattern_id: str
    pattern_no: int
    name: str
    fits: bool
    result: LayerResult

    @property
    def box_count(self) -> int:
        return self.result.box_count


def suggest(library: PatternLibrary, base: Inputs) -> list[Suggestion]:
    """Berechnet alle Muster für den Karton aus `base` und liefert sie sortiert."""
    suggestions = []
    for pattern in library.all():
        result = calculate(replace(base, pattern=pattern.id), library)
        if not result.ok:
            continue
        fits = not result.warnings & WARN_OVERHANG
        suggestions.append(Suggestion(pattern.id, pattern.number, pattern.name, fits, result))
    suggestions.sort(key=lambda s: (not s.fits, -s.result.box_count, -round(s.result.area_usage, 6),
                                    s.result.rotated_count, s.pattern_no))
    return suggestions

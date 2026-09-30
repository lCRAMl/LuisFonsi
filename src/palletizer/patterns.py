"""Layerpattern-Bibliothek.

Muster werden als TOML-Dateien im Ordner `patterns/` beschrieben (eine Datei
pro Muster). Muster, die nicht in den Standardaufbau passen, können als
Python-Plugin ergänzt werden. Das Dateiformat ist in `patterns/README.md`
beschrieben.

Standardaufbau (alle Muster aus dem PDF):
    Block A: cols x rows Kartons in Grundorientierung, links
    Block B: optional, cols x rows Kartons um 90° gedreht,
             rechts neben Block A, oben bündig mit Block A
"""

from __future__ import annotations

import importlib.util
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .geometry import extent
from .model import BlockDef

# Plugin-Signatur: build(px, py, gap, params) -> list[BlockDef] | None
#   px, py : Kartonmaß in X/Y in der Grundorientierung der Variante
#   gap    : Spaltmaß
#   params : Parameter aus der TOML-Datei (Abschnitt [params])
#   Rückgabe None = Muster mit diesem Karton in dieser Variante nicht darstellbar
PluginFunc = Callable[[float, float, float, dict], "list[BlockDef] | None"]


class PatternError(Exception):
    """Fehler in einer Musterdefinition."""


@dataclass
class Pattern:
    """Ein Layerpattern."""
    id: str
    number: int
    name: str
    drawn_long_side: str = "x"            # Lage der Kartons von Block A in der Zeichnung
    block_a: tuple[int, int] | None = None
    block_b: tuple[int, int] | None = None
    plugin: PluginFunc | None = None
    params: dict = field(default_factory=dict)
    start_corner: int | None = None       # Übersteuerung der Startecke (Grundsystem)
    fill: str = "columns"                 # Füllrichtung innerhalb eines Blocks
    order: list[str] | None = None        # explizite Ablagereihenfolge ("A.1.3", ...)
    description: str = ""
    source: Path | None = None

    @property
    def fixed_count(self) -> int | None:
        """Anzahl Kartons, sofern sie ohne Karton-Maße feststeht (Standardaufbau)."""
        if self.plugin is not None or self.block_a is None:
            return None
        count = self.block_a[0] * self.block_a[1]
        if self.block_b is not None:
            count += self.block_b[0] * self.block_b[1]
        return count

    def build_blocks(self, px: float, py: float, gap: float) -> list[BlockDef] | None:
        """Liefert die Blockliste im Lagen-System (vor dem Zentrieren)."""
        if self.plugin is not None:
            return self.plugin(px, py, gap, self.params)
        return build_standard_blocks(self.block_a, self.block_b, px, py, gap)


def build_standard_blocks(block_a: tuple[int, int], block_b: tuple[int, int] | None,
                          px: float, py: float, gap: float) -> list[BlockDef]:
    """Standardaufbau: Block A links, Block B (90° gedreht) rechts daneben, oben bündig.

    Block A: Kartonmaß (px, py)       -> Breite D(colsA, px), Höhe D(rowsA, py)
    Block B: Kartonmaß (py, px)       -> Höhe D(rowsB, px)
    Lagenhöhe H = max(Höhe A, Höhe B); jeder Block beginnt bei y0 = H - Blockhöhe.
    """
    a_cols, a_rows = block_a
    a_width = extent(a_cols, px, gap)
    a_height = extent(a_rows, py, gap)
    if block_b is None:
        return [BlockDef("A", 0.0, 0.0, a_cols, a_rows, False)]

    b_cols, b_rows = block_b
    b_height = extent(b_rows, px, gap)   # gedreht: Y-Maß des Kartons ist px
    layer_height = max(a_height, b_height)
    return [
        BlockDef("A", 0.0, layer_height - a_height, a_cols, a_rows, False),
        BlockDef("B", a_width + gap, layer_height - b_height, b_cols, b_rows, True),
    ]


class PatternLibrary:
    """Sammlung aller geladenen Muster, auffindbar über ID oder Nummer."""

    def __init__(self, patterns: list[Pattern]):
        self._by_id: dict[str, Pattern] = {}
        self._by_number: dict[int, Pattern] = {}
        for pattern in patterns:
            key = pattern.id.upper()
            if key in self._by_id:
                raise PatternError(f"Pattern-ID {pattern.id} ist doppelt vergeben "
                                   f"({self._by_id[key].source}, {pattern.source})")
            if pattern.number in self._by_number:
                raise PatternError(f"Pattern-Nummer {pattern.number} ist doppelt vergeben "
                                   f"({self._by_number[pattern.number].source}, {pattern.source})")
            self._by_id[key] = pattern
            self._by_number[pattern.number] = pattern

    @classmethod
    def load(cls, directory: Path | str | None = None) -> "PatternLibrary":
        """Lädt alle *.toml-Dateien aus `directory` (rekursiv)."""
        directory = Path(directory) if directory is not None else default_pattern_dir()
        if not directory.is_dir():
            raise PatternError(f"Pattern-Ordner nicht gefunden: {directory}")
        patterns = []
        for path in sorted(directory.rglob("*.toml")):
            patterns.append(load_pattern_file(path))
        return cls(patterns)

    def find(self, key: str | int) -> Pattern | None:
        """Sucht ein Muster über ID ("EU36") oder Nummer (36 bzw. "36")."""
        text = str(key).strip()
        if text.isdigit():
            return self._by_number.get(int(text))
        return self._by_id.get(text.upper())

    def all(self) -> list[Pattern]:
        return sorted(self._by_number.values(), key=lambda p: p.number)


def default_pattern_dir() -> Path:
    """Standard-Ordner `patterns/` im Projektverzeichnis."""
    return Path(__file__).resolve().parents[2] / "patterns"


def load_pattern_file(path: Path) -> Pattern:
    """Liest eine Musterdefinition aus einer TOML-Datei."""
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PatternError(f"{path}: Datei nicht lesbar ({exc})") from exc

    def fail(message: str) -> PatternError:
        return PatternError(f"{path}: {message}")

    for key in ("id", "number", "name"):
        if key not in data:
            raise fail(f"Pflichtfeld '{key}' fehlt")

    pattern = Pattern(
        id=str(data["id"]),
        number=int(data["number"]),
        name=str(data["name"]),
        drawn_long_side=str(data.get("drawn_long_side", "x")).lower(),
        description=str(data.get("description", "")),
        params=dict(data.get("params", {})),
        source=path,
    )
    if pattern.number <= 0:
        raise fail("'number' muss > 0 sein")
    if pattern.drawn_long_side not in ("x", "y"):
        raise fail("'drawn_long_side' muss \"x\" oder \"y\" sein")

    if "plugin" in data:
        pattern.plugin = _load_plugin(str(data["plugin"]), path.parent, fail)
    elif "block_a" in data:
        pattern.block_a = _read_block(data["block_a"], "block_a", fail)
        if "block_b" in data:
            pattern.block_b = _read_block(data["block_b"], "block_b", fail)
    else:
        raise fail("Es muss entweder 'block_a' oder 'plugin' angegeben sein")

    sequence = data.get("sequence", {})
    if "start_corner" in sequence:
        corner = int(sequence["start_corner"])
        if corner not in (1, 2, 3, 4):
            raise fail("'sequence.start_corner' muss 1..4 sein")
        pattern.start_corner = corner
    pattern.fill = str(sequence.get("fill", "columns"))
    if pattern.fill not in ("columns", "rows"):
        raise fail("'sequence.fill' muss \"columns\" oder \"rows\" sein")
    if "order" in sequence:
        pattern.order = [str(item) for item in sequence["order"]]
    return pattern


def _read_block(data: dict, name: str, fail) -> tuple[int, int]:
    try:
        cols = int(data["cols"])
        rows = int(data["rows"])
    except (KeyError, TypeError, ValueError) as exc:
        raise fail(f"'{name}' braucht ganzzahlige Werte 'cols' und 'rows'") from exc
    if cols < 1 or rows < 1:
        raise fail(f"'{name}': 'cols' und 'rows' müssen >= 1 sein")
    return cols, rows


def _load_plugin(spec: str, base: Path, fail) -> PluginFunc:
    """Lädt eine Plugin-Funktion aus "datei.py:funktion" (relativ zur TOML-Datei)."""
    file_name, _, func_name = spec.partition(":")
    if not file_name or not func_name:
        raise fail("'plugin' muss das Format \"datei.py:funktion\" haben")
    module_path = (base / file_name).resolve()
    if not module_path.is_file():
        raise fail(f"Plugin-Datei nicht gefunden: {module_path}")
    module_spec = importlib.util.spec_from_file_location(
        f"palletizer_plugin_{module_path.stem}", module_path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    func = getattr(module, func_name, None)
    if not callable(func):
        raise fail(f"Plugin-Funktion '{func_name}' nicht gefunden in {module_path}")
    return func

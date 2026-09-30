"""Datentypen der Berechnung.

Jede Klasse entspricht einem späteren UDT in der SPS. Alle Maße in mm,
alle Koordinaten im "Grundsystem" (siehe unten), sofern nicht anders angegeben.

Grundsystem: Ursprung in Ecke E1 (unten links in der PDF-Zeichnung),
X entlang der Palettenlänge, Y entlang der Palettenbreite. Die Ecken sind
gegen den Uhrzeigersinn nummeriert: E1 unten links, E2 unten rechts,
E3 oben rechts, E4 oben links.
"""

from dataclasses import dataclass, field, fields


@dataclass
class Inputs:
    """Eingangsgrößen der Berechnung."""
    box_length_conv: float          # Kartonmaß in Förderrichtung
    box_width_conv: float           # Kartonmaß quer zur Förderrichtung
    pattern: str                    # Pattern-ID ("EU36") oder Pattern-Nummer ("36")
    pallet_length: float = 1200.0   # Palettenmaß in X
    pallet_width: float = 800.0     # Palettenmaß in Y
    origin_corner: int = 1          # Palettennullpunkt, Ecke 1..4
    orientation_mode: int = 0       # 0 = automatisch, 1 = Variante X, 2 = Variante Y
    gap: float = 0.0                # Spaltmaß zwischen den Kartons
    max_overhang: float = 0.0       # erlaubter Überstand je Seite
    plate_conv: float = 600.0       # Saugplatte in Förderrichtung
    plate_cross: float = 400.0      # Saugplatte quer zur Förderrichtung
    plate_ext_conv: float = 600.0   # ausgefahrene Saugplatte in Förderrichtung
    plate_ext_cross: float = 1400.0  # ausgefahrene Saugplatte quer zur Förderrichtung
    approach_dist: float = 30.0     # Abstand der Vorposition in X/Y
    approach_height: float = 20.0   # Höhe der Vorposition über der Ablage (Z)
    tolerance: float = 0.1          # Toleranz eps für Vergleiche

    def __post_init__(self):
        """Typen vereinheitlichen (z. B. 680 aus TOML -> 680.0), wie später in der SPS (LReal/Int)."""
        for f in fields(self):
            value = getattr(self, f.name)
            if f.type in ("float", float):
                setattr(self, f.name, float(value))
            elif f.type in ("int", int):
                setattr(self, f.name, int(value))
            elif f.type in ("str", str):
                setattr(self, f.name, str(value))

    @classmethod
    def from_dict(cls, data: dict) -> "Inputs":
        """Erzeugt die Eingaben aus einem Dictionary (z. B. aus einer TOML-Datei)."""
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"Unbekannte Eingabeparameter: {', '.join(unknown)}")
        return cls(**data)


@dataclass
class BlockDef:
    """Block, wie ihn eine Musterdefinition liefert (Lagen-System, vor dem Zentrieren).

    `rotated` bezieht sich auf die Grundorientierung der Variante:
    False = Karton liegt wie in der Variante vorgegeben, True = um 90° gedreht.
    """
    id: str
    x0: float
    y0: float
    cols: int
    rows: int
    rotated: bool


@dataclass
class Block:
    """Aufgelöster Block im Grundsystem (nach dem Zentrieren)."""
    id: str
    x0: float          # linke untere Ecke des Blocks
    y0: float
    cols: int          # Spalten (in X)
    rows: int          # Reihen (in Y)
    rotated: bool
    size_x: float      # Kartonmaß in X innerhalb dieses Blocks
    size_y: float      # Kartonmaß in Y innerhalb dieses Blocks
    width: float       # Blockmaß in X
    height: float      # Blockmaß in Y

    @property
    def count(self) -> int:
        return self.cols * self.rows


@dataclass
class Box:
    """Ein Karton der Lage im Grundsystem."""
    block_id: str
    col: int           # Spalte im Block, ab 1
    row: int           # Reihe im Block, ab 1
    cx: float          # Mittelpunkt
    cy: float
    size_x: float      # Grundfläche in X
    size_y: float      # Grundfläche in Y
    rot: int           # 0 oder 90, bezogen auf die Lage auf dem Förderband

    @property
    def key(self) -> str:
        """Eindeutige Bezeichnung, z. B. "A.1.3" (Block.Spalte.Reihe)."""
        return f"{self.block_id}.{self.col}.{self.row}"

    @property
    def x1(self) -> float:
        return self.cx - self.size_x / 2

    @property
    def x2(self) -> float:
        return self.cx + self.size_x / 2

    @property
    def y1(self) -> float:
        return self.cy - self.size_y / 2

    @property
    def y2(self) -> float:
        return self.cy + self.size_y / 2


@dataclass
class VariantLayout:
    """Ergebnis der Stufen S2-S4 für eine Orientierungsvariante.

    Variante "X": Kartons von Block A mit der Langseite in X.
    Variante "Y": Kartons von Block A mit der Langseite in Y.
    """
    name: str
    valid: bool = True
    error_code: int = 0
    blocks: list[Block] = field(default_factory=list)
    boxes: list[Box] = field(default_factory=list)
    layer_size_x: float = 0.0      # Lagenmaß W_X
    layer_size_y: float = 0.0      # Lagenmaß W_Y
    overhang_x: float = 0.0        # Überstand je Seite in X
    overhang_y: float = 0.0        # Überstand je Seite in Y
    overhang_sum: float = 0.0      # Rangkriterium: max(0, W_X - L_P) + max(0, W_Y - B_P)
    rotated_count: int = 0         # Anzahl Kartons mit Rot = 90

    @property
    def count(self) -> int:
        return len(self.boxes)


@dataclass
class SequenceInfo:
    """Zwischenergebnis der Stufe S5 (Startecke der Ablage)."""
    start_corner: int = 1
    source_x: str = ""             # Begründung für die X-Seite
    source_y: str = ""             # Begründung für die Y-Seite
    loose_count: int = 0           # Kartons im "lockeren" Teil (Blöcke mit weniger Kartons)
    loose_cx: float = 0.0
    loose_cy: float = 0.0
    gap_area: float = 0.0          # Lückenfläche innerhalb des Lagenmaßes
    gap_cx: float = 0.0
    gap_cy: float = 0.0


@dataclass
class ApproachInfo:
    """Zwischenergebnis der Stufe S6 (Annäherungsrichtung) für einen Karton."""
    mask: int = 0                  # Bit k = Nachbarzone k belegt
    free: int = 0                  # Bit k = Richtung k frei
    vx: float = 0.0                # Wunschvektor (weg von den Nachbarn)
    vy: float = 0.0
    wx: float = 0.0                # Vektor Palettenmitte -> Karton (normiert)
    wy: float = 0.0
    used_outward: bool = False     # Wunschvektor war 0, Vektor nach außen verwendet
    direction: int = 0             # gewählte Richtung 0..7
    no_free: bool = False          # keine Richtung frei

    @property
    def angle(self) -> int:
        return self.direction * 45


@dataclass
class GripperInfo:
    """Zwischenergebnis der Stufe S7 (Saugplatte) für einen Karton."""
    needed: bool = False           # Karton länger als die Grundplatte in Ausfahrachse
    allowed: bool = False          # ausgefahrene Platte überdeckt keinen abgelegten Karton
    extend: bool = False           # Ausgabe: 1 = ausfahren


@dataclass
class BoxResult:
    """Ausgabe für einen Karton (entspricht dem Ergebnis-UDT der SPS)."""
    no: int                        # Ablagereihenfolge, ab 1
    block_id: str
    col: int
    row: int
    x: float                       # Mittelpunkt im Ausgabesystem (gewählter Nullpunkt)
    y: float
    rot: int                       # 0 oder 90
    approach_angle: int            # 0, 45, ..., 315 im Ausgabesystem
    pre_dx: float                  # Versatz der Vorposition im Ausgabesystem
    pre_dy: float
    pre_dz: float
    extend_plate: bool             # 1 = Saugplatte ausfahren
    neighbor_mask: int             # Nachbarmaske (Grundsystem)
    warnings: int                  # Warnbits dieses Kartons
    # Zwischenwerte im Grundsystem (für Kontrolle und Report)
    x_base: float = 0.0
    y_base: float = 0.0
    size_x: float = 0.0
    size_y: float = 0.0
    approach_angle_base: int = 0
    approach: ApproachInfo = field(default_factory=ApproachInfo)
    gripper: GripperInfo = field(default_factory=GripperInfo)

    @property
    def key(self) -> str:
        return f"{self.block_id}.{self.col}.{self.row}"


@dataclass
class LayerResult:
    """Gesamtergebnis einer Lage (Kopfdaten + Kartonliste + Zwischenergebnisse)."""
    inputs: Inputs
    error_code: int = 0
    pattern_id: str = ""
    pattern_no: int = 0
    pattern_name: str = ""
    box_long: float = 0.0          # Langseite des Kartons
    box_short: float = 0.0         # Kurzseite des Kartons
    variant: str = ""              # gewählte Variante "X" oder "Y"
    variant_reason: str = ""
    variants: list[VariantLayout] = field(default_factory=list)
    sequence: SequenceInfo | None = None
    boxes: list[BoxResult] = field(default_factory=list)
    warnings: int = 0              # Sammelwarnung (ODER aller Warnbits)
    layer_size_x: float = 0.0
    layer_size_y: float = 0.0
    overhang_x: float = 0.0
    overhang_y: float = 0.0
    rotated_count: int = 0
    area_usage: float = 0.0        # Kartonfläche / Palettenfläche in %

    @property
    def ok(self) -> bool:
        return self.error_code == 0

    @property
    def box_count(self) -> int:
        return len(self.boxes)

    @property
    def chosen_layout(self) -> VariantLayout | None:
        for layout in self.variants:
            if layout.name == self.variant:
                return layout
        return None

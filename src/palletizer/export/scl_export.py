"""SCL-Quellen für TIA Portal (S7-1500), Import als "Externe Quelle" und "Bausteine aus Quelle generieren".

layer_scl    : UDTs typPalInput, typPalBox, typPalLayer + DB "DB_PalLayer" mit dem berechneten Ergebnis
patterns_scl : UDT typPalPattern + DB "DB_PalPatterns" mit allen Musterdefinitionen im Standardaufbau
"""

from __future__ import annotations

from datetime import datetime

from .. import __version__
from ..constants import (ERROR_TEXTS, MAX_BOXES, MAX_PATTERNS, WARNING_TEXTS)
from ..model import LayerResult
from ..patterns import PatternLibrary
from .names import INPUT_FIELDS, input_value

SCL_VERSION = "0.1"


def lreal(value: float) -> str:
    text = f"{value:.4f}"
    return "0.0000" if text == "-0.0000" else text


def literal(value, scl_type: str) -> str:
    if scl_type == "LReal":
        return lreal(float(value))
    if scl_type == "Bool":
        return "TRUE" if value else "FALSE"
    if scl_type == "Byte":
        return f"16#{int(value):02X}"
    if scl_type == "Word":
        return f"16#{int(value):04X}"
    if scl_type.startswith("String") or scl_type == "Char":
        return "'" + str(value).replace("'", "$'") + "'"
    return str(int(value))


def _header(title: str) -> list[str]:
    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    return [
        f"// {title}",
        f"// Erzeugt von palletizer {__version__} am {stamp}",
        "// Import in TIA Portal: Externe Quellen -> Neue externe Datei hinzufügen ->",
        "//                       Rechtsklick -> Bausteine aus Quelle generieren",
        "",
    ]


def _codes_comment() -> list[str]:
    lines = ["// Fehlercodes (Layer.ErrorCode):"]
    for code, text in ERROR_TEXTS.items():
        lines.append(f"//   {code:>3} = {text}")
    lines.append("// Warnbits (Layer.Warnings / Boxes[i].Warnings):")
    for bit, text in WARNING_TEXTS.items():
        lines.append(f"//   Bit {bit.bit_length() - 1} = {text}")
    lines.append("")
    return lines


def _type_block(name: str, title: str, fields: list[tuple[str, str, str]]) -> list[str]:
    lines = [f'TYPE "{name}"', f"TITLE = '{title}'", f"VERSION : {SCL_VERSION}", "   STRUCT"]
    for field_name, scl_type, comment in fields:
        lines.append(f"      {field_name} : {scl_type};   // {comment}")
    lines += ["   END_STRUCT;", "END_TYPE", ""]
    return lines


BOX_TYPE_FIELDS = [
    ("No", "Int", "Ablagereihenfolge, ab 1"),
    ("BlockId", "String[8]", "Block im Muster"),
    ("Col", "Int", "Spalte im Block, ab 1"),
    ("Row", "Int", "Reihe im Block, ab 1"),
    ("X", "LReal", "Kartonmittelpunkt X bezogen auf den Palettennullpunkt [mm]"),
    ("Y", "LReal", "Kartonmittelpunkt Y bezogen auf den Palettennullpunkt [mm]"),
    ("Rot", "Int", "Drehung zum Förderband: 0 oder 90 [°]"),
    ("ApproachAngle", "Int", "Anfahrrichtung 0..315 [°], Karton kommt aus dieser Richtung"),
    ("PreDX", "LReal", "Vorposition relativ zum Ziel X [mm]"),
    ("PreDY", "LReal", "Vorposition relativ zum Ziel Y [mm]"),
    ("PreDZ", "LReal", "Vorposition relativ zum Ziel Z [mm]"),
    ("ExtendPlate", "Bool", "TRUE = Saugplatte ausfahren"),
    ("NeighborMask", "Byte", "Nachbarmaske, Bit k = Zone k*45° belegt (Grundsystem)"),
    ("Warnings", "Word", "Warnbits dieses Kartons"),
]

LAYER_TYPE_FIELDS = [
    ("PatternNo", "Int", "Layerpattern-Nummer"),
    ("ErrorCode", "Int", "0 = OK"),
    ("Warnings", "Word", "Sammelwarnung (ODER aller Warnbits)"),
    ("Variant", "Char", "gewählte Orientierungsvariante 'X' oder 'Y'"),
    ("BoxCount", "Int", "Anzahl Kartons"),
    ("RotatedCount", "Int", "Anzahl Kartons mit Rot = 90"),
    ("StartCorner", "Int", "Startecke der Ablage 1..4 (Grundsystem)"),
    ("LayerSizeX", "LReal", "Lagenmaß X [mm]"),
    ("LayerSizeY", "LReal", "Lagenmaß Y [mm]"),
    ("OverhangX", "LReal", "Überstand je Seite X [mm]"),
    ("OverhangY", "LReal", "Überstand je Seite Y [mm]"),
    ("AreaUsage", "LReal", "Flächennutzung [%]"),
    ("Boxes", f'Array[1..{MAX_BOXES}] of "typPalBox"', f"Kartonliste (MAX_BOXES = {MAX_BOXES})"),
]


def layer_scl(result: LayerResult, db_name: str = "DB_PalLayer") -> str:
    """UDTs und Ergebnis-DB einer berechneten Lage."""
    lines = _header(f"Palettierung: Ergebnis Layerpattern {result.pattern_id or result.inputs.pattern}")
    lines += _codes_comment()
    lines += _type_block("typPalInput", "Palettierung: Eingangsgrößen",
                         [(name, scl_type, comment) for _, name, scl_type, comment in INPUT_FIELDS])
    lines += _type_block("typPalBox", "Palettierung: Ergebnis je Karton", BOX_TYPE_FIELDS)
    lines += _type_block("typPalLayer", "Palettierung: Ergebnis der Lage", LAYER_TYPE_FIELDS)

    lines += [f'DATA_BLOCK "{db_name}"', "{ S7_Optimized_Access := 'TRUE' }",
              f"VERSION : {SCL_VERSION}", "NON_RETAIN", "   VAR",
              '      Input : "typPalInput";', '      Layer : "typPalLayer";', "   END_VAR", "",
              "BEGIN"]
    for field, name, scl_type, _ in INPUT_FIELDS:
        lines.append(f"   Input.{name} := {literal(input_value(result, field), scl_type)};")

    seq = result.sequence
    header_values = {
        "PatternNo": result.pattern_no, "ErrorCode": result.error_code, "Warnings": result.warnings,
        "Variant": result.variant or " ", "BoxCount": result.box_count,
        "RotatedCount": result.rotated_count, "StartCorner": seq.start_corner if seq else 0,
        "LayerSizeX": result.layer_size_x, "LayerSizeY": result.layer_size_y,
        "OverhangX": result.overhang_x, "OverhangY": result.overhang_y, "AreaUsage": result.area_usage,
    }
    for name, scl_type, _ in LAYER_TYPE_FIELDS:
        if name in header_values:
            lines.append(f"   Layer.{name} := {literal(header_values[name], scl_type)};")

    for box in result.boxes:
        values = {
            "No": box.no, "BlockId": box.block_id, "Col": box.col, "Row": box.row,
            "X": box.x, "Y": box.y, "Rot": box.rot, "ApproachAngle": box.approach_angle,
            "PreDX": box.pre_dx, "PreDY": box.pre_dy, "PreDZ": box.pre_dz,
            "ExtendPlate": box.extend_plate, "NeighborMask": box.neighbor_mask,
            "Warnings": box.warnings,
        }
        for name, scl_type, _ in BOX_TYPE_FIELDS:
            lines.append(f"   Layer.Boxes[{box.no}].{name} := {literal(values[name], scl_type)};")
    lines += ["", "END_DATA_BLOCK", ""]
    return "\n".join(lines)


PATTERN_TYPE_FIELDS = [
    ("PatternNo", "Int", "Layerpattern-Nummer"),
    ("Id", "String[8]", "Layerpattern-ID"),
    ("ColsA", "Int", "Block A: Spalten (X)"),
    ("RowsA", "Int", "Block A: Reihen (Y)"),
    ("ColsB", "Int", "Block B: Spalten, 0 = kein Block B"),
    ("RowsB", "Int", "Block B: Reihen"),
    ("DrawnLongSideY", "Bool", "Zeichnung: Langseite von Block A in Y"),
    ("StartCorner", "Int", "Startecke vorgegeben 1..4, 0 = automatisch"),
    ("FillRows", "Bool", "TRUE = reihenweise füllen, FALSE = spaltenweise"),
]


def patterns_scl(library: PatternLibrary, db_name: str = "DB_PalPatterns") -> str:
    """Alle Muster im Standardaufbau als DB (Grundlage für eine SCL-Nachbildung)."""
    lines = _header("Palettierung: Layerpattern-Definitionen")
    patterns = [p for p in library.all() if p.plugin is None]
    skipped = [p for p in library.all() if p.plugin is not None]
    lines.append("// Standardaufbau: Block A links, Block B um 90° gedreht rechts daneben, oben bündig.")
    for pattern in skipped:
        lines.append(f"// Nicht enthalten (Python-Plugin): {pattern.id} {pattern.name}")
    for pattern in patterns:
        if pattern.order is not None:
            lines.append(f"// Hinweis: {pattern.id} hat eine feste Ablagereihenfolge, "
                         "die hier nicht abgebildet ist.")
    if len(patterns) > MAX_PATTERNS:
        raise ValueError(f"Zu viele Muster für MAX_PATTERNS = {MAX_PATTERNS}")
    lines.append("")
    lines += _type_block("typPalPattern", "Palettierung: Layerpattern", PATTERN_TYPE_FIELDS)
    lines += [f'DATA_BLOCK "{db_name}"', "{ S7_Optimized_Access := 'TRUE' }",
              f"VERSION : {SCL_VERSION}", "NON_RETAIN", "   VAR",
              "      Count : Int;   // Anzahl belegter Einträge",
              f'      Patterns : Array[1..{MAX_PATTERNS}] of "typPalPattern";'
              f"   // MAX_PATTERNS = {MAX_PATTERNS}",
              "   END_VAR", "", "BEGIN", f"   Count := {len(patterns)};"]
    for index, pattern in enumerate(patterns, start=1):
        cols_b, rows_b = pattern.block_b if pattern.block_b else (0, 0)
        values = {
            "PatternNo": pattern.number, "Id": pattern.id,
            "ColsA": pattern.block_a[0], "RowsA": pattern.block_a[1],
            "ColsB": cols_b, "RowsB": rows_b,
            "DrawnLongSideY": pattern.drawn_long_side == "y",
            "StartCorner": pattern.start_corner or 0,
            "FillRows": pattern.fill == "rows",
        }
        lines.append(f"   // {pattern.id} {pattern.name}")
        for name, scl_type, _ in PATTERN_TYPE_FIELDS:
            lines.append(f"   Patterns[{index}].{name} := {literal(values[name], scl_type)};")
    lines += ["", "END_DATA_BLOCK", ""]
    return "\n".join(lines)

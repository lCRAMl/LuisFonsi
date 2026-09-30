"""Testvektoren für die SPS: Eingaben, alle Zwischenstufen und Endergebnisse als CSV.

Ein Fall = ein Ordner:
    inputs.csv    Eingangsgrößen (SCL-Namen)
    variants.csv  S2-S4: beide Orientierungsvarianten
    blocks.csv    S2-S4: Blockliste der gewählten Variante (nach dem Zentrieren)
    sequence.csv  S5: Startecke und die Werte, aus denen sie bestimmt wurde
    boxes.csv     S3-S8: je Karton alle Zwischenwerte und die Ausgabe
    layer.csv     Kopfdaten der Lage (Fehlercode, Warnungen, ...)

Format fest: Trennzeichen ";", Dezimalpunkt ".", 4 Nachkommastellen. Keine Zeitstempel,
damit die Dateien bei gleichem Algorithmus identisch bleiben (Vergleich per Git/diff).
"""

from __future__ import annotations

import csv
import tomllib
from pathlib import Path

from ..calculator import calculate
from ..model import Inputs, LayerResult
from ..patterns import PatternLibrary
from .names import INPUT_FIELDS, input_value


def num(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        text = f"{value:.4f}"
        return "0.0000" if text == "-0.0000" else text
    return str(value)


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";", lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow([num(v) for v in row])


def write_testvector(result: LayerResult, folder: Path) -> list[Path]:
    """Schreibt alle Dateien eines Falls in `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    written = []

    path = folder / "inputs.csv"
    _write(path, ["Name", "Value"],
           [[name, input_value(result, field)] for field, name, _, _ in INPUT_FIELDS])
    written.append(path)

    path = folder / "layer.csv"
    seq = result.sequence
    _write(path, ["ErrorCode", "Warnings", "Variant", "BoxCount", "RotatedCount", "StartCorner",
                  "LayerSizeX", "LayerSizeY", "OverhangX", "OverhangY", "AreaUsage",
                  "BoxLong", "BoxShort"],
           [[result.error_code, result.warnings, result.variant, result.box_count,
             result.rotated_count, seq.start_corner if seq else 0, result.layer_size_x,
             result.layer_size_y, result.overhang_x, result.overhang_y, result.area_usage,
             result.box_long, result.box_short]])
    written.append(path)

    if not result.variants:
        return written

    path = folder / "variants.csv"
    rows = []
    for layout in result.variants:
        rows.append([layout.name, layout.valid, layout.error_code, layout.count,
                     layout.layer_size_x, layout.layer_size_y, layout.overhang_x,
                     layout.overhang_y, layout.overhang_sum, layout.rotated_count,
                     layout.name == result.variant])
    _write(path, ["Variant", "Valid", "ErrorCode", "BoxCount", "LayerSizeX", "LayerSizeY",
                  "OverhangX", "OverhangY", "OverhangSum", "RotatedCount", "Chosen"], rows)
    written.append(path)

    layout = result.chosen_layout
    if layout is None:
        return written

    path = folder / "blocks.csv"
    _write(path, ["BlockId", "Cols", "Rows", "Rotated", "SizeX", "SizeY", "Width", "Height",
                  "X0", "Y0"],
           [[b.id, b.cols, b.rows, b.rotated, b.size_x, b.size_y, b.width, b.height, b.x0, b.y0]
            for b in layout.blocks])
    written.append(path)

    if seq is not None:
        path = folder / "sequence.csv"
        _write(path, ["StartCorner", "LooseCount", "LooseCX", "LooseCY", "GapArea", "GapCX",
                      "GapCY", "SourceX", "SourceY"],
               [[seq.start_corner, seq.loose_count, seq.loose_cx, seq.loose_cy, seq.gap_area,
                 seq.gap_cx, seq.gap_cy, seq.source_x, seq.source_y]])
        written.append(path)

    path = folder / "boxes.csv"
    rows = []
    for b in result.boxes:
        a, g = b.approach, b.gripper
        rows.append([b.no, b.block_id, b.col, b.row, b.x_base, b.y_base, b.size_x, b.size_y,
                     b.rot, a.mask, a.free, a.vx, a.vy, a.wx, a.wy, a.used_outward, a.no_free,
                     b.approach_angle_base, g.needed, g.allowed, g.plate_over_neighbor,
                     b.x, b.y, b.approach_angle, b.pre_dx, b.pre_dy, b.pre_dz,
                     b.extend_plate, b.warnings])
    _write(path, ["No", "BlockId", "Col", "Row", "XBase", "YBase", "SizeX", "SizeY", "Rot",
                  "NeighborMask", "FreeMask", "VX", "VY", "WX", "WY", "UsedOutward", "NoFree",
                  "ApproachAngleBase", "ExtendNeeded", "ExtendAllowed", "PlateOverNeighbor",
                  "X", "Y", "ApproachAngle", "PreDX", "PreDY", "PreDZ", "ExtendPlate",
                  "Warnings"], rows)
    written.append(path)
    return written


def load_suite(path: Path) -> list[dict]:
    """Liest die Fallsammlung (TOML mit [[case]]-Einträgen)."""
    with Path(path).open("rb") as handle:
        data = tomllib.load(handle)
    cases = data.get("case", [])
    names = set()
    for case in cases:
        if "name" not in case:
            raise ValueError(f"{path}: Fall ohne 'name'")
        if case["name"] in names:
            raise ValueError(f"{path}: Fall '{case['name']}' doppelt")
        names.add(case["name"])
    return cases


def run_suite(suite_path: Path, out_dir: Path, library: PatternLibrary) -> list[Path]:
    """Berechnet alle Fälle der Sammlung und schreibt die Testvektoren nach `out_dir`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_rows = []
    written = []
    for case in load_suite(suite_path):
        values = {k: v for k, v in case.items() if k not in ("name", "description")}
        result = calculate(Inputs.from_dict(values), library)
        written += write_testvector(result, out_dir / case["name"])
        index_rows.append([case["name"], case.get("description", ""), result.inputs.pattern,
                           result.inputs.box_length_conv, result.inputs.box_width_conv,
                           result.inputs.origin_corner, result.error_code, result.warnings,
                           result.box_count])
    index = out_dir / "index.csv"
    _write(index, ["Case", "Description", "Pattern", "BoxLengthConv", "BoxWidthConv",
                   "OriginCorner", "ErrorCode", "Warnings", "BoxCount"], index_rows)
    written.append(index)
    return written

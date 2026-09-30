"""Kommandozeile.

Beispiele:
    python -m palletizer list
    python -m palletizer calc --pattern EU36 --box 680x260
    python -m palletizer calc --config examples/eu36.toml --origin 3
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from .calculator import calculate
from .constants import ERROR_TEXTS, warning_texts
from .model import Inputs, LayerResult
from .patterns import PatternError, PatternLibrary
from .report import PdfError, build_report, html_to_pdf

CORNER_NAMES = {1: "E1 (unten links)", 2: "E2 (unten rechts)",
                3: "E3 (oben rechts)", 4: "E4 (oben links)"}


def main(argv: list[str] | None = None) -> int:
    if not sys.stdout.isatty():
        # Umgeleitete Ausgabe (Datei, Pipe) immer als UTF-8 schreiben
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        library = PatternLibrary.load(args.patterns)
    except PatternError as exc:
        print(f"Fehler in der Pattern-Bibliothek: {exc}", file=sys.stderr)
        return 2
    if args.command == "list":
        print(format_pattern_list(library))
        return 0
    try:
        inputs = build_inputs(args)
    except (OSError, ValueError, TypeError, tomllib.TOMLDecodeError) as exc:
        print(f"Fehler in den Eingaben: {exc}", file=sys.stderr)
        return 2
    result = calculate(inputs, library)
    print(format_result(result))
    if args.html is not None or args.pdf is not None:
        try:
            write_report(result, args.html, args.pdf)
        except (OSError, PdfError) as exc:
            print(f"Report nicht erzeugt: {exc}", file=sys.stderr)
            return 3
    return 0 if result.ok else 1


def write_report(result: LayerResult, html_path: Path | None, pdf_path: Path | None) -> None:
    """Schreibt den HTML-Report und erzeugt daraus bei Bedarf das PDF."""
    if html_path is None:
        html_path = pdf_path.with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(build_report(result), encoding="utf-8")
    print(f"Report: {html_path}")
    if pdf_path is not None:
        html_to_pdf(html_path, pdf_path)
        print(f"PDF:    {pdf_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="palletizer",
                                     description="Palettieralgorithmus – Berechnung einer Lage")
    parser.add_argument("--patterns", type=Path, default=None,
                        help="Ordner mit den Musterdefinitionen (Standard: patterns/)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Alle Layerpatterns auflisten")

    calc = sub.add_parser("calc", help="Eine Lage berechnen")
    calc.add_argument("--config", type=Path, help="TOML-Datei mit Eingabeparametern")
    calc.add_argument("--pattern", help="Pattern-ID oder -Nummer, z. B. EU36 oder 36")
    calc.add_argument("--box", help="Karton 'in Förderrichtung x quer', z. B. 680x260")
    calc.add_argument("--pallet", help="Palette 'Länge x Breite', z. B. 1200x800")
    calc.add_argument("--origin", type=int, help="Palettennullpunkt 1..4")
    calc.add_argument("--orientation", type=int, help="0 = automatisch, 1 = Variante X, 2 = Variante Y")
    calc.add_argument("--gap", type=float, help="Spaltmaß in mm")
    calc.add_argument("--max-overhang", type=float, help="erlaubter Überstand je Seite in mm")
    calc.add_argument("--approach-dist", type=float, help="Abstand der Vorposition in mm")
    calc.add_argument("--approach-height", type=float, help="Höhe der Vorposition in mm")
    calc.add_argument("--html", type=Path, help="HTML-Report schreiben, z. B. output/eu36.html")
    calc.add_argument("--pdf", type=Path, help="PDF-Report schreiben (über Edge/Chrome), "
                                               "z. B. output/eu36.pdf")
    return parser


def build_inputs(args: argparse.Namespace) -> Inputs:
    """Eingaben zusammensetzen: Standardwerte <- Konfigurationsdatei <- Kommandozeile."""
    values: dict = {}
    if args.config is not None:
        with args.config.open("rb") as handle:
            values.update(tomllib.load(handle))
    if args.pattern is not None:
        values["pattern"] = args.pattern
    if args.box is not None:
        values["box_length_conv"], values["box_width_conv"] = parse_size(args.box)
    if args.pallet is not None:
        values["pallet_length"], values["pallet_width"] = parse_size(args.pallet)
    overrides = {"origin_corner": args.origin, "orientation_mode": args.orientation,
                 "gap": args.gap, "max_overhang": args.max_overhang,
                 "approach_dist": args.approach_dist, "approach_height": args.approach_height}
    for key, value in overrides.items():
        if value is not None:
            values[key] = value
    for key in ("pattern", "box_length_conv", "box_width_conv"):
        if key not in values:
            raise ValueError(f"'{key}' fehlt (per --config oder Kommandozeile angeben)")
    return Inputs.from_dict(values)


def parse_size(text: str) -> tuple[float, float]:
    parts = text.lower().replace("*", "x").split("x")
    if len(parts) != 2:
        raise ValueError(f"Maß '{text}' hat nicht das Format 'A x B'")
    return float(parts[0]), float(parts[1])


def format_pattern_list(library: PatternLibrary) -> str:
    lines = [f"{'Nr':>4}  {'ID':<6} {'Kartons':>7}  Name"]
    for pattern in library.all():
        count = pattern.fixed_count
        count_text = str(count) if count is not None else "Plugin"
        lines.append(f"{pattern.number:>4}  {pattern.id:<6} {count_text:>7}  {pattern.name}")
    return "\n".join(lines)


def format_result(result: LayerResult) -> str:
    inp = result.inputs
    if not result.ok:
        return f"FEHLER {result.error_code}: {ERROR_TEXTS.get(result.error_code, '?')}"

    seq = result.sequence
    lines = [
        f"Pattern {result.pattern_id} (Nr. {result.pattern_no}) \"{result.pattern_name}\"",
        f"Palette {inp.pallet_length:g} x {inp.pallet_width:g} mm, "
        f"Nullpunkt {CORNER_NAMES[inp.origin_corner]}",
        f"Karton {inp.box_length_conv:g} (Förderrichtung) x {inp.box_width_conv:g} (quer) mm",
        "",
    ]
    for layout in result.variants:
        mark = "*" if layout.name == result.variant else " "
        if layout.valid:
            lines.append(f" {mark} Variante {layout.name}: Lage {layout.layer_size_x:.1f} x "
                         f"{layout.layer_size_y:.1f} mm, Überstand {layout.overhang_sum:.1f} mm, "
                         f"{layout.rotated_count} von {layout.count} gedreht")
        else:
            lines.append(f" {mark} Variante {layout.name}: nicht darstellbar")
    lines.append(f"   Gewählt: Variante {result.variant} ({result.variant_reason})")
    lines.append(f"   Überstand je Seite: X {result.overhang_x:.1f} mm, Y {result.overhang_y:.1f} mm; "
                 f"Flächennutzung {result.area_usage:.1f} %")
    lines.append(f"   Startecke {CORNER_NAMES[seq.start_corner]} "
                 f"(X: {seq.source_x}; Y: {seq.source_y})")
    lines.append("")
    lines.append(" Nr  Karton     X [mm]    Y [mm]  Rot  Anfahrt   dX [mm]   dY [mm]  "
                 "dZ  Ausf.  Maske     Warn")
    for box in result.boxes:
        lines.append(f"{box.no:>3}  {box.key:<7} {box.x:>9.1f} {box.y:>9.1f} {box.rot:>4} "
                     f"{box.approach_angle:>7}° {box.pre_dx:>9.1f} {box.pre_dy:>9.1f} "
                     f"{box.pre_dz:>3g} {int(box.extend_plate):>6}  "
                     f"{box.neighbor_mask:08b}  {box.warnings:>4}")
    texts = warning_texts(result.warnings)
    lines.append("")
    lines.append("Warnungen: " + ("; ".join(texts) if texts else "keine"))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())

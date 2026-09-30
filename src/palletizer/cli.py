"""Kommandozeile.

Beispiele:
    python -m palletizer list
    python -m palletizer calc --pattern EU36 --box 680x260
    python -m palletizer calc --config examples/eu36.toml --origin 3
    python -m palletizer calc --pattern EU36 --box 680x260 --export json,csv,scl,pdf
    python -m palletizer testvectors
    python -m palletizer export-patterns
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from .assistant import Suggestion, suggest
from .calculator import calculate
from .constants import ERROR_TEXTS, warning_texts
from .export import ExportOptions, parse_formats, patterns_scl, run_suite, write_exports
from .model import Inputs, LayerResult
from .patterns import PatternError, PatternLibrary
from .report import PdfError, html_to_pdf

CORNER_NAMES = {1: "E1 (unten links)", 2: "E2 (unten rechts)",
                3: "E3 (oben rechts)", 4: "E4 (oben links)"}
PROJECT_DIR = Path(__file__).resolve().parents[2]


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
    if args.command == "export-patterns":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(patterns_scl(library), encoding="utf-8-sig")
        print(f"Geschrieben: {args.out}")
        return 0
    if args.command == "gui":
        return run_gui()
    if args.command == "suggest":
        try:
            base = build_suggest_inputs(args)
        except ValueError as exc:
            print(f"Fehler in den Eingaben: {exc}", file=sys.stderr)
            return 2
        print(format_suggestions(suggest(library, base), args.top))
        return 0
    if args.command == "docs":
        try:
            pdf = html_to_pdf(PROJECT_DIR / "doc" / "formelsammlung.html",
                              args.out / "formelsammlung.pdf")
        except PdfError as exc:
            print(f"PDF nicht erzeugt: {exc}", file=sys.stderr)
            return 3
        print(f"Geschrieben: {pdf}")
        return 0
    if args.command == "testvectors":
        try:
            written = run_suite(args.suite, args.out, library)
        except (OSError, ValueError, TypeError, tomllib.TOMLDecodeError) as exc:
            print(f"Fehler in der Fallsammlung: {exc}", file=sys.stderr)
            return 2
        print(f"{len(written)} Dateien nach {args.out} geschrieben")
        return 0

    try:
        inputs, options = build_inputs(args)
    except (OSError, ValueError, TypeError, tomllib.TOMLDecodeError) as exc:
        print(f"Fehler in den Eingaben: {exc}", file=sys.stderr)
        return 2
    result = calculate(inputs, library)
    print(format_result(result))
    try:
        written = write_exports(result, options, library)
    except (OSError, PdfError) as exc:
        print(f"Export fehlgeschlagen: {exc}", file=sys.stderr)
        return 3
    if written:
        print("\nExport:")
        for path in written:
            print(f"  {path}")
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="palletizer",
                                     description="Palettieralgorithmus – Berechnung einer Lage")
    parser.add_argument("--patterns", type=Path, default=None,
                        help="Ordner mit den Musterdefinitionen (Standard: patterns/)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Alle Layerpatterns auflisten")

    calc = sub.add_parser("calc", help="Eine Lage berechnen")
    calc.add_argument("--config", type=Path, help="TOML-Datei mit Eingabeparametern und [export]")
    calc.add_argument("--pattern", help="Pattern-ID oder -Nummer, z. B. EU36 oder 36")
    calc.add_argument("--box", help="Karton 'in Förderrichtung x quer', z. B. 680x260")
    calc.add_argument("--pallet", help="Palette 'Länge x Breite', z. B. 1200x800")
    calc.add_argument("--origin", type=int, help="Palettennullpunkt 1..4")
    calc.add_argument("--orientation", type=int, help="0 = automatisch, 1 = Variante X, 2 = Variante Y")
    calc.add_argument("--gap", type=float, help="Spaltmaß in mm")
    calc.add_argument("--max-overhang", type=float, help="erlaubter Überstand je Seite in mm")
    calc.add_argument("--approach-dist", type=float, help="Abstand der Vorposition in mm")
    calc.add_argument("--approach-height", type=float, help="Höhe der Vorposition in mm")
    calc.add_argument("--export", help="Exportformate, z. B. json,csv,scl,scl_patterns,testvector,"
                                       "html,pdf oder all / none (ersetzt die Auswahl aus --config)")
    calc.add_argument("--out", type=Path, help="Zielordner der Exporte (Standard: output)")
    calc.add_argument("--name", help="Dateiname der Exporte ohne Endung (Standard: automatisch)")

    vectors = sub.add_parser("testvectors", help="Testvektoren für die SPS erzeugen")
    vectors.add_argument("--suite", type=Path, default=PROJECT_DIR / "examples" / "testvectors.toml",
                         help="Fallsammlung (Standard: examples/testvectors.toml)")
    vectors.add_argument("--out", type=Path, default=PROJECT_DIR / "examples" / "testvectors",
                         help="Zielordner (Standard: examples/testvectors)")

    sug = sub.add_parser("suggest", help="Musterassistent: passende Layerpatterns vorschlagen")
    sug.add_argument("--box", required=True, help="Karton 'in Förderrichtung x quer', z. B. 680x260")
    sug.add_argument("--pallet", default="1200x800", help="Palette 'Länge x Breite'")
    sug.add_argument("--gap", type=float, default=0.0, help="Spaltmaß in mm")
    sug.add_argument("--max-overhang", type=float, default=0.0, help="erlaubter Überstand je Seite")
    sug.add_argument("--top", type=int, default=0, help="nur die besten N anzeigen (0 = alle)")

    sub.add_parser("gui", help="Bedienoberfläche im Browser starten (Streamlit)")

    docs = sub.add_parser("docs", help="Formelsammlung als PDF erzeugen")
    docs.add_argument("--out", type=Path, default=Path("output"),
                      help="Zielordner (Standard: output)")

    pats = sub.add_parser("export-patterns", help="Musterdefinitionen als SCL-DB exportieren")
    pats.add_argument("--out", type=Path, default=Path("output") / "DB_PalPatterns.scl",
                      help="Zieldatei (Standard: output/DB_PalPatterns.scl)")
    return parser


def build_inputs(args: argparse.Namespace) -> tuple[Inputs, ExportOptions]:
    """Eingaben zusammensetzen: Standardwerte <- Konfigurationsdatei <- Kommandozeile."""
    values: dict = {}
    export_values: dict = {}
    if args.config is not None:
        with args.config.open("rb") as handle:
            values.update(tomllib.load(handle))
        export_values = values.pop("export", {})
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

    options = ExportOptions.from_dict(export_values)
    if args.export is not None:
        options.formats = parse_formats(args.export)
    if args.out is not None:
        options.out_dir = args.out
    if args.name is not None:
        options.name = args.name
    return Inputs.from_dict(values), options


def build_suggest_inputs(args: argparse.Namespace) -> Inputs:
    conv, cross = parse_size(args.box)
    length, width = parse_size(args.pallet)
    return Inputs(box_length_conv=conv, box_width_conv=cross, pattern="", pallet_length=length,
                  pallet_width=width, gap=args.gap, max_overhang=args.max_overhang)


def format_suggestions(suggestions: list[Suggestion], top: int = 0) -> str:
    if top > 0:
        suggestions = suggestions[:top]
    lines = [f"{'Rang':>4}  {'Muster':<6} {'Name':<18} {'Kartons':>7}  {'passt':<5} "
             f"{'Var.':<4} {'Überstand X/Y':>14}  {'Fläche':>7}  {'gedreht':>7}"]
    for rank, s in enumerate(suggestions, start=1):
        r = s.result
        lines.append(f"{rank:>4}  {s.pattern_id:<6} {s.name[:18]:<18} {r.box_count:>7}  "
                     f"{'ja' if s.fits else 'nein':<5} {r.variant:<4} "
                     f"{r.overhang_x:>6.1f} / {r.overhang_y:<6.1f} {r.area_usage:>6.1f} %  "
                     f"{r.rotated_count:>7}")
    return "\n".join(lines)


def run_gui() -> int:
    """Startet die Streamlit-Oberfläche."""
    import importlib.util
    import subprocess
    if importlib.util.find_spec("streamlit") is None:
        print("Streamlit ist nicht installiert: pip install -e .[gui]", file=sys.stderr)
        return 2
    app = Path(__file__).resolve().parent / "app.py"
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)])


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

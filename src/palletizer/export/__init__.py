"""Exporte einer berechneten Lage. Welche Formate erzeugt werden, ist einstellbar.

Formate:
    json          vollständiges Ergebnis inkl. Zwischenergebnissen
    csv           Kartonliste (Trenn-/Dezimalzeichen einstellbar)
    scl           UDTs + Ergebnis-DB für TIA Portal
    scl_patterns  DB mit allen Musterdefinitionen für TIA Portal
    testvector    Ordner mit allen Zwischenstufen als CSV (Vergleich mit der SCL-Umsetzung)
    html          Report
    pdf           Report als PDF (über Edge/Chrome)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..model import LayerResult
from ..patterns import PatternLibrary
from ..report import build_report, html_to_pdf
from .csv_export import boxes_csv
from .json_export import to_json
from .scl_export import layer_scl, patterns_scl
from .testvectors import run_suite, write_testvector

FORMATS = ("json", "csv", "scl", "scl_patterns", "testvector", "html", "pdf")


@dataclass
class ExportOptions:
    """Einstellungen der Exporte (Abschnitt [export] der Konfigurationsdatei)."""
    formats: set[str] = field(default_factory=set)
    out_dir: Path = Path("output")
    name: str = ""                 # Dateiname ohne Endung; leer = automatisch
    csv_delimiter: str = ";"
    csv_decimal: str = ","

    @classmethod
    def from_dict(cls, data: dict) -> "ExportOptions":
        options = cls()
        known = set(FORMATS) | {"dir", "name", "csv_delimiter", "csv_decimal"}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"Unbekannte Export-Einstellungen: {', '.join(unknown)}")
        for fmt in FORMATS:
            if data.get(fmt, False):
                options.formats.add(fmt)
        if "dir" in data:
            options.out_dir = Path(data["dir"])
        options.name = str(data.get("name", ""))
        options.csv_delimiter = str(data.get("csv_delimiter", options.csv_delimiter))
        options.csv_decimal = str(data.get("csv_decimal", options.csv_decimal))
        return options


def parse_formats(text: str) -> set[str]:
    """"json,csv" -> {"json", "csv"}; "all" = alle, "none" = keine."""
    text = text.strip().lower()
    if text == "none":
        return set()
    if text == "all":
        return set(FORMATS)
    formats = {part.strip() for part in text.split(",") if part.strip()}
    unknown = sorted(formats - set(FORMATS))
    if unknown:
        raise ValueError(f"Unbekannte Exportformate: {', '.join(unknown)} "
                         f"(möglich: {', '.join(FORMATS)}, all, none)")
    return formats


def default_name(result: LayerResult) -> str:
    inp = result.inputs
    pattern = result.pattern_id or str(inp.pattern)
    return f"{pattern}_{inp.box_length_conv:g}x{inp.box_width_conv:g}_E{inp.origin_corner}"


def write_exports(result: LayerResult, options: ExportOptions,
                  library: PatternLibrary) -> list[Path]:
    """Erzeugt alle eingeschalteten Exporte. Rückgabe: geschriebene Dateien."""
    if not options.formats:
        return []
    out_dir = Path(options.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / (options.name or default_name(result))
    written: list[Path] = []

    if "json" in options.formats:
        path = base.with_suffix(".json")
        path.write_text(to_json(result), encoding="utf-8")
        written.append(path)
    if "csv" in options.formats:
        path = base.with_suffix(".csv")
        # Mit BOM, damit Excel die Datei als UTF-8 erkennt
        path.write_text(boxes_csv(result, options.csv_delimiter, options.csv_decimal),
                        encoding="utf-8-sig")
        written.append(path)
    if "scl" in options.formats:
        path = base.with_suffix(".scl")
        path.write_text(layer_scl(result), encoding="utf-8-sig")
        written.append(path)
    if "scl_patterns" in options.formats:
        path = out_dir / "DB_PalPatterns.scl"
        path.write_text(patterns_scl(library), encoding="utf-8-sig")
        written.append(path)
    if "testvector" in options.formats:
        written += write_testvector(result, out_dir / f"{base.name}_testvector")
    if "html" in options.formats or "pdf" in options.formats:
        html_path = base.with_suffix(".html")
        html_path.write_text(build_report(result), encoding="utf-8")
        if "html" in options.formats:
            written.append(html_path)
        if "pdf" in options.formats:
            try:
                written.append(html_to_pdf(html_path, base.with_suffix(".pdf")))
            finally:
                if "html" not in options.formats:
                    html_path.unlink(missing_ok=True)
    return written


__all__ = ["FORMATS", "ExportOptions", "parse_formats", "write_exports", "write_testvector",
           "run_suite", "patterns_scl", "layer_scl", "boxes_csv", "to_json"]

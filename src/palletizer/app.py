"""Bedienoberfläche im Browser (Streamlit).

Start:  palletizer gui     oder     streamlit run src/palletizer/app.py

Links: alle Eingaben. Rechts: Kennzahlen, Report mit Lagenbild (Schritt für Schritt),
Kartonliste, Musterassistent und Exporte (Download oder in einen Ordner speichern).
"""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path

try:
    import palletizer  # noqa: F401
except ImportError:  # Start per "streamlit run": src/ in den Suchpfad aufnehmen
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from palletizer.assistant import suggest
from palletizer.calculator import calculate
from palletizer.constants import ERROR_TEXTS, warning_texts
from palletizer.export import (FORMATS, ExportOptions, boxes_csv, layer_scl, patterns_scl, to_json,
                               write_exports, write_testvector)
from palletizer.model import Inputs, LayerResult
from palletizer.patterns import PatternLibrary
from palletizer.report import PdfError, build_report, find_browser, html_to_pdf

PALLETS = {
    "EU-Palette 1200 × 800": (1200.0, 800.0),
    "Industriepalette 1200 × 1000": (1200.0, 1000.0),
    "frei": None,
}
CORNERS = {1: "E1 unten links", 2: "E2 unten rechts", 3: "E3 oben rechts", 4: "E4 oben links"}
ORIENTATIONS = {0: "automatisch", 1: "Variante X (Langseite A in X)", 2: "Variante Y (Langseite A in Y)"}
FORMAT_LABELS = {
    "json": "JSON (vollständig)", "csv": "CSV (Kartonliste)", "scl": "SCL: DB_PalLayer",
    "scl_patterns": "SCL: DB_PalPatterns", "testvector": "Testvektoren (ZIP)",
    "html": "Report HTML", "pdf": "Report PDF",
}


@st.cache_resource
def load_library() -> PatternLibrary:
    return PatternLibrary.load()


def sidebar_inputs(library: PatternLibrary) -> Inputs:
    sb = st.sidebar
    sb.header("Karton")
    col1, col2 = sb.columns(2)
    conv = col1.number_input("in Förderrichtung [mm]", min_value=1.0, value=680.0, step=5.0)
    cross = col2.number_input("quer [mm]", min_value=1.0, value=260.0, step=5.0)

    sb.header("Muster")
    patterns = library.all()
    ids = [p.id for p in patterns]
    if "pattern" not in st.session_state:
        st.session_state["pattern"] = "EU36" if "EU36" in ids else ids[0]
    names = {p.id: p for p in patterns}
    sb.selectbox("Layerpattern", ids, key="pattern",
                 format_func=lambda pid: f"{pid} · {names[pid].name}")
    orientation = sb.selectbox("Orientierung", list(ORIENTATIONS), format_func=ORIENTATIONS.get)

    sb.header("Palette")
    preset = sb.selectbox("Palettentyp", list(PALLETS))
    if PALLETS[preset] is None:
        col1, col2 = sb.columns(2)
        length = col1.number_input("Länge X [mm]", min_value=1.0, value=1200.0, step=10.0)
        width = col2.number_input("Breite Y [mm]", min_value=1.0, value=800.0, step=10.0)
    else:
        length, width = PALLETS[preset]
    corner = sb.selectbox("Palettennullpunkt", list(CORNERS), format_func=CORNERS.get)
    col1, col2 = sb.columns(2)
    gap = col1.number_input("Spaltmaß [mm]", min_value=0.0, value=0.0, step=1.0)
    overhang = col2.number_input("Überstand erlaubt je Seite [mm]", min_value=0.0, value=0.0, step=5.0)

    with sb.expander("Saugplatte"):
        col1, col2 = st.columns(2)
        plate_conv = col1.number_input("Grundplatte in Förderr.", min_value=1.0, value=600.0, step=10.0)
        plate_cross = col2.number_input("Grundplatte quer", min_value=1.0, value=400.0, step=10.0)
        ext_conv = col1.number_input("ausgefahren in Förderr.", min_value=1.0, value=600.0, step=10.0)
        ext_cross = col2.number_input("ausgefahren quer", min_value=1.0, value=1400.0, step=10.0)
    with sb.expander("Vorposition und Toleranz"):
        approach_dist = st.number_input("Abstand X/Y [mm]", min_value=0.1, value=30.0, step=5.0)
        approach_height = st.number_input("Höhe Z [mm]", min_value=0.0, value=20.0, step=5.0)
        tolerance = st.number_input("Toleranz ε [mm]", min_value=0.001, value=0.1, step=0.05, format="%.3f")

    return Inputs(box_length_conv=conv, box_width_conv=cross, pattern=st.session_state["pattern"],
                  pallet_length=length, pallet_width=width, origin_corner=corner,
                  orientation_mode=orientation, gap=gap, max_overhang=overhang,
                  plate_conv=plate_conv, plate_cross=plate_cross, plate_ext_conv=ext_conv,
                  plate_ext_cross=ext_cross, approach_dist=approach_dist,
                  approach_height=approach_height, tolerance=tolerance)


def show_summary(result: LayerResult) -> None:
    cols = st.columns(6)
    cols[0].metric("Kartons", result.box_count)
    cols[1].metric("davon gedreht", result.rotated_count)
    cols[2].metric("Variante", result.variant)
    cols[3].metric("Überstand je Seite X / Y", f"{result.overhang_x:.1f} / {result.overhang_y:.1f}")
    cols[4].metric("Flächennutzung", f"{result.area_usage:.1f} %")
    cols[5].metric("Warnungen", len(warning_texts(result.warnings)))
    for text in warning_texts(result.warnings):
        st.warning(text, icon="⚠️")


def tab_boxes(result: LayerResult) -> None:
    rows = [{
        "Nr": b.no, "Karton": b.key, "X": round(b.x, 1), "Y": round(b.y, 1), "Rot": b.rot,
        "Anfahrt °": b.approach_angle, "dX": round(b.pre_dx, 1), "dY": round(b.pre_dy, 1),
        "dZ": round(b.pre_dz, 1), "Ausfahren": int(b.extend_plate), "Maske": f"{b.neighbor_mask:08b}",
        "Warnungen": "; ".join(warning_texts(b.warnings)),
    } for b in result.boxes]
    st.dataframe(rows, hide_index=True, width="stretch")


def take_pattern(pattern_id: str) -> None:
    """Callback: Muster aus dem Assistenten in die Auswahl links übernehmen."""
    st.session_state["pattern"] = pattern_id


def tab_assistant(library: PatternLibrary, inputs: Inputs) -> None:
    st.caption("Alle Muster mit dem aktuellen Karton berechnet. Rangfolge: passt ohne Überstand, "
               "mehr Kartons, höhere Flächennutzung, weniger Drehungen.")
    suggestions = suggest(library, replace(inputs, orientation_mode=0))
    rows = [{
        "Rang": rank, "Muster": s.pattern_id, "Name": s.name, "Kartons": s.box_count,
        "passt": "ja" if s.fits else "nein", "Variante": s.result.variant,
        "Überstand X": round(s.result.overhang_x, 1), "Überstand Y": round(s.result.overhang_y, 1),
        "Fläche %": round(s.result.area_usage, 1), "gedreht": s.result.rotated_count,
    } for rank, s in enumerate(suggestions, start=1)]
    st.dataframe(rows, hide_index=True, width="stretch")
    fitting = [s.pattern_id for s in suggestions if s.fits]
    if fitting:
        col1, col2 = st.columns([3, 1])
        choice = col1.selectbox("Muster übernehmen", fitting, key="assistant_choice")
        col2.write("")
        col2.button("Übernehmen", width="stretch", on_click=take_pattern, args=(choice,))
    else:
        st.info("Kein Muster passt ohne Überstand.")


def export_file(result: LayerResult, library: PatternLibrary, fmt: str,
                options: ExportOptions) -> tuple[str, bytes, str]:
    """Inhalt eines Exports für den Download: (Dateiname, Daten, MIME-Typ)."""
    name = options.name or (f"{result.pattern_id}_{result.inputs.box_length_conv:g}x"
                            f"{result.inputs.box_width_conv:g}_E{result.inputs.origin_corner}")
    if fmt == "json":
        return f"{name}.json", to_json(result).encode("utf-8"), "application/json"
    if fmt == "csv":
        text = boxes_csv(result, options.csv_delimiter, options.csv_decimal)
        return f"{name}.csv", text.encode("utf-8-sig"), "text/csv"
    if fmt == "scl":
        return f"{name}.scl", layer_scl(result).encode("utf-8-sig"), "text/plain"
    if fmt == "scl_patterns":
        return "DB_PalPatterns.scl", patterns_scl(library).encode("utf-8-sig"), "text/plain"
    if fmt == "html":
        return f"{name}.html", build_report(result).encode("utf-8"), "text/html"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if fmt == "testvector":
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in write_testvector(result, tmp_path / name):
                    archive.write(path, f"{name}/{path.name}")
            return f"{name}_testvector.zip", buffer.getvalue(), "application/zip"
        if fmt == "pdf":
            return f"{name}.pdf", cached_pdf(repr(result.inputs), result), "application/pdf"
    raise ValueError(fmt)


@st.cache_data(show_spinner="PDF wird erzeugt …", max_entries=20)
def cached_pdf(inputs_key: str, _result: LayerResult) -> bytes:
    """PDF nur einmal je Eingabestand erzeugen (der Browser-Druck dauert einige Sekunden)."""
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "report.html"
        html_path.write_text(build_report(_result), encoding="utf-8")
        return html_to_pdf(html_path, Path(tmp) / "report.pdf").read_bytes()


def tab_export(result: LayerResult, library: PatternLibrary) -> None:
    st.caption("Auswählen, welche Exporte erzeugt werden – dann einzeln herunterladen "
               "oder alle zusammen in einen Ordner speichern.")
    available = [f for f in FORMATS if f != "pdf" or find_browser() is not None]
    selected = st.multiselect("Exporte", available, default=["json", "csv", "scl"],
                              format_func=FORMAT_LABELS.get)
    col1, col2, col3 = st.columns(3)
    delimiter = col1.selectbox("CSV-Trennzeichen", [";", ","], index=0)
    decimal = col2.selectbox("CSV-Dezimalzeichen", [",", "."], index=0)
    name = col3.text_input("Dateiname (leer = automatisch)", value="")
    options = ExportOptions(formats=set(selected), csv_delimiter=delimiter, csv_decimal=decimal,
                            name=name.strip())

    if selected:
        st.subheader("Herunterladen")
        cols = st.columns(min(len(selected), 4))
        for index, fmt in enumerate(selected):
            try:
                file_name, data, mime = export_file(result, library, fmt, options)
            except PdfError as exc:
                cols[index % len(cols)].error(f"PDF: {exc}")
                continue
            cols[index % len(cols)].download_button(FORMAT_LABELS[fmt], data, file_name=file_name,
                                                    mime=mime, width="stretch", key=f"dl_{fmt}")

        st.subheader("In Ordner speichern")
        col1, col2 = st.columns([3, 1])
        folder = col1.text_input("Zielordner", value="output")
        col2.write("")
        if col2.button("Speichern", width="stretch"):
            options.out_dir = Path(folder)
            try:
                written = write_exports(result, options, library)
            except (OSError, PdfError) as exc:
                st.error(f"Export fehlgeschlagen: {exc}")
            else:
                st.success("Geschrieben:\n\n" + "\n".join(f"- `{p}`" for p in written))


def main() -> None:
    st.set_page_config(page_title="Palettierung", page_icon="📦", layout="wide")
    library = load_library()
    inputs = sidebar_inputs(library)
    result = calculate(inputs, library)

    st.title(f"Palettierung {result.pattern_id or inputs.pattern}"
             + (f" · {result.pattern_name}" if result.pattern_name else ""))
    if not result.ok:
        st.error(f"Fehler {result.error_code}: {ERROR_TEXTS.get(result.error_code, '?')}")
        return
    show_summary(result)

    report, boxes, assistant, export = st.tabs(
        ["Lagenbild & Rechenweg", "Kartonliste", "Musterassistent", "Export"])
    with report:
        st.iframe(build_report(result, header=False), height=1500)
    with boxes:
        tab_boxes(result)
    with assistant:
        tab_assistant(library, inputs)
    with export:
        tab_export(result, library)


main()

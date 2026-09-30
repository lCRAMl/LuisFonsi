"""Gemeinsame Bezeichner für alle Exporte (SCL, CSV, Testvektoren).

Die Namen in Spalte 2 sind die Bezeichner in der SPS (UDT-Felder).
"""

# (Python-Feld, SCL-Name, SCL-Typ, Kommentar)
INPUT_FIELDS = [
    ("box_length_conv", "BoxLengthConv", "LReal", "Kartonmaß in Förderrichtung [mm]"),
    ("box_width_conv", "BoxWidthConv", "LReal", "Kartonmaß quer zur Förderrichtung [mm]"),
    ("pattern", "PatternNo", "Int", "Layerpattern-Nummer (EU36 = 36)"),
    ("pallet_length", "PalletLength", "LReal", "Palettenmaß in X [mm]"),
    ("pallet_width", "PalletWidth", "LReal", "Palettenmaß in Y [mm]"),
    ("origin_corner", "OriginCorner", "Int", "Palettennullpunkt 1..4"),
    ("orientation_mode", "OrientationMode", "Int", "0 = automatisch, 1 = Variante X, 2 = Variante Y"),
    ("gap", "Gap", "LReal", "Spaltmaß [mm]"),
    ("max_overhang", "MaxOverhang", "LReal", "erlaubter Überstand je Seite [mm]"),
    ("plate_conv", "PlateConv", "LReal", "Saugplatte in Förderrichtung [mm]"),
    ("plate_cross", "PlateCross", "LReal", "Saugplatte quer [mm]"),
    ("plate_ext_conv", "PlateExtConv", "LReal", "ausgefahrene Saugplatte in Förderrichtung [mm]"),
    ("plate_ext_cross", "PlateExtCross", "LReal", "ausgefahrene Saugplatte quer [mm]"),
    ("approach_dist", "ApproachDist", "LReal", "Vorposition Abstand X/Y [mm]"),
    ("approach_height", "ApproachHeight", "LReal", "Vorposition Höhe Z [mm]"),
    ("tolerance", "Tolerance", "LReal", "Toleranz für Vergleiche [mm]"),
]

# Spalten der Kartonliste (CSV und SCL)
BOX_COLUMNS = ["No", "BlockId", "Col", "Row", "X", "Y", "Rot", "ApproachAngle",
               "PreDX", "PreDY", "PreDZ", "ExtendPlate", "NeighborMask", "Warnings"]


def input_value(result, field: str):
    """Eingabewert für den Export; die Pattern-ID wird als Nummer ausgegeben."""
    if field == "pattern":
        return result.pattern_no
    return getattr(result.inputs, field)


def box_row(box) -> list:
    """Werte einer Zeile der Kartonliste in der Reihenfolge von BOX_COLUMNS."""
    return [box.no, box.block_id, box.col, box.row, box.x, box.y, box.rot, box.approach_angle,
            box.pre_dx, box.pre_dy, box.pre_dz, box.extend_plate, box.neighbor_mask, box.warnings]

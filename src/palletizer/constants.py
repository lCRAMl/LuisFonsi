"""Konstanten: Array-Grenzen, Fehlercodes, Warnbits und Richtungstabellen.

Alle Werte sind so gewählt, dass sie 1:1 als Konstanten in der SPS (SCL)
angelegt werden können.
"""

# --- Array-Grenzen ---------------------------------------------------------
MAX_BOXES = 100   # maximale Anzahl Kartons pro Lage
MAX_BLOCKS = 8    # maximale Anzahl Blöcke pro Muster
MAX_PATTERNS = 50  # maximale Anzahl Muster im Pattern-DB der SPS

# --- Fehlercodes (INT, 0 = OK) --------------------------------------------
# 1xx: ungültige Eingaben, 2xx: Muster nicht berechenbar
ERR_OK = 0
ERR_PALLET_SIZE = 101
ERR_BOX_SIZE = 102
ERR_PATTERN_UNKNOWN = 103
ERR_ORIGIN_CORNER = 104
ERR_ORIENTATION_MODE = 105
ERR_GAP = 106
ERR_APPROACH = 107
ERR_PLATE = 108
ERR_TOLERANCE = 109
ERR_TOO_MANY_BOXES = 201
ERR_TOO_MANY_BLOCKS = 202
ERR_PATTERN_OVERLAP = 203
ERR_NO_VALID_VARIANT = 204
ERR_SEQUENCE_OVERRIDE = 205

ERROR_TEXTS = {
    ERR_OK: "OK",
    ERR_PALLET_SIZE: "Palettenmaß ungültig (muss > 0 sein)",
    ERR_BOX_SIZE: "Kartonmaß ungültig (muss > 0 sein)",
    ERR_PATTERN_UNKNOWN: "Layerpattern unbekannt",
    ERR_ORIGIN_CORNER: "Palettennullpunkt ungültig (erlaubt: 1..4)",
    ERR_ORIENTATION_MODE: "Orientierungsmodus ungültig (erlaubt: 0, 1, 2)",
    ERR_GAP: "Spaltmaß oder erlaubter Überstand ungültig (muss >= 0 sein)",
    ERR_APPROACH: "Vorposition ungültig (Abstand > 0, Höhe >= 0)",
    ERR_PLATE: "Saugplatte ungültig (Maße > 0, ausgefahren >= Grundplatte)",
    ERR_TOLERANCE: "Toleranz ungültig (muss > 0 sein)",
    ERR_TOO_MANY_BOXES: "Zu viele Kartons für die Array-Grenze MAX_BOXES",
    ERR_TOO_MANY_BLOCKS: "Zu viele Blöcke für die Array-Grenze MAX_BLOCKS",
    ERR_PATTERN_OVERLAP: "Musterdefinition fehlerhaft: Kartons überlappen sich",
    ERR_NO_VALID_VARIANT: "Muster mit diesem Karton in keiner Orientierung darstellbar",
    ERR_SEQUENCE_OVERRIDE: "Vorgegebene Ablagereihenfolge im Pattern passt nicht zu den Kartons",
}

# --- Warnbits (WORD) --------------------------------------------------------
WARN_OVERHANG = 1 << 0                # Überstand größer als erlaubt
WARN_BOX_LARGER_THAN_PALLET = 1 << 1  # Einzelkarton größer als die Palette
WARN_NO_FREE_APPROACH = 1 << 2        # keine kollisionsfreie Anfahrrichtung gefunden
WARN_EXTEND_BLOCKED = 1 << 3          # Ausfahren nötig, aber durch Nachbarn blockiert
WARN_SHORT_SIDE_LEADING = 1 << 4      # Hinweis: Karton kommt mit der Kurzseite voran

WARNING_TEXTS = {
    WARN_OVERHANG: "Überstand größer als erlaubt",
    WARN_BOX_LARGER_THAN_PALLET: "Karton größer als die Palette",
    WARN_NO_FREE_APPROACH: "Keine freie Anfahrrichtung",
    WARN_EXTEND_BLOCKED: "Saugplatte müsste ausfahren, Nachbarn blockieren",
    WARN_SHORT_SIDE_LEADING: "Hinweis: Karton kommt mit der Kurzseite voran",
}


def warning_texts(bits: int) -> list[str]:
    """Liefert die Klartexte aller gesetzten Warnbits."""
    texts = []
    for bit, text in WARNING_TEXTS.items():
        if bits & bit:
            texts.append(text)
    return texts


# --- Richtungen (Index k = 0..7, Winkel = k * 45°) -------------------------
# 0° = +X, positiv gegen den Uhrzeigersinn (von oben gesehen).
DIAG = 0.7071067811865476  # cos(45°) = sin(45°)
DIR_ANGLE = (0, 45, 90, 135, 180, 225, 270, 315)
DIR_X = (1.0, DIAG, 0.0, -DIAG, -1.0, -DIAG, 0.0, DIAG)
DIR_Y = (0.0, DIAG, 1.0, DIAG, 0.0, -DIAG, -1.0, -DIAG)

# Feste Rangfolge bei vollständigem Gleichstand: erst Diagonalen, dann Achsen.
APPROACH_PRIORITY = (1, 3, 5, 7, 0, 2, 4, 6)

# Toleranz für Vergleiche von Skalarprodukten (einheitenlos)
DOT_EPS = 1e-6

"""CSV-Export der Kartonliste (eine Zeile je Karton, Spaltennamen wie in der SPS).

Trennzeichen und Dezimalzeichen sind einstellbar; Standard ";" und "," für deutsches Excel.
"""

from __future__ import annotations

import csv
import io

from ..model import LayerResult
from .names import BOX_COLUMNS, box_row


def format_value(value, decimal: str = ".", digits: int = 4) -> str:
    """Zahl ohne überflüssige Nullen, Bool als 0/1."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
        if text in ("-0", ""):
            text = "0"
        return text.replace(".", decimal)
    return str(value)


def boxes_csv(result: LayerResult, delimiter: str = ";", decimal: str = ",") -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(BOX_COLUMNS)
    for box in result.boxes:
        writer.writerow([format_value(v, decimal) for v in box_row(box)])
    return buffer.getvalue()

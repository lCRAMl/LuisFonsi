"""JSON-Export: vollständiges Ergebnis inkl. aller Zwischenergebnisse (verlustfrei)."""

from __future__ import annotations

import json
from dataclasses import asdict

from .. import __version__
from ..constants import ERROR_TEXTS, warning_texts
from ..model import LayerResult


def result_to_dict(result: LayerResult) -> dict:
    data = {
        "format": "palletizer-layer",
        "generator": f"palletizer {__version__}",
        "error_text": ERROR_TEXTS.get(result.error_code, "?"),
        "warning_texts": warning_texts(result.warnings),
    }
    data.update(asdict(result))
    for box, box_data in zip(result.boxes, data["boxes"]):
        box_data["key"] = box.key
        box_data["warning_texts"] = warning_texts(box.warnings)
    return data


def to_json(result: LayerResult) -> str:
    return json.dumps(result_to_dict(result), ensure_ascii=False, indent=2)

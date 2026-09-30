# Palettierer

Berechnet für einen Portalroboter die Ablagepositionen von Kartons auf einer Palette
nach vorgegebenen Layerpatterns – und dient gleichzeitig als nachvollziehbare
Vorlage für die Umsetzung in der SPS (SCL, S7-1500).

Pro Karton werden berechnet:

- X/Y des Kartonmittelpunkts bezogen auf den gewählten Palettennullpunkt
- Drehung 0°/90° bezogen auf die Lage auf dem Förderband
- Annäherungsrichtung in 45°-Schritten und Versatz der Vorposition
- Saugplatte ausfahren ja/nein
- Nachbarmaske und Warnbits zur Kontrolle

## Schnellstart

Voraussetzung: Python 3.11 oder neuer. Der Rechenkern braucht keine weiteren Pakete.

```powershell
pip install -e .[dev]          # einmalig (installiert auch pytest)

palletizer list                                       # alle Muster
palletizer calc --pattern EU36 --box 680x260           # Karton: Förderrichtung x quer
palletizer calc --config examples/eu36.toml --origin 3
palletizer calc --pattern EU36 --box 680x260 --html output/eu36.html --pdf output/eu36.pdf
pytest                                                 # Tests
```

Der HTML-Report enthält das Lagenbild mit Schritt-für-Schritt-Steuerung (Karton anklicken,
Pfeiltasten, Esc = Gesamtansicht), die Ausgabetabelle für die SPS, den Variantenvergleich,
kleine Bilder jedes Ablageschritts und den kompletten Rechenweg mit eingesetzten Zahlen.
Das PDF wird über Microsoft Edge bzw. Google Chrome im Hintergrund gedruckt.

Ohne Installation: `$env:PYTHONPATH="src"; python -m palletizer list`

## Aufbau

| Ordner | Inhalt |
|---|---|
| `src/palletizer/` | Rechenkern, eine Datei je Berechnungsstufe (S0–S8) |
| `patterns/` | Layerpattern-Definitionen (TOML), Format siehe `patterns/README.md` |
| `config/` | Standardparameter als Vorlage |
| `examples/` | Beispielaufträge |
| `tests/` | Tests (pytest) |
| `doc/` | Dokumentation (Planung, Formeln, SPS-Leitfaden) |
| `reference/` | Referenzmaterial (PDF der Layerpatterns) |
| `output/` | erzeugte Ergebnisse (nicht in Git) |

## Berechnungsstufen

| Stufe | Modul | Aufgabe |
|---|---|---|
| S0 | `validate.py` | Eingaben prüfen, Fehlercode |
| S1 | `calculator.py` | Lang-/Kurzseite bestimmen |
| S2–S4 | `layout.py` | Blockliste, Kartonpositionen, Zentrieren, Wahl der Orientierung |
| S5 | `sequence.py` | Ablagereihenfolge (dichter Teil zuerst) |
| S6 | `approach.py` | Annäherungsrichtung (Nachbarzonen) |
| S7 | `gripper.py` | Saugplatte ausfahren |
| S8 | `transform.py` | Umrechnung auf den Palettennullpunkt (Spiegeln) |
| – | `viz/svg.py` | Zeichnung der Lage (SVG) |
| – | `report/` | HTML-Report und PDF |

Die fachlichen Festlegungen stehen in [doc/planung.md](doc/planung.md).

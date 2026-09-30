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
pip install -e .[dev,gui]      # einmalig (installiert auch pytest und streamlit)

palletizer gui                                         # Bedienoberfläche im Browser
palletizer list                                       # alle Muster
palletizer suggest --box 680x260                       # Musterassistent
palletizer calc --pattern EU36 --box 680x260           # Karton: Förderrichtung x quer
palletizer calc --config examples/eu36.toml --origin 3
palletizer calc --pattern EU36 --box 680x260 --export json,csv,scl,html,pdf
palletizer testvectors                                 # Testvektoren für die SPS erzeugen
palletizer export-patterns                             # Musterdefinitionen als SCL-DB
palletizer docs                                        # Formelsammlung als PDF
pytest                                                 # Tests
```

## Bedienoberfläche

`palletizer gui` startet die Oberfläche im Browser (Streamlit). Links alle Eingaben
(Karton, Muster, Orientierung, Palette, Nullpunkt, Spaltmaß, Überstand, Saugplatte,
Vorposition), rechts Kennzahlen und vier Reiter:

- **Lagenbild & Rechenweg** – der komplette Report mit Schritt-für-Schritt-Ansicht
- **Kartonliste** – Ausgabe an die SPS als Tabelle
- **Musterassistent** – alle Muster mit dem aktuellen Karton, sortiert nach „passt ohne
  Überstand“, Kartonanzahl, Flächennutzung, Drehungen; Muster per Klick übernehmen
- **Export** – Formate auswählen, einzeln herunterladen oder in einen Ordner speichern

## Exporte

Welche Exporte erzeugt werden, ist einstellbar: im Abschnitt `[export]` der
Konfigurationsdatei (siehe `config/defaults.toml`) oder mit `--export` auf der
Kommandozeile (`all`, `none` oder eine Liste). Zielordner `--out`, Dateiname `--name`.

| Format | Datei | Inhalt |
|---|---|---|
| `json` | `.json` | vollständiges Ergebnis inkl. aller Zwischenergebnisse |
| `csv` | `.csv` | Kartonliste für Excel (Trenn-/Dezimalzeichen einstellbar) |
| `scl` | `.scl` | UDTs `typPalInput`, `typPalBox`, `typPalLayer` + DB `DB_PalLayer` mit dem Ergebnis |
| `scl_patterns` | `DB_PalPatterns.scl` | UDT `typPalPattern` + DB mit allen Musterdefinitionen |
| `testvector` | Ordner | alle Zwischenstufen als CSV zum Vergleich mit einer SCL-Umsetzung |
| `html` | `.html` | Report mit Lagenbild, Schritt-für-Schritt-Ansicht und Rechenweg |
| `pdf` | `.pdf` | Report als PDF (über Microsoft Edge bzw. Google Chrome) |

Die SCL-Dateien werden in TIA Portal unter „Externe Quellen“ eingefügt und mit
„Bausteine aus Quelle generieren“ übersetzt.

## Testvektoren

`examples/testvectors.toml` enthält die Fallsammlung (alle 18 Muster, alle Nullpunkte,
Sonderfälle). `palletizer testvectors` schreibt pro Fall einen Ordner nach
`examples/testvectors/` mit `inputs.csv`, `variants.csv`, `blocks.csv`, `sequence.csv`,
`boxes.csv` und `layer.csv` (Trennzeichen `;`, Dezimalpunkt). Ein Test prüft, dass die
abgelegten Dateien zum aktuellen Algorithmus passen – nach einer gewollten Änderung
neu erzeugen und den Git-Diff prüfen.

Der HTML-Report (`--export html`) enthält das Lagenbild mit Schritt-für-Schritt-Steuerung (Karton anklicken,
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
| – | `export/` | JSON, CSV, SCL, Testvektoren |
| – | `assistant.py` | Musterassistent |
| – | `app.py` | Bedienoberfläche (Streamlit) |

## Dokumentation

| Dokument | Inhalt |
|---|---|
| [doc/formelsammlung.html](doc/formelsammlung.html) | alle Formeln mit Skizzen und Rechenbeispiel (PDF: `palletizer docs`) |
| [doc/sps-leitfaden.md](doc/sps-leitfaden.md) | Umsetzung in SCL: UDTs, Bausteine, Pseudocode, Testvektoren, Übergabe an den Roboter |
| [doc/planung.md](doc/planung.md) | freigegebene fachliche Festlegungen |
| [patterns/README.md](patterns/README.md) | Format der Musterdefinitionen, eigene Muster und Plugins |

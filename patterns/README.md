# Layerpattern-Definitionen

Jede `*.toml`-Datei in diesem Ordner (auch in Unterordnern) beschreibt ein Muster.
Die Muster aus `reference/Kave_Layerpattern.pdf` liegen in `eu/`.

## Standardaufbau (ohne Programmierung)

Alle Muster aus dem PDF bestehen aus höchstens zwei Blöcken:

- **Block A**: `cols` Spalten (in X) × `rows` Reihen (in Y), links
- **Block B** (optional): um 90° gedreht, rechts neben Block A, oben bündig

```toml
id = "EU36"                # eindeutige ID
number = 36                # eindeutige Nummer (Auswahl in der SPS: PatternNo)
name = "1x3+2x1 (mixto)"
drawn_long_side = "x"      # Langseite der Kartons von Block A in der Zeichnung: "x" oder "y"
block_a = { cols = 1, rows = 3 }
block_b = { cols = 2, rows = 1 }
```

`drawn_long_side` wird nur als letzter Entscheid bei der Wahl der Orientierung
verwendet. Vorher entscheiden Überstand und Anzahl der Drehungen.

## Ablagereihenfolge übersteuern (optional)

```toml
[sequence]
start_corner = 1                    # Startecke im Grundsystem, 1..4
fill = "rows"                       # "columns" (Standard) oder "rows"
order = ["A.1.1", "A.2.1", "B.1.1"] # komplette Reihenfolge (Block.Spalte.Reihe)
```

## Muster als Python-Plugin

Für Muster, die nicht in den Standardaufbau passen:

```toml
id = "EX01"
number = 901
name = "Windmühle (Beispiel-Plugin)"
plugin = "pinwheel.py:build"   # Datei relativ zu dieser TOML-Datei : Funktion

[params]                        # wird an die Funktion übergeben
arm_boxes = 1
```

Die Funktion `build(px, py, gap, params)` erhält das Kartonmaß in der
Grundorientierung der Variante und liefert eine Liste von `BlockDef`
(Block-ID, linke untere Ecke, Spalten, Reihen, gedreht ja/nein) oder `None`,
wenn das Muster mit diesem Karton nicht darstellbar ist.
Beispiel: `examples/pinwheel.py`.

# Planung und Festlegungen

Freigegebener Stand der Planungsphase. Die ausführliche Formelsammlung und der
SPS-Leitfaden folgen in eigenen Dokumenten.

## Koordinatensystem

- **Grundsystem**: Ursprung E1 = unten links in der PDF-Zeichnung (von oben gesehen),
  X entlang der Palettenlänge (1200), Y entlang der Palettenbreite (800).
- Ecken gegen den Uhrzeigersinn: E1 unten links, E2 unten rechts, E3 oben rechts, E4 oben links.
  Die Zuordnung zu den physischen Ecken wird bei der Inbetriebnahme festgelegt.
- Winkel: 0° = +X, positiv gegen den Uhrzeigersinn.
- Einheiten: mm, Datentyp LREAL.
- Das Muster liegt **physikalisch fest**. Der Palettennullpunkt ändert nur die Zahlen:
  Umrechnung durch **Spiegeln**, alle Koordinaten positiv.

| Nullpunkt | x' | y' | Winkel θ' |
|---|---|---|---|
| E1 | x | y | θ |
| E2 | L_P − x | y | 180° − θ |
| E3 | L_P − x | B_P − y | θ + 180° |
| E4 | x | B_P − y | 360° − θ |

Die Kartondrehung 0°/90° ändert sich beim Spiegeln nicht.

## Karton und Drehung

- Eingabe: Kartonmaß **in** Förderrichtung und **quer** dazu. Keine Normierung der Eingabe.
- Bei 0° liegt die Förderrichtung parallel zu X. Nur 0° und 90°.
- Quadratischer Karton: immer 0°.
- Kommt der Karton mit der Kurzseite voran, wird ein Hinweis ausgegeben.

## Layerpatterns

- 18 Muster aus `reference/Kave_Layerpattern.pdf` (EU-Palette 1200 × 800), Namensschema
  `Spalten x Reihen`.
- Standardaufbau: Block A links, optional Block B um 90° gedreht rechts daneben, oben bündig.
- Die Kartonanzahl ist durch das Muster fest vorgegeben, es wird nicht optimiert.
- Erweiterung: neue TOML-Datei (Standardaufbau) oder Python-Plugin (freie Blockliste).

## Anordnung

- Lage zentriert auf der Palette, Karton an Karton (Spaltmaß einstellbar, Standard 0).
- Überstand: erlaubter Wert je Seite einstellbar (Standard 0). Passt das Muster nicht,
  wird trotzdem gerechnet und gewarnt.
- Einzelner Karton größer als die Palette: zentriert, Warnung.

## Orientierung (Variante X / Y)

Jedes Muster wird in beiden Varianten berechnet (Block A mit Langseite in X bzw. in Y).
Auswahl:

1. weniger Überstand: max(0, W_X − L_P) + max(0, W_Y − B_P)
2. weniger gedrehte Kartons
3. Orientierung laut Zeichnung

Manuelle Vorgabe über `orientation_mode` (1 = X, 2 = Y). Beide Varianten werden angezeigt.

## Ablagereihenfolge

"Dichter Teil zuerst":

1. Blöcke mit mehr Kartons zuerst.
2. Startecke X-seitig gegenüber dem lockeren Teil (Block B), Y-seitig gegenüber der Lücke.
   Ohne Block B/Lücke: Ecke des Palettennullpunkts.
3. Innerhalb des Blocks spaltenweise von der Startecke weg.

Im Pattern überschreibbar (Startecke, Füllrichtung, komplette Reihenfolge).

## Annäherungsrichtung (Modell Nachbarzonen)

- Winkel = Richtung, aus der der Karton kommt. Vorposition = Ziel + s · (cos θ, sin θ), dazu dZ.
- 8 Prüfzonen der Tiefe s um den Karton → 8-Bit-Nachbarmaske (nur bereits abgelegte Kartons).
- Richtung frei: Zone frei; Diagonale zusätzlich beide Nachbarzonen frei.
- Wunschvektor v = −Σ Richtungsvektoren der belegten Zonen; bei v = 0 von außen
  (Palettenmitte → Karton).
- Auswahl: größtes Skalarprodukt mit v, dann mit dem Vektor nach außen, dann feste Rangfolge
  (45°, 135°, 225°, 315°, 0°, 90°, 180°, 270°).
- Keine Richtung frei: Richtung mit den wenigsten belegten Zonen, Warnung.
- Weitere Hindernisse (Umfeld, Reichweite) werden nicht berücksichtigt.

## Saugplatte

- Grundplatte 600 mm in Förderrichtung × 400 mm quer. Ausgefahren symmetrisch quer auf 1400 mm.
- Die Platte sitzt mittig auf dem Karton und dreht sich mit ihm.
- **nötig**: Karton ist in der Ausfahrachse (quer) länger als die Grundplatte (400 mm).
- **erlaubt**: ausgefahrene Platte überdeckt keinen bereits abgelegten Karton.
- **Ausfahren = nötig UND erlaubt**; nötig, aber nicht erlaubt → Warnung.

## Technik

- Python 3.13, Rechenkern nur mit Standardbibliothek, SCL-naher Stil.
- Zuerst Kommandozeile + TOML-Konfiguration, später Streamlit-Oberfläche.
- Ziel-SPS: S7-1500, TIA Portal V20. Array-Grenze MAX_BOXES = 100.
- Exporte: JSON, CSV, SCL-Quelle (UDT + DB), Testvektoren, HTML-Report → PDF (Edge headless),
  Formelsammlung als HTML/PDF.
- Doku deutsch, Bezeichner englisch.

## Etappen

| Etappe | Inhalt | Stand |
|---|---|---|
| M1 | Rechenkern, Muster, Orientierung, Nullpunkt | erledigt |
| M2 | Reihenfolge, Anfahrrichtung, Saugplatte, Warnungen | erledigt |
| M3 | Exporte und SCL-Testvektoren (Formate einzeln einstellbar) | erledigt |
| M4 | Report und Visualisierung inkl. PDF | erledigt |
| M5 | Formelsammlung und SPS-Leitfaden | erledigt |
| M6 | Musterassistent und Streamlit-Oberfläche | erledigt |

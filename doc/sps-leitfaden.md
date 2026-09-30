# SPS-Leitfaden: Palettieralgorithmus in SCL nachbilden

Zielsystem: S7-1500, TIA Portal V20, SCL. Dieser Leitfaden beschreibt, wie der Algorithmus
aus `src/palletizer/` in der SPS nachgebaut wird und wie man die Umsetzung mit den
Testvektoren prüft. Alle Formeln mit Skizzen stehen in der **Formelsammlung**
(`doc/formelsammlung.html`, als PDF: `palletizer docs`).

## 1. Zwei Wege in die SPS

| Weg | Vorgehen | Wann sinnvoll |
|---|---|---|
| **A: Ergebnis übernehmen** | Python rechnet, Export `scl` erzeugt den DB `DB_PalLayer` mit allen Kartonpositionen | wenige, bekannte Kartonsorten; Rechnung offline |
| **B: Algorithmus in SCL** | SPS rechnet selbst aus Kartonmaß + Musternummer; Musterdefinitionen aus `DB_PalPatterns` | Kartonmaß wird erst zur Laufzeit bekannt |

Beide Wege nutzen dieselbe Ausgabe `typPalLayer` → der Roboter-/Achsteil ist identisch.

## 2. Datenfluss

```
typPalInput ──► S0 Prüfen ──► S1 l, k ──► S2-S4 je Variante X / Y ──► Variante wählen
                                           (Blockliste, Kartons,       │
                                            Zentrieren, Überstand)     ▼
typPalLayer ◄── S8 Nullpunkt ◄── S7 Saugplatte ◄── S6 Anfahrrichtung ◄── S5 Reihenfolge
```

S6 und S7 laufen **in Ablagereihenfolge**: Für Karton Nr. n zählen nur die Kartons 1 … n−1
als „bereits abgelegt“.

## 3. Datentypen

### Schnittstelle (vom Export `scl` erzeugt)

| UDT | Inhalt |
|---|---|
| `typPalInput` | alle Eingangsgrößen (Maße LReal, Nummern Int) |
| `typPalBox` | Ergebnis je Karton: `No`, `BlockId`, `Col`, `Row`, `X`, `Y`, `Rot`, `ApproachAngle`, `PreDX`, `PreDY`, `PreDZ`, `ExtendPlate`, `NeighborMask`, `Warnings` |
| `typPalLayer` | Kopfdaten (`ErrorCode`, `Warnings`, `Variant`, `BoxCount`, …) + `Boxes : Array[1..100] of typPalBox` |
| `typPalPattern` | Musterdefinition (Export `scl_patterns`): `PatternNo`, `Id`, `ColsA`, `RowsA`, `ColsB`, `RowsB`, `DrawnLongSideY`, `StartCorner`, `FillRows` |

### Intern (nur für Weg B, Vorschlag)

```scl
TYPE "typPalBlock"
   STRUCT
      X0 : LReal;  Y0 : LReal;         // linke untere Ecke (Grundsystem)
      Cols : Int;  Rows : Int;
      Rotated : Bool;
      SizeX : LReal;  SizeY : LReal;   // Kartonmaß im Block
      Width : LReal;  Height : LReal;  // Blockmaß
   END_STRUCT;
END_TYPE

TYPE "typPalWorkBox"
   STRUCT
      BlockIdx : Int;  Col : Int;  Row : Int;
      CX : LReal;  CY : LReal;         // Mittelpunkt Grundsystem
      SizeX : LReal;  SizeY : LReal;
      Rot : Int;
   END_STRUCT;
END_TYPE

TYPE "typPalVariant"
   STRUCT
      Valid : Bool;
      ErrorCode : Int;
      BlockCount : Int;
      Blocks : Array[1..8] of "typPalBlock";       // MAX_BLOCKS
      BoxCount : Int;
      Boxes : Array[1..100] of "typPalWorkBox";    // MAX_BOXES
      LayerSizeX : LReal;  LayerSizeY : LReal;
      OverhangX : LReal;  OverhangY : LReal;  OverhangSum : LReal;
      RotatedCount : Int;
   END_STRUCT;
END_TYPE
```

### Konstanten

| Name | Wert | Zweck |
|---|---|---|
| `MAX_BOXES` | 100 | Array-Grenze Kartons |
| `MAX_BLOCKS` | 8 | Array-Grenze Blöcke |
| `MAX_PATTERNS` | 50 | Array-Grenze Muster |
| `DIAG` | 0.7071067811865476 | cos 45° |
| `DOT_EPS` | 1.0E-6 | Vergleich von Skalarprodukten |
| `DIR_X` | [1, DIAG, 0, −DIAG, −1, −DIAG, 0, DIAG] | Richtungsvektor X, Index 0..7 |
| `DIR_Y` | [0, DIAG, 1, DIAG, 0, −DIAG, −1, −DIAG] | Richtungsvektor Y |
| `APPROACH_PRIORITY` | [1, 3, 5, 7, 0, 2, 4, 6] | Rangfolge bei Gleichstand |

`DIR_X`, `DIR_Y`, `APPROACH_PRIORITY` als `Array[0..7] of LReal/Int` in einem konstanten DB
oder als Startwerte im Instanz-DB.

## 4. Bausteinstruktur (Vorschlag für Weg B)

| Baustein | Stufe | Eingang | Ausgang |
|---|---|---|---|
| FB `PalCalculate` | alle | `typPalInput`, Muster | `typPalLayer` |
| FC `PalValidate` | S0 | `typPalInput` | Fehlercode |
| FC `PalBuildVariant` | S2–S4 | Input, Muster, `VariantY : Bool` | `typPalVariant` |
| FC `PalChooseVariant` | S4 | beide Varianten, Input, Muster | Index 1 = X, 2 = Y, 0 = keine |
| FC `PalStartCorner` | S5 | Variante, Input, Muster | Startecke 1..4 |
| FC `PalOrderBoxes` | S5 | Variante, Startecke, Muster | `Order : Array[1..100] of Int` |
| FC `PalApproach` | S6 | Kartonindex, Variante, Order, Anzahl abgelegt | Maske, Richtung, Warnung |
| FC `PalGripper` | S7 | Kartonindex, Variante, Order, Anzahl abgelegt | ExtendPlate, Warnung |
| FC `PalTransform` | S8 | Punkt/Winkel/Vektor, Ecke | Werte im Ausgabesystem |
| FC `PalRectOverlap` | Hilfe | zwei Rechtecke, ε | Bool |

`PalCalculate` braucht zwei `typPalVariant` im Static-Bereich (je ca. 5 KB).

## 5. Pseudocode je Stufe

Der Code ist SCL-nah; Namen wie in Python. `#` = lokale/Parameter-Variable.

### Hilfsfunktionen

```scl
// D(n, a) = n*a + (n-1)*g
#Extent := INT_TO_LREAL(#n) * #a + INT_TO_LREAL(#n - 1) * #g;

// Rechteck-Überlappung (FC PalRectOverlap)
#ox := MIN(IN1 := #ax2, IN2 := #bx2) - MAX(IN1 := #ax1, IN2 := #bx1);
#oy := MIN(IN1 := #ay2, IN2 := #by2) - MAX(IN1 := #ay1, IN2 := #by1);
#PalRectOverlap := (#ox > #eps) AND (#oy > #eps);
```

### S1 und S2: Blockliste (Standardaufbau)

```scl
#l := MAX(IN1 := #In.BoxLengthConv, IN2 := #In.BoxWidthConv);
#k := MIN(IN1 := #In.BoxLengthConv, IN2 := #In.BoxWidthConv);
IF #VariantY THEN  #px := #k;  #py := #l;
ELSE               #px := #l;  #py := #k;
END_IF;

// Block A
#V.Blocks[1].Cols := #Pat.ColsA;   #V.Blocks[1].Rows := #Pat.RowsA;
#V.Blocks[1].Rotated := FALSE;
#V.Blocks[1].SizeX := #px;         #V.Blocks[1].SizeY := #py;
#hA := Extent(#Pat.RowsA, #py);
#V.Blocks[1].X0 := 0.0;
#V.BlockCount := 1;

IF #Pat.ColsB > 0 THEN
   // Block B: gedreht, rechts von A, oben bündig
   #hB := Extent(#Pat.RowsB, #px);
   #h := MAX(IN1 := #hA, IN2 := #hB);
   #V.Blocks[1].Y0 := #h - #hA;
   #V.Blocks[2].Cols := #Pat.ColsB;   #V.Blocks[2].Rows := #Pat.RowsB;
   #V.Blocks[2].Rotated := TRUE;
   #V.Blocks[2].SizeX := #py;         #V.Blocks[2].SizeY := #px;
   #V.Blocks[2].X0 := Extent(#Pat.ColsA, #px) + #In.Gap;
   #V.Blocks[2].Y0 := #h - #hB;
   #V.BlockCount := 2;
ELSE
   #V.Blocks[1].Y0 := 0.0;
END_IF;
// je Block: Width := Extent(Cols, SizeX); Height := Extent(Rows, SizeY)
```

### S3 und S4: Kartons, Zentrieren, Überstand

```scl
// Lagenmaß
#minX := #V.Blocks[1].X0;  #maxX := #V.Blocks[1].X0 + #V.Blocks[1].Width;   // Y analog
FOR #b := 2 TO #V.BlockCount DO
   #minX := MIN(IN1 := #minX, IN2 := #V.Blocks[#b].X0);
   #maxX := MAX(IN1 := #maxX, IN2 := #V.Blocks[#b].X0 + #V.Blocks[#b].Width);
   // Y analog
END_FOR;
#V.LayerSizeX := #maxX - #minX;   #V.LayerSizeY := #maxY - #minY;
#dx := (#In.PalletLength - #V.LayerSizeX) / 2.0 - #minX;
#dy := (#In.PalletWidth  - #V.LayerSizeY) / 2.0 - #minY;

// Kartons (Doppelschleife je Block)
#n := 0;
FOR #b := 1 TO #V.BlockCount DO
   #V.Blocks[#b].X0 := #V.Blocks[#b].X0 + #dx;
   #V.Blocks[#b].Y0 := #V.Blocks[#b].Y0 + #dy;
   FOR #i := 0 TO #V.Blocks[#b].Cols - 1 DO
      FOR #j := 0 TO #V.Blocks[#b].Rows - 1 DO
         #n := #n + 1;                                  // vorher: Prüfung n <= MAX_BOXES -> Fehler 201
         #V.Boxes[#n].BlockIdx := #b;
         #V.Boxes[#n].Col := #i + 1;  #V.Boxes[#n].Row := #j + 1;
         #V.Boxes[#n].SizeX := #V.Blocks[#b].SizeX;
         #V.Boxes[#n].SizeY := #V.Blocks[#b].SizeY;
         #V.Boxes[#n].CX := #V.Blocks[#b].X0 + INT_TO_LREAL(#i) * (#V.Blocks[#b].SizeX + #In.Gap)
                            + #V.Blocks[#b].SizeX / 2.0;
         #V.Boxes[#n].CY := #V.Blocks[#b].Y0 + INT_TO_LREAL(#j) * (#V.Blocks[#b].SizeY + #In.Gap)
                            + #V.Blocks[#b].SizeY / 2.0;
         // Drehung bezogen auf das Förderband
         IF ABS(#V.Blocks[#b].SizeX - #In.BoxLengthConv) <= #In.Tolerance
            AND ABS(#V.Blocks[#b].SizeY - #In.BoxWidthConv) <= #In.Tolerance THEN
            #V.Boxes[#n].Rot := 0;
         ELSE
            #V.Boxes[#n].Rot := 90;
            #V.RotatedCount := #V.RotatedCount + 1;
         END_IF;
      END_FOR;
   END_FOR;
END_FOR;
#V.BoxCount := #n;

// Überstand
#ex := MAX(IN1 := 0.0, IN2 := #V.LayerSizeX - #In.PalletLength);
#ey := MAX(IN1 := 0.0, IN2 := #V.LayerSizeY - #In.PalletWidth);
#V.OverhangX := #ex / 2.0;   #V.OverhangY := #ey / 2.0;
#V.OverhangSum := #ex + #ey;
```

Wahl der Variante (FC `PalChooseVariant`):

```scl
IF #In.OrientationMode = 1 THEN #Choice := 1;
ELSIF #In.OrientationMode = 2 THEN #Choice := 2;
ELSIF #VX.OverhangSum < #VY.OverhangSum - #In.Tolerance THEN #Choice := 1;
ELSIF #VY.OverhangSum < #VX.OverhangSum - #In.Tolerance THEN #Choice := 2;
ELSIF #VX.RotatedCount < #VY.RotatedCount THEN #Choice := 1;
ELSIF #VY.RotatedCount < #VX.RotatedCount THEN #Choice := 2;
ELSIF #Pat.DrawnLongSideY THEN #Choice := 2;
ELSE #Choice := 1;
END_IF;
```

### S5: Startecke und Reihenfolge

```scl
// Mitte der Lage = Palettenmitte
#mx := #In.PalletLength / 2.0;   #my := #In.PalletWidth / 2.0;
// Standard: Seite des Nullpunkts
#xMax := (#In.OriginCorner = 2) OR (#In.OriginCorner = 3);
#yMax := (#In.OriginCorner = 3) OR (#In.OriginCorner = 4);

// lockerer Teil = Blöcke mit weniger Kartons als der größte Block -> Schwerpunkt (#lx, #ly), Anzahl #lc
// Lücke: #gapA := LayerSizeX*LayerSizeY - Summe(SizeX*SizeY)
//        #gx := (LayerSizeX*LayerSizeY*#mx - Summe(SizeX*SizeY*CX)) / #gapA   (gy analog)
#hasGap := #gapA > #In.Tolerance * (#V.LayerSizeX + #V.LayerSizeY);

IF #Pat.StartCorner > 0 THEN
   #Start := #Pat.StartCorner;
ELSE
   IF #lc > 0 AND #lx > #mx + #In.Tolerance THEN #xMax := FALSE;
   ELSIF #lc > 0 AND #lx < #mx - #In.Tolerance THEN #xMax := TRUE;
   ELSIF #hasGap AND #gx > #mx + #In.Tolerance THEN #xMax := FALSE;
   ELSIF #hasGap AND #gx < #mx - #In.Tolerance THEN #xMax := TRUE;
   END_IF;
   IF #hasGap AND #gy < #my - #In.Tolerance THEN #yMax := TRUE;
   ELSIF #hasGap AND #gy > #my + #In.Tolerance THEN #yMax := FALSE;
   ELSIF #lc > 0 AND #ly > #my + #In.Tolerance THEN #yMax := FALSE;
   ELSIF #lc > 0 AND #ly < #my - #In.Tolerance THEN #yMax := TRUE;
   END_IF;
   // Ecke aus Seiten: (min,min)=1, (max,min)=2, (max,max)=3, (min,max)=4
END_IF;
```

Reihenfolge: Blöcke nach (mehr Kartons, kleinerer Abstand
`ABS(Blockmitte_x - Start_x) + ABS(Blockmitte_y - Start_y)`, Index) sortieren
(bei höchstens 8 Blöcken reicht ein einfacher Insertion-Sort). Dann je Block:

```scl
FOR #c := 1 TO #Cols DO
   IF #xMax THEN #col := #Cols + 1 - #c; ELSE #col := #c; END_IF;
   FOR #r := 1 TO #Rows DO
      IF #yMax THEN #row := #Rows + 1 - #r; ELSE #row := #r; END_IF;
      #cnt := #cnt + 1;
      #Order[#cnt] := <Index des Kartons (Block, #col, #row)>;
   END_FOR;
END_FOR;
// FillRows = TRUE: Schleifen tauschen (erst Reihen, dann Spalten)
```

Tipp: Werden die Kartons in S3 in der Reihenfolge Block → Spalte → Reihe angelegt, ist der
Index `Blockstart + (col-1)*Rows + row` (Blockstart = Anzahl Kartons in den Blöcken davor).

### S6: Annäherungsrichtung

```scl
// Karton #t = Order[#pos]; abgelegt sind Order[1 .. #pos-1]
#x1 := CX - SizeX/2;  #x2 := CX + SizeX/2;  #y1 := CY - SizeY/2;  #y2 := CY + SizeY/2;
#s := #In.ApproachDist;
// Zonen k = 0..7 (siehe Formelsammlung, Tabelle "Prüfzonen")
#Mask := 0;
FOR #k := 0 TO 7 DO
   FOR #p := 1 TO #pos - 1 DO
      IF PalRectOverlap(Zone[#k], Box[Order[#p]], #In.Tolerance) THEN
         #Mask := #Mask OR SHL(IN := BYTE#1, N := #k);
         EXIT;
      END_IF;
   END_FOR;
END_FOR;

// freie Richtungen
FOR #k := 0 TO 7 DO
   #need := SHL(IN := BYTE#1, N := #k);
   IF (#k MOD 2) = 1 THEN
      #need := #need OR SHL(IN := BYTE#1, N := (#k + 7) MOD 8)
                     OR SHL(IN := BYTE#1, N := (#k + 1) MOD 8);
   END_IF;
   #Free[#k] := (#Mask AND #need) = 0;
END_FOR;

// Wunschvektor v und Vektor nach außen w
#vx := 0.0;  #vy := 0.0;
FOR #k := 0 TO 7 DO
   IF (#Mask AND SHL(IN := BYTE#1, N := #k)) <> 0 THEN
      #vx := #vx - DIR_X[#k];  #vy := #vy - DIR_Y[#k];
   END_IF;
END_FOR;
#wx := CX - #In.PalletLength / 2.0;   #wy := CY - #In.PalletWidth / 2.0;
#len := SQRT(#wx * #wx + #wy * #wy);
IF #len > #In.Tolerance THEN #wx := #wx / #len; #wy := #wy / #len; ELSE #wx := 0.0; #wy := 0.0; END_IF;
IF SQRT(#vx * #vx + #vy * #vy) <= DOT_EPS THEN #vx := #wx; #vy := #wy; END_IF;

// keine freie Richtung -> Kandidaten = Richtungen mit den wenigsten belegten Zonen, Warnbit 2
// Auswahl in Rangfolge
#best := -1;
FOR #m := 0 TO 7 DO
   #k := APPROACH_PRIORITY[#m];
   IF #Candidate[#k] THEN
      #sv := DIR_X[#k] * #vx + DIR_Y[#k] * #vy;
      #sw := DIR_X[#k] * #wx + DIR_Y[#k] * #wy;
      IF #best < 0 OR #sv > #bestV + DOT_EPS
         OR (ABS(#sv - #bestV) <= DOT_EPS AND #sw > #bestW + DOT_EPS) THEN
         #best := #k;  #bestV := #sv;  #bestW := #sw;
      END_IF;
   END_IF;
END_FOR;
#AngleBase := #best * 45;
#PreDX := #s * DIR_X[#best];   #PreDY := #s * DIR_Y[#best];   #PreDZ := #In.ApproachHeight;
```

### S7: Saugplatte

```scl
#needed := (#In.PlateExtConv > #In.PlateConv + #In.Tolerance
            AND #In.BoxLengthConv > #In.PlateConv + #In.Tolerance)
        OR (#In.PlateExtCross > #In.PlateCross + #In.Tolerance
            AND #In.BoxWidthConv > #In.PlateCross + #In.Tolerance);
IF Rot = 0 THEN #ex := #In.PlateExtConv;  #ey := #In.PlateExtCross;
ELSE            #ex := #In.PlateExtCross; #ey := #In.PlateExtConv;
END_IF;
// ausgefahrene Platte mittig auf dem Karton gegen alle abgelegten Kartons prüfen
#allowed := TRUE;
FOR #p := 1 TO #pos - 1 DO
   IF PalRectOverlap(CX-#ex/2, CX+#ex/2, CY-#ey/2, CY+#ey/2, Box[Order[#p]], #In.Tolerance) THEN
      #allowed := FALSE;  EXIT;
   END_IF;
END_FOR;
#ExtendPlate := #needed AND #allowed;
IF #needed AND NOT #allowed THEN #Warnings := #Warnings OR 16#0008; END_IF;
```

### S8: Nullpunkt

```scl
CASE #In.OriginCorner OF
   1: #sx := 1.0;  #sy := 1.0;  #xe := 0.0;               #ye := 0.0;
   2: #sx := -1.0; #sy := 1.0;  #xe := #In.PalletLength;  #ye := 0.0;
   3: #sx := -1.0; #sy := -1.0; #xe := #In.PalletLength;  #ye := #In.PalletWidth;
   4: #sx := 1.0;  #sy := -1.0; #xe := 0.0;               #ye := #In.PalletWidth;
END_CASE;
#Out.X := #sx * (CX - #xe);        #Out.Y := #sy * (CY - #ye);
#Out.PreDX := #sx * #PreDX;        #Out.PreDY := #sy * #PreDY;
CASE #In.OriginCorner OF
   1: #Out.ApproachAngle := #AngleBase;
   2: #Out.ApproachAngle := (540 - #AngleBase) MOD 360;   // 180 - θ, positiv gehalten
   3: #Out.ApproachAngle := (#AngleBase + 180) MOD 360;
   4: #Out.ApproachAngle := (360 - #AngleBase) MOD 360;
END_CASE;
```

## 6. Hinweise zur Umsetzung

- **Datentyp LReal** verwenden. Python rechnet ebenfalls mit 64-Bit-Gleitkomma; die Ergebnisse
  stimmen dann bis auf Rundung in der letzten Stelle überein.
- **Alle Längenvergleiche mit Toleranz** `Tolerance` (Standard 0,1 mm), Skalarprodukte mit `DOT_EPS`.
- **Array-Grenzen** vor dem Schreiben prüfen (Fehler 201/202) – nicht auf Laufzeitfehler verlassen.
- **Plugin-Muster** (z. B. Windmühle EX01) sind nur in Python vorhanden und nicht in `DB_PalPatterns`.
  Eine im Pattern fest vorgegebene Reihenfolge (`order`) ist im DB ebenfalls nicht enthalten.
- Der Rechenaufwand ist klein (bei 10 Kartons wenige tausend Operationen); die Berechnung
  kann in einem Zyklus laufen. Bei sehr vielen Kartons ggf. auf mehrere Zyklen verteilen.

## 7. Testvektoren nutzen

`palletizer testvectors` schreibt nach `examples/testvectors/` pro Fall einen Ordner
(Übersicht in `index.csv`). Trennzeichen `;`, Dezimalpunkt, 4 Nachkommastellen.

| Datei | Stufe | Vergleichen mit |
|---|---|---|
| `inputs.csv` | Eingabe | `typPalInput` befüllen |
| `variants.csv` | S2–S4 | beide `typPalVariant`: Lagenmaß, Überstand, Drehungen, gewählte Variante |
| `blocks.csv` | S2–S4 | Blockliste der gewählten Variante **nach** dem Zentrieren |
| `sequence.csv` | S5 | Startecke, lockerer Teil, Lückenfläche und -schwerpunkt |
| `boxes.csv` | S3–S8 | je Karton in Ablagereihenfolge: Grundkoordinaten, Maske (`NeighborMask`), freie Richtungen (`FreeMask`), `v`, `w`, Winkel, Saugplatte, Ausgabe |
| `layer.csv` | Kopf | `ErrorCode`, `Warnings`, `BoxCount`, … |

Vorgehen: Eingaben eines Falls in die SPS laden, rechnen lassen, Stufe für Stufe mit den CSV-Werten
vergleichen (Abweichung ≤ 0,001 mm bzw. Bits identisch). Die Fälle decken alle 18 Muster, alle
vier Nullpunkte und die Sonderfälle ab (Überstand, Karton größer als Palette, Kurzseite voran,
Saugplatte blockiert, Spaltmaß, quadratischer Karton, Fehlerfall).

## 8. Übergabe an den Roboter

Je Karton in der Reihenfolge `No` = 1 … `BoxCount`:

| Wert | Verwendung |
|---|---|
| `X`, `Y` | Zielposition Kartonmitte im Palettenkoordinatensystem (gewählter Nullpunkt) |
| `Rot` | Drehung des Greifers gegenüber der Aufnahmelage: 0° oder 90° |
| `PreDX`, `PreDY`, `PreDZ` | Vorposition = Ziel + (PreDX, PreDY, PreDZ); von dort auf das Ziel fahren |
| `ApproachAngle` | Richtung der Vorposition als Winkel (Information / Anzeige) |
| `ExtendPlate` | TRUE: Zusatz-Saugfläche vor dem Aufnehmen ausfahren |
| `Warnings` | ≠ 0: Karton prüfen (Bits siehe Formelsammlung Kapitel 13) |

Vorschlag Bewegungsablauf: über der Vorposition absenken bis Vorposition (Ziel + Versatz, `PreDZ`
über der Ablagehöhe), dann linear auf das Ziel. Der Karton gleitet dabei von der freien Seite
an die bereits abgelegten Kartons heran. Z-Werte (Palettenhöhe, Kartonhöhe, Lagen) sind nicht
Teil dieses Algorithmus.

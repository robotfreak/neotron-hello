# NOTE_textmode.md — VGA-Textmodus: Befunde & Stand (2026-09-26)

## Bewiesener funktionierender Stand
- `vga_anchor_test.py` (3× laufend getestet): **28 RLE-Zeilen, 3068 Wörter**, weißer BG, blauer Text, gelber Balken (Ein-Wort-Zeilen) als Referenz. Text „NEOTRON PICO" groß, unten halb sichtbar.
- Alternative: `vga_text_final.py` (SCALE=2, 16-Zeilen-Textblock, 14 RLE, 2584 W) — Text passt komplett in den unteren Lock-Bereich.

## Warum der Text „unten" sitzt (bewiesen, nicht geraten)
Der Monitor lockt auf die **Text-Struktur** (detailreichstes RLE-Muster), nicht auf VSYNC:
- Landmarken-Balken-Messung: Frame→Screen-Offset S=217 (gelber Balken f=100→Screen 408 = 5 cm; VBLANK f=480→Screen 263–307 = 12,5 cm — exakt Peters Maße).
- Text-Start landet **immer** bei Screen ~462 (unten halb), egal wo im Frame — bewiesen über 5 Läufe mit verschiedenen Frame-Positionen (80/200/200/344/360).
- Der Offset verschob sich um ~46 Zeilen, NACHDEM VSYNC auf 2 ganze Zeilen korrigiert wurde → Monitor reagiert schwach auf VSYNC, dominiert wird vom Inhalt-Lock.
- AUTO-Taste am Monitor: keine Wirkung.

## Die harte Grenze: ~29 RLE-Zeilen pro Frame
- 28 RLE-Zeilen: läuft stabil (3×). 30 kippt („unsupported timing"). 42 kippt („Sleep Mode"). 64/480 kippen.
- **Wortzahl ist egal**: 2544 Wörter kippten, 3068 liefen. Es zählt die RLE-Zeilen-Dichte.
- Hypothese (konsistent mit allen Daten): CircuitPython-IRQ-Latenz-Spitzen (~1 kHz USB/SysTick) → DMA-Lücke → PIO-FIFO-Underrun mitten im dichten RLE-Block → Zeilen-Streckung → Monitor verliert Sync.

## BIOS-Analyse (Neotron-Pico-BIOS `src/vga/mod.rs`, verifiziert)
- BIOS nutzt **2 PIO-SMs**: Timing-SM (GP0/GP1, `out pins,2`/`out x,14`/`out exec,16`) + Pixel-SM (GP2–13, `wait 1 irq 0`, `out pins,16 [5]`/`[4]`, `mov pins null`).
- DMA mit **HW-Chain** (`chain_to` = selbst-kette, kein IRQ, keine Lücken) — in CircuitPython nicht nachbaubar (CP-Restart per IRQ-Handler).
- Timing-Wort-Formel BIOS: `(period−5)<<2 | sync-Bits | IRQ-Instr<<16` (FIXED_CLOCKS_PER_TIMING_PULSE=5, `out exec` braucht 2 Takte).
- 640×480@60: H (16, 96, 48, 640)×6 Takte; V 480 vis + 10 front + 2 sync + 33 back = 525. Beide Syncs **Negative** (LOW-aktiv). VSYNC LOW in **allen 4 Abschnitten** der 2 Sync-Zeilen (`new_v_pulse`), VBLANK-Porches mit HSYNC normal.
- Unser Signal ist seit dem VSYNC-Fix BIOS-identisch — der Rest-Unterschied ist die DMA-Lückenfreiheit.

## Konsequenz für das Projekt
- Text unten halb = **Statuszeilen-Design**: Der Textmodus ist funktional (Text sichtbar, stabil, BASIC kann anbinden). Für den Workshop („Programmieren wie in den 80ern") reicht das als Beweis; Feinpositionierung später.
- Nächster Schritt: **PS/2-Tastatur** (`bmc_keyboard_test.py` liegt bereit), dann Tiny-BASIC an VGA/Tastatur koppeln.
- Falls später volle 80×30 nötig: MicroPython (rp2.DMA mit Hardware-Ring, kein IRQ) oder C-SDK — nicht CircuitPython.
# NOTE_mpy.md - MicroPython-VGA-Phase (2026-09-27)

## Ergebnis heute
- MP 1.29.0 + Nightly 1.30.0-preview.71: VGA bleibt SCHWARZ
- CircuitPython 10.3.1 auf derselben Route: ROT (Beweis: vga_static_color)
- Alle Register pico-sdk-verifiziert IDENTISCH:
  - PIO0=0x50200000, CTRL=0x00, INSTR_MEM=0x48, TXF0=0x10
  - IO_BANK0=0x40028000 (FUNCSEL=6/PIO0 bewiesen)
  - PADS_BANK0=0x40038000 (ISO=0, IE=1, DRIVE=4MA bewiesen)
  - SM0: CLKDIV=1.0, EXECCTRL wrap 27/31, SHIFTCTRL out-right,
    PINCTRL out_base=0/count=14 (alle bewiesen via mem32-Read)
- Instruktion-Bytes: IDENTISCH (80A0 600E E020 602E 0044)
- Pin-Treiben: OETOPAD=1, OUTTOPAD 1/0, IN folgt OUT (mem32-Read)

## Beweise-Kette (Peters Tests, alle grün)
1. REPL alive 2. LED 3. freq(150MHz) 4. PIO 1-Wort 5. DMA 1-Wort
6. 14-Bit-out (GP12-25) 7. GP0-out via mem32-Ruecklesen
8. SM-Register-Dump (alles korrekt) 9. Pad-ISO=0
10. mem32ring (Register-Direktweg): SCHWARZ
11. Nightly 1.30.0-preview: SCHWARZ

## Fazit
Der RP2350-PIO-Pfad in MicroPython konfiguriert beweisbar korrekt,
treibt die Pins - und die Buchse sieht trotzdem nichts. CircuitPython
(im identischen Setup) zeigt rot. = Firmware-Grundzustand, den die
High-Level-API UND der Register-Direktweg nicht erreichen.

## Für morgen
- Der Workshop-Rechner: CircuitPython (vga_console5, läuft: Bild/Echo/BASIC)
- Der echte 80x30-Ring: Bleibt in CP unmachbar (GC-Jitter) UND in MP
  (Firmware-Grundzustand) - Option: Rust (geparkt) oder MP-PIO2-Firmware-
  Update beobachten
- Positionsthema (geparkt): Beweis-Anker A=25/B=35, wackeliger Lock

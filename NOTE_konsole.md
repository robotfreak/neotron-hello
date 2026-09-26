# NOTE_konsole.md — BASIC-Konsole: Stand (2026-09-26 Abend)

## Bewiesen laufend (heute verifiziert)
- BMC-SPI: Firmware pico-v0.5.4 gelesen (Status 0xA0). CS-Weg: BMC = GP21
  (noutput_en → 74HC138-CS0, GPIOA=0), MCP23S17 = GP17. Readback IODIRB
  0x5A bewies Bus + GP17.
- Tastatur-FIFO Register 0x40: Scancodes kommen (diag: a0 01 16 = "1",
  5a=Enter, 4b=L, 42=K, f0=Release). Poll OHNE nirq-Gate (nirq/MCP-INT
  kommt nie - GPIOB-Lese-Handling fehlt, Poll IMMER als Workaround).
- tinybasic.py: repl() NUR unter __name__=="__main__" (Import blockierte
  sonst im echten input() -> Thonny-"Hang"). 17/17 Tests OK.
- Konsole: BASIC-Fehlermeldungen erschienen auf VGA/Serial ("Unbekannter
  Befehl: UN110", "= erwartet") - Engine + out()-Shim laufen.
- VGA-Frame: 2100 Wörter leer (v9-Struktur), Updates liefen 5-6x auf
  Monitor (3048/3052 W) BEVOR Kipp.

## Offen: "unsupported timing" beim VGA (aktuelle Blockade)
- Konsole kippt den Monitor; der BMC-SPI-Poll neben der VGA-DMA ist der
  Hauptverdächtige (je Poll ~1ms CPU-Busy, kollidiert evtl. mit DMA-
  Restart-IRQ-Fenster). Stand: Poll gedrosselt auf 2x/s + bewiesene
  v9-Struktur zurück (Commit 302e92d) - VON PETER NOCH NICHT GETESTET.
- Nächste Schritte morgen:
  1. 302e92d testen (Monitor kommt? -> Poll-Rate anheben, Limit finden)
  2. Wenn kippt: VGA komplett ohne BMC-Init testen (reiner v9-Frame) ->
     Beweis, dass BMC-Transfer die DMA-Kette stört -> Polls zwischen
     Frames timen (nach VSYNC) ODER Poll-IRQ-gesteuert
- Performance-Durchbruch liegt bereit (b178643: fit_words/feste 30
  Wörter je Fontzeile, In-Place-Patch ~10-20ms statt 1700ms) - aber die
  Fest-30-Struktur kippte; fit_words (balancierte Splits) ist in der
  Datei, wird von build_frame NICHT mehr genutzt. Morgen wieder
  versuchen, sobald VGA stabil ist.
- Wort-Grenzen: 3052/3068 liefen bewiesen; 3226 kippt. 12KB-Grenze
  (12288 B) als Muster.

## Dateien
- vga_basic_console.py (als code.py) + tinybasic.py + font8x8.py
- Stufen-Marker [1]-[10] in der Datei (Serial-Diagnose bleibt drin)
- diag-Zeilen alle 5s auf Serial (nirq + Register 0x40-Rohdaten)
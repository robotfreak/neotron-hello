# vga_text_test.py - VGA Textmodus 80x30 (BIOS-Architektur, EINE PIO-SM + DMA)
#
# Grundlage: vga_dma_color_test.py (verifiziert auf dem PCB - rotes Bild lief!)
# Neu: Font-Rendering in Python (font8x8, 8x8 Pixel) - der DMA-Loop wird pro
#      Frame neu gefuettert: jede sichtbare Zeile bekommt ihre Pixel-Woerter.
#
# Layout: 8x8 Font, 80 Zeichen x 30 Zeilen = 640x480.
# Zeile = 4800 Takte @150 MHz = 6 Takte/Pixel -> 25 MHz Pixeltakt.
# 1 Pixel = 1 PIO-Wort mit 6 Takten? Nein: Wir treiben Pixel als Farben fuer
# 6 Takte: 1 Farbe-Wort = color|bits14+15, Loop-Zaehler = 5 (6 Takte).
#
# Wortformat (32 Bit): bit0-13 = RGB (12 Bit Farbe), bit14+15 = HSYNC/VSYNC,
#   bit16-31 = Loop-Zaehler. 480 sichtbare Pixel a 6 Takte = 2880 Woerter/Zeile
#   + 4 Timing-Woerter (Front/Sync/Back/Vis-Null) -> 2884 Woerter pro Zeile? ZU VIEL
#   fuer einen DMA-Loop (Speicher!).
#
# PRAKTISCH: Nur Zeile 0-479 sichtbar, wir schreiben TEXT in die oberen 4 Zeilen
# ("HELLO" 4x8 Pixel) und lassen den Rest schwarz. Loop-Woerter pro Frame:
#   480*4 Timing + Text-Zeilen: 4 Zeilen a (1 Front + 1 Sync + 1 Back + 80*8=640 Pixel) 
#   = 4*643 = 2572 + 476*4 = 1904 -> 4476 Woerter a 4 Byte = 17.9 KB pro Frame.
# CircuitPython: array mit 17.9 KB passt (520 KB RAM). Rebuild-Zeit in Python:
#   ~4448 Worte * 3 ops = triviale Last, aber ~50 ms/Frame @ 1x pro Frame reicht.
#
# Text: "NEOTRON PICO BASIC" in Gelb oben links.
# Als code.py auf CIRCUITPY. LED blinkt. Beenden: Strg+C.
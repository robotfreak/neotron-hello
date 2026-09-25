# vga_text_test.py - VGA Textmodus: "NEOTRON PICO" in 8x8-Font auf dem Monitor
#
# Basiert auf der verifizierten DMA-Architektur (vga_dma_color_test.py):
# EINE PIO-SM @ 150 MHz treibt GP0..GP13 aus einem DMA-Ringpuffer mit
# 32-Bit-Woertern: bit0-1 = HSYNC/VSYNC (aktiv LOW), bit2-13 = RGB 4-4-4,
# bit14-31 = Loop-Zaehler. 6 Takte pro Pixel -> 25 MHz effektiv.
#
# Text-Rendering: font8x8.py (Public-Domain-Font), 8x8 Pixel, 80x30 Zeichen.
# Wir rendern in einen Zeilen-Wort-Puffer und starten einen DMA-Write pro
# Frame (background_write ohne loop) - Rebuild im Python-Loop.
#
# Erste Version: einzeiliger Text "NEOTRON PICO" in Gelb oben links,
# Rest schwarz. 60 FPS-Ziel, Rebuild ~30 ms -> gut genug.
#
# Als code.py auf CIRCUITPY. LED (GP25) blinkt 1x/s. Beenden: Strg+C.

import board
import rp2pio
import adafruit_pioasm
import digitalio
import time
import array
from font8x8 import FONT

timing_pio = """
    pull
    out pins, 14
    set x, 0
    out x, 14
period_loop:
    jmp x-- period_loop
"""
timing_prog = adafruit_pioasm.assemble(timing_pio)

# Takte pro Abschnitt
CY_FRONT = 16 * 6    # 96
CY_SYNC = 96 * 6     # 576
CY_BACK = 48 * 6     # 288
CY_VIS = 640 * 6     # 3840 (1 Wort = 6 Takte? NEIN: Pixel sind einzelne Woerter!)

# Fuer Textmodus: JEDER Pixel = eigenes Wort mit Loop-Zaehler 5 (6 Takte).
# Wortformat: bits 0-1 Sync, bits 2-13 Farbe, bits 14-31 Loop-Zaehler
def pix_word(color):
    # 1 Pixel = 6 Takte: pull+out+out+set = 4 Takte + (count+1) -> count = 1
    return (1 << 14) | color

BLACK = 0
def color_word(r, g, b):
    return (r << 2) | (g << 6) | (b << 10)

# Sync-Woerter (identisch zum verifizierten Farb-Test)
def timing_word(cycles_, hsync_low=False, vsync_low=False):
    b0 = 0 if hsync_low else 1
    b1 = 0 if vsync_low else 1
    # Abschnitt = 4 Takte + (count+1) -> count = Takte - 5
    return (((cycles_ - 5) << 14) | b0 | (b1 << 1)) & 0xFFFFFFFF

W_FRONT = timing_word(CY_FRONT)
W_SYNC = timing_word(CY_SYNC, hsync_low=True)
W_BACK = timing_word(CY_BACK)

TEXT = "NEOTRON PICO"
TEXT_ROW = 2           # Textblock ab Zeile 2 (16 Pixel von oben)
TEXT_COL = 8           # ab Spalte 8 (64 Pixel von links)
FG = color_word(15, 15, 0)   # Gelb
BG = BLACK

def build_frame():
    buf = array.array("I")
    # 30 Textzeilen a 8 Pixelzeilen = 240 Zeilen Textbereich,
    # Rest (240 Zeilen) schwarz.
    text_rows = len(TEXT) > 0
    for vline in range(480):
        in_text_row = (TEXT_ROW * 8) <= vline < (TEXT_ROW + 1) * 8 if text_rows else False
        buf.append(W_FRONT)
        buf.append(W_SYNC)
        buf.append(W_BACK)
        if in_text_row:
            font_row = FONT[ord("N")] if False else None
            # Zeichen bestimmen: Spalte = vline-Offset innerhalb des Zeichens
            frow = vline - TEXT_ROW * 8
            # Text: nur die Zeichen der Zeile zeichnen, Rest schwarz
            for col in range(80):
                ch_col = col - TEXT_COL
                if 0 <= ch_col < len(TEXT):
                    glyph = FONT[ord(TEXT[ch_col])]
                    row_bits = glyph[frow]
                    # 8 Pixel a 6 Takte: Wort mit Loop-Zaehler 1 = 6 Takte
                    for px in range(8):
                        on = (row_bits >> px) & 1
                        buf.append(pix_word(FG if on else BG))
                else:
                    for _ in range(8):
                        buf.append(pix_word(BG))
        else:
            # volle 640 Pixel schwarz - als EIN Wort (3840 Takte)
            buf.append(timing_word(CY_VIS))
    return buf

print("Baue Frame-Buffer...")
frame = build_frame()
print("Woerter im Frame:", len(frame), "=", len(frame) * 4, "Bytes")

sm = rp2pio.StateMachine(
    timing_prog,
    frequency=150_000_000,
    first_out_pin=board.GP0,
    out_pin_count=14,
    initial_out_pin_state=0b11,
    initial_out_pin_direction=0x3FFF,
    auto_pull=False,
)

# GP21 nOUTPUT_EN + LED
try:
    noutput_en = digitalio.DigitalInOut(board.GP21)
    noutput_en.direction = digitalio.Direction.OUTPUT
    noutput_en.value = True
    print("GP21 nOUTPUT_EN = HIGH")
except Exception as e:
    print("WARN: GP21:", e)

led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT
led.value = True

print("Starte Textausgabe im DMA-Loop (statisch)...")
sm.background_write(loop=frame)
n = 0
try:
    while True:
        pass  # Frame laeuft im DMA-Loop endlos
        n += 1
        if n % 60 == 0:              # ~1 s
            led.value = not led.value
            print("frame", n)
except KeyboardInterrupt:
    led.value = False
    sm.deinit()
    print("Gestoppt.")
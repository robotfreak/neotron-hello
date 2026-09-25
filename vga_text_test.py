# vga_text_test.py - VGA Textmodus: "NEOTRON PICO" in 8x8-Font (RLE, DMA-Loop)
#
# Basiert auf verifizierter DMA-Architektur (vga_dma_color_test.py):
# EINE PIO-SM @ 150 MHz, GP0..GP13, 32-Bit-Woerter:
#   bit0-1 = HSYNC/VSYNC (1=idle HIGH, 0=Puls LOW), bit2-13 = RGB 4-4-4,
#   bit14-31 = Loop-Zaehler. Abschnittsdauer = 4 + (count+1) Takte.
#
# KRITISCH (Fehler der 1. Version, gefixt): Ein Wort pro PIXEL braucht
# ~25M Woerter/s -> CircuitPython-DMA kommt nicht hinterher -> FIFO-Underrun
# -> gestreckte Zeilen -> Monitor: "Input timing not supported".
# FIX: Run-Length-Encoding! Gleiche Farbe hintereinander = 1 Wort mit
# angepasstem Loop-Zaehler (N Pixel = N*6 Takte, count = N*6 - 5).
# Textzeile: ~60 Woerter statt 643 -> DMA-Last trivial.
#
# Font: font8x8.py (Public Domain), 8x8 Pixel, Raster 80x30.
# Zeile: 96+576+288+3840 = 4800 Takte = 31,25 kHz; 525 Zeilen = 59,5 Hz.
#
# Als code.py auf CIRCUITPY (ZUSAMMEN mit font8x8.py!). Beenden: Strg+C.

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

CY_FRONT = 16 * 6    # 96
CY_SYNC = 96 * 6     # 576
CY_BACK = 48 * 6     # 288
CY_VIS = 640 * 6     # 3840


def timing_word(cycles_, hsync_low=False, vsync_low=False):
    b0 = 0 if hsync_low else 1
    b1 = 0 if vsync_low else 1
    # Abschnitt = 4 Takte (pull,out,set,out) + (count+1) -> count = Takte-5
    return (((cycles_ - 5) << 14) | b0 | (b1 << 1)) & 0xFFFFFFFF


def color_word(r, g, b):
    return (r << 2) | (g << 6) | (b << 10)


W_FRONT = timing_word(CY_FRONT)
W_SYNC = timing_word(CY_SYNC, hsync_low=True)
W_BACK = timing_word(CY_BACK)
W_BLACK_VIS = timing_word(CY_VIS)   # 640 schwarze Pixel in EINEM Wort

TEXT = "NEOTRON PICO"
TEXT_ROW = 2    # oberste Textpixelzeile (Pixelzeile 16)
TEXT_COL = 8    # Pixelspalte 64
FG = color_word(15, 15, 0)   # Gelb
BG = 0


def rle_words(colors):
    """640 Pixel-Farben -> RLE-Woerter (Lauf gleicher Farbe = 1 Wort)."""
    out = []
    i = 0
    n = len(colors)
    while i < n:
        j = i
        while j < n and colors[j] == colors[i]:
            j += 1
        cycles = (j - i) * 6
        out.append((((cycles - 5) << 14) | colors[i]) & 0xFFFFFFFF)
        i = j
    return out


def build_frame():
    buf = array.array("I")
    for vline in range(480):
        buf.append(W_FRONT)
        buf.append(W_SYNC)
        buf.append(W_BACK)
        if TEXT_ROW * 8 <= vline < (TEXT_ROW + 1) * 8:
            frow = vline - TEXT_ROW * 8
            row_colors = [BG] * 640
            for ch_idx, ch in enumerate(TEXT):
                bits = FONT[ord(ch)][frow]
                base = (TEXT_COL + ch_idx) * 8
                for px in range(8):
                    col = base + px
                    if 0 <= col < 640:
                        row_colors[col] = FG if ((bits >> px) & 1) else BG
            buf.extend(rle_words(row_colors))
        else:
            buf.append(W_BLACK_VIS)
    for _ in range(10):   # Front Porch
        buf.append(W_FRONT); buf.append(W_SYNC); buf.append(W_BLACK_VIS)
    for _ in range(2):    # VSYNC (2 Zeilen low)
        buf.append(W_FRONT); buf.append(W_SYNC); buf.append(timing_word(CY_VIS, vsync_low=True))
    for _ in range(33):   # Back Porch
        buf.append(W_FRONT); buf.append(W_SYNC); buf.append(W_BLACK_VIS)
    return buf

print("Baue Frame-Buffer (RLE)...")
frame = build_frame()
print("Woerter:", len(frame), "=", len(frame) * 4, "Bytes")

sm = rp2pio.StateMachine(
    timing_prog,
    frequency=150_000_000,
    first_out_pin=board.GP0,
    out_pin_count=14,
    initial_out_pin_state=0b11,
    initial_out_pin_direction=0x3FFF,
    auto_pull=False,
)

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

sm.background_write(loop=frame)
print("Textmodus im DMA-Endlosloop aktiv (statisch, 59,5 Hz).")

n = 0
try:
    while True:
        time.sleep(1)
        n += 1
        led.value = not led.value
        print("alive", n)
except KeyboardInterrupt:
    led.value = False
    sm.deinit()
    print("Gestoppt.")
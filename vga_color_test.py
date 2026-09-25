# vga_color_test.py - VGA Farbtest fuer Neotron Pico (Pico 2 / CircuitPython 10)
#
# Schritte:
#   1. Monitor zeigt schwarzes Bild (Sync laeuft) - dann Farbrausch-Test:
#      Vollbild ROT -> GRUEN -> BLAU -> WEISS, je 3 s
#   2. Helligkeitsrampe: Graustufen 0..15, je 1 s (testet R-2R-Stufen)
#
# Belegung (Neotron-Pico-Schematic):
#   GP0=HSYNC GP1=VSYNC (PIO, wie im Sync-Test)
#   GP2-5=Rot, GP6-9=Gruen, GP10-13=Blau (je 4 Bit R-2R -> 4096 Farben)
#
# Als code.py auf CIRCUITPY. Beenden: Strg+C.

import board
import rp2pio
import adafruit_pioasm
import digitalio
import time

# --- Sync (identisch zum getesteten Sync-Test) ---
hsync_pio = """
    set pins, 0   [31]
    nop           [31]
    nop           [31]
    set pins, 1   [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
"""

vsync_pio = """
    set pins, 0
    nop
    set pins, 1
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [9]
"""

hsync_prog = adafruit_pioasm.assemble(hsync_pio)
vsync_prog = adafruit_pioasm.assemble(vsync_pio)

freq_pixel = 25_175_000
sm_h = rp2pio.StateMachine(hsync_prog, frequency=freq_pixel,
                           first_set_pin=board.GP0, set_pin_count=1)
sm_v = rp2pio.StateMachine(vsync_prog, frequency=freq_pixel // 800,
                           first_set_pin=board.GP1, set_pin_count=1)
print("Sync aktiv (640x480@60).")

# --- 12 Farb-Pins als digitale Ausgaenge ---
color_pins = []
for gp in range(2, 14):  # GP2..GP13
    p = digitalio.DigitalInOut(getattr(board, "GP%d" % gp))
    p.direction = digitalio.Direction.OUTPUT
    color_pins.append(p)
# Reihenfolge in color_pins:
#   0-3: Rot  (GP2..GP5)   -> Bit0..Bit3
#   4-7: Gruen (GP6..GP9)  -> Bit0..Bit3
#   8-11: Blau (GP10..13)  -> Bit0..Bit3


def set_rgb(r, g, b):
    """4-Bit-Werte (0-15) je Kanal setzen. Bit0 = GP2/GP6/GP10."""
    bits = []
    for c in (r, g, b):
        for i in range(4):
            bits.append((c >> i) & 1)
    for pin, v in zip(color_pins, bits):
        pin.value = v


print("VGA Farbtest - Vollbildfarben, je 3 s")
set_rgb(0, 0, 0)
time.sleep(2)

for name, r, g, b in (("ROT", 15, 0, 0), ("GRUEN", 0, 15, 0),
                      ("BLAU", 0, 0, 15), ("WEISS", 15, 15, 15)):
    print("Farbe:", name)
    set_rgb(r, g, b)
    time.sleep(3)

print("Graustufen-Rampe 0..15, je 1 s (R-2R-Stufen testen)")
for level in range(16):
    print("Stufe", level)
    set_rgb(level, level, level)
    time.sleep(1)

print("Endlos-Dauerschleife: Farben wiederholen. Strg+C beendet.")
while True:
    for name, r, g, b in (("ROT", 15, 0, 0), ("GRUEN", 0, 15, 0),
                          ("BLAU", 0, 0, 15), ("WEISS", 15, 15, 15)):
        set_rgb(r, g, b)
        time.sleep(2)
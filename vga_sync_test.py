# vga_sync_test.py - VGA Sync-Test fuer Neotron Pico (Pico 2 / CircuitPython 10)
#
# Monitor sollte "Signal: 640x480@60Hz" anzeigen (schwarzes Bild).
# Benoetigt adafruit_pioasm in lib/ auf CIRCUITPY (Standard-Bundle).
#
# Belegung (Neotron-Pico-Schematic): GP0=HSYNC, GP1=VSYNC
#   GP2-5=Rot, GP6-9=Gruen, GP10-13=Blau (je 4 Bit R-2R)
# Timing 640x480@60: 25.175 MHz Pixel, 800 Takte/Zeile, 525 Zeilen/Bild,
#   HSYNC 96 low, VSYNC 2 low, beides negativ polarisiert.
#
# Als code.py auf CIRCUITPY kopieren. Beenden: Strg+C.

import board
import rp2pio
import adafruit_pioasm
import time

# --- HSYNC: 96 low + 704 high = 800 Takte/Zeile (exakt) ---
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

# --- VSYNC: 2 low + 523 high = 525 Zeilen (1 Takt = 1 Zeile) ---
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
print("HSYNC:", len(hsync_prog), "Instr | VSYNC:", len(vsync_prog), "Instr")

freq_pixel = 25_175_000

sm_h = rp2pio.StateMachine(
    hsync_prog,
    frequency=freq_pixel,
    first_set_pin=board.GP0,
    set_pin_count=1,
)
print("HSYNC @", sm_h.frequency, "Hz (Zeilen:", sm_h.frequency // 800, "Hz)")

sm_v = rp2pio.StateMachine(
    vsync_prog,
    frequency=freq_pixel // 800,
    first_set_pin=board.GP1,
    set_pin_count=1,
)
print("VSYNC @", sm_v.frequency, "Hz")

print("Sync aktiv -> Monitor pruefen! (Strg+C beendet)")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    sm_h.deinit()
    sm_v.deinit()
    print("Gestoppt.")
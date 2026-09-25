# vga_static_test.py - Diagnose: Sync + EINE statische Farbe, sonst NICHTS.
#
# Ziel: Feststellen, ob statische RGB-Level allein das Sync-Problem ausloesen.
#   - Wenn ROT DAUERHAFT stabil -> Problem liegt im Farbwechsel-/Rampe-Code
#   - Wenn ROT auch hier flackert -> Monitor-/Timing-Thema (Polaritaet/Frequenz)
#
# Serial zeigt alle 2 s "alive N" - damit koennen wir korrelieren,
# ob das Blitzen mit dem Code-Zyklus oder dem Monitor zusammenhaengt.
#
# Als code.py auf CIRCUITPY. Beenden: Strg+C.

import board
import rp2pio
import adafruit_pioasm
import digitalio
import time

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

# Nur Rot-Kanal: GP2..GP5
red_pins = []
for gp in range(2, 6):
    p = digitalio.DigitalInOut(getattr(board, "GP%d" % gp))
    p.direction = digitalio.Direction.OUTPUT
    red_pins.append(p)

for pin in red_pins:
    pin.value = True   # volle Rot-Stufe (15)

print("ROT statisch gesetzt - jetzt darf nichts mehr laufen.")
print("Beobachte den Monitor: stabil = RGB-Wechsel war das Problem.")

n = 0
try:
    while True:
        time.sleep(2)
        n += 1
        print("alive", n)
except KeyboardInterrupt:
    for pin in red_pins:
        pin.value = False
    sm_h.deinit()
    sm_v.deinit()
    print("Gestoppt.")
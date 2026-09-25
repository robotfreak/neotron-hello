# vga_static_test.py - Diagnose: Sync + EINE statische Farbe + LED-Heartbeat
#
# LED am Pico 2 blinkt 1x/s = Code laeuft definitiv (kein Serial noetig!)
#   LED AN dauerhaft = Crash/Reload -> Problem im Code
#   LED blinkt, Monitor schwarz -> RGB-Pfad-Thema (Buffer/Pins)
#
# Belegung (Neotron-Pico-Schematic + BIOS):
#   GP0=HSYNC GP1=VSYNC (PIO, negativ, 640x480@60 wie Neotron-BIOS)
#   GP2-5=Rot, GP6-9=Gruen, GP10-13=Blau (4 Bit R-2R je Kanal)
#   GP21=nOUTPUT_EN (HIGH = PCB-Ausgangspuffer aktiv, aus BIOS main.rs)
#   LED = GP25
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
    nop           [31]
    nop           [31]
    nop           [31]
    nop           [9]
"""

hsync_prog = adafruit_pioasm.assemble(hsync_pio)
vsync_prog = adafruit_pioasm.assemble(vsync_prog_pio := vsync_pio)

freq_pixel = 25_175_000
sm_h = rp2pio.StateMachine(hsync_prog, frequency=freq_pixel,
                           first_set_pin=board.GP0, set_pin_count=1)
sm_v = rp2pio.StateMachine(vsync_prog, frequency=freq_pixel // 800,
                           first_set_pin=board.GP1, set_pin_count=1)
print("Sync aktiv (640x480@60).")

# --- GP21 nOUTPUT_EN = HIGH (PCB-Ausgangspuffer aktiv, aus BIOS) ---
try:
    noutput_en = digitalio.DigitalInOut(board.GP21)
    noutput_en.direction = digitalio.Direction.OUTPUT
    noutput_en.value = True
    print("GP21 nOUTPUT_EN = HIGH (Buffer aktiv)")
except Exception as e:
    print("WARN: GP21 nicht setzbar:", e)

# --- LED als Lebenszeichen ---
led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT
led.value = True  # AN dauerhaft zuerst

# --- Nur Rot-Kanal: GP2..GP5 ---
red_pins = []
for gp in range(2, 6):
    p = digitalio.DigitalInOut(getattr(board, "GP%d" % gp))
    p.direction = digitalio.Direction.OUTPUT
    red_pins.append(p)

for pin in red_pins:
    pin.value = True   # volle Rot-Stufe (15)

print("ROT statisch gesetzt.")

n = 0
try:
    while True:
        time.sleep(1)
        n += 1
        led.value = not led.value  # Blinken = Code lebt
        print("alive", n)
except KeyboardInterrupt:
    for pin in red_pins:
        pin.value = False
    led.value = False
    sm_h.deinit()
    sm_v.deinit()
    print("Gestoppt.")
# vga_phase_test.py - VGA mit PHASENGEKOPPELTEN Syncs (wie Neotron-BIOS)
#
# BIOS-artig: HSYNC-SM sendet IRQ am Zeilenanfang; VSYNC-SM wartet darauf.
# Beide SMs laufen mit 25.175 MHz -> starre Phasenkopplung, VSYNC am Zeilenanfang.
# RGB-Pins (GP2-5 = ROT voll) digitalio-statisch, GP21 = Buffer-Enable.
#
# Als code.py auf CIRCUITPY. LED (GP25) blinkt 1x/s = Code lebt.

import board
import rp2pio
import adafruit_pioasm
import digitalio
import time

# HSYNC: 800 Takte/Zeile, 96 low + 704 high. IRQ4 = Zeilenanfang-Marke,
# wird nach der Low-Phase wieder gecleared (Handshake mit VSYNC-SM).
hsync_pio = """    irq 4         [31]
    set pins, 0   [31]
    set pins, 0   [31]
    irq clear 4   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
    set pins, 1   [31]
"""

# VSYNC: wartet auf IRQ4 (Zeilenanfang), 2 Zeilen low, dann 523 high.
# 1 Takt pro Zeile, getaktet durch den HSYNC-IRQ -> exakt phasengekoppelt.
vsync_pio = """    wait 1 irq 4
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
    nop           [8]
"""

hsync_prog = adafruit_pioasm.assemble(hsync_pio)
vsync_prog = adafruit_pioasm.assemble(vsync_pio)

freq_pixel = 25_175_000
sm_h = rp2pio.StateMachine(hsync_prog, frequency=freq_pixel,
                           first_set_pin=board.GP0, set_pin_count=1)
sm_v = rp2pio.StateMachine(vsync_prog, frequency=freq_pixel,
                           first_set_pin=board.GP1, set_pin_count=1)
print("Sync PHASENGEKOPPELT aktiv (640x480@60, IRQ-Handshake).")

# GP21 nOUTPUT_EN = HIGH (wie BIOS)
try:
    noutput_en = digitalio.DigitalInOut(board.GP21)
    noutput_en.direction = digitalio.Direction.OUTPUT
    noutput_en.value = True
    print("GP21 nOUTPUT_EN = HIGH")
except Exception as e:
    print("WARN: GP21:", e)

# LED-Lebenszeichen
led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT
led.value = True

# Statisches ROT (GP2..GP5 alle HIGH = Stufe 15)
red_pins = []
for gp in range(2, 6):
    p = digitalio.DigitalInOut(getattr(board, "GP%d" % gp))
    p.direction = digitalio.Direction.OUTPUT
    red_pins.append(p)
for pin in red_pins:
    pin.value = True

print("ROT statisch, Sync gekoppelt.")

n = 0
try:
    while True:
        time.sleep(1)
        n += 1
        led.value = not led.value
        print("alive", n)
except KeyboardInterrupt:
    for pin in red_pins:
        pin.value = False
    led.value = False
    sm_h.deinit()
    sm_v.deinit()
    print("Gestoppt.")
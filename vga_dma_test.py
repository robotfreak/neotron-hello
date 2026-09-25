# vga_dma_test.py - VGA 640x480@60 fuer Neotron Pico, BIOS-Architektur
#
# EINE PIO-StateMachine erzeugt HSYNC (GP0) + VSYNC (GP1) aus einem
# DMA-Ringpuffer mit Timing-Woertern (wie Neotron-BIOS vga/mod.rs):
#   Wortformat: bit0=HSYNC (0=aktiv/low), bit1=VSYNC (0=aktiv/low),
#               bits 2-15 = Loop-Zaehler (Periodendauer in PIO-Takten)
#   Programm: pull; out pins,2; out x,14; loop: jmp x-- (Periodendauer)
#   Phasenkohaerent durch Konstruktion: EIN Programm, EINE SM, DMA-Endlosloop.
#
# Pixeltakt-aequivalent: SM laeuft 25,2 MHz (150 MHz CPU / 6), BIOS identisch.
# Zeile: 16+96+48+640 Pixel = 800 -> 4800 Takte. Bild: 525 Zeilen -> 59,5 Hz.
# RGB: GP2-5 statisch ROT (digitalio), GP21 = nOUTPUT_EN (Buffer-Enable).
#
# Als code.py auf CIRCUITPY. LED (GP25) blinkt 1x/s. Beenden: Strg+C.

import board
import rp2pio
import adafruit_pioasm
import digitalio
import time
import array

# --- Timing-Programm: 1 Wort = 1 Periodenabschnitt mit H/V-Pegeln ---
timing_pio = """
    pull
    out pins, 2
    out x, 14
period_loop:
    jmp x-- period_loop
"""
timing_prog = adafruit_pioasm.assemble(timing_pio)

# --- Timing-Woerter aufbauen ---
# Takte pro Abschnitt (6 Takte/Pixel @ 150 MHz SM-Takt = 25,0 MHz effektiv):
T_FRONT = 16 * 6    # 96
T_SYNC = 96 * 6     # 576
T_BACK = 48 * 6     # 288
T_VIS = 640 * 6     # 3840
# Wort: (loop_count << 2) | bits. loop_count = Takte - 4 (pull+out pins+out x
# = 3 Takte, jmp x-- laeuft count+1 Takte -> 3 + count+1 = Takte -> count = Takte-4)
def word(cycles_, hsync_active, vsync_active):
    # NEGATIVE Polaritaet (BIOS 640x480: beide negativ):
    # aktiv = LOW. Idle = HIGH (1), Sync-Puls = LOW (0).
    h = 0 if hsync_active else 1
    v = 0 if vsync_active else 1
    return ((cycles_ - 4) << 2) | h | (v << 1)

def line(hsync_active, vsync_active):
    return array.array("H", [
        word(T_FRONT, False, vsync_active),
        word(T_SYNC, True, vsync_active),
        word(T_BACK, False, vsync_active),
        word(T_VIS, False, vsync_active),
    ])

timing = array.array("H")
timing.extend(line(False, False))    # 480 sichtbare Zeilen, VSYNC high
for _ in range(479):
    timing.extend(line(False, False))
for _ in range(10):                  # Front Porch
    timing.extend(line(False, False))
for _ in range(2):                   # VSYNC-Puls (2 Zeilen low)
    timing.extend(line(False, True))
for _ in range(33):                  # Back Porch
    timing.extend(line(False, False))
print("Timing-Woerter:", len(timing), "(Ziel 525*4 = 2100)")
assert len(timing) == 2100

freq_sm = 150_000_000  # CPU-Takt; 6 Takte pro Pixel -> 25,0 MHz Pixeltakt
sm = rp2pio.StateMachine(
    timing_prog,
    frequency=freq_sm,
    first_out_pin=board.GP0,
    out_pin_count=2,
    initial_out_pin_state=0b11,   # beide Syncs initial HIGH (idle)
    initial_out_pin_direction=0b11,
    auto_pull=True,
    out_shift_right=True,         # bit0 zuerst -> GP0 = HSYNC
    pull_threshold=16,
)
sm.background_write(loop=timing)
print("Sync-SM @", sm.frequency, "Hz mit DMA-Endlosloop (59,5 Hz, phasestabil).")

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

# Statisches ROT (GP2..GP5 = Stufe 15)
red_pins = []
for gp in range(2, 6):
    p = digitalio.DigitalInOut(getattr(board, "GP%d" % gp))
    p.direction = digitalio.Direction.OUTPUT
    red_pins.append(p)
for pin in red_pins:
    pin.value = True
print("ROT statisch gesetzt.")

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
    sm.deinit()
    print("Gestoppt.")
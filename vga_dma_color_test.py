# vga_dma_color_test.py - VGA 640x480@60 mit Farbe im sichtbaren Bereich
#
# BIOS-Architektur: EINE PIO-SM erzeugt HSYNC+VSYNC **und** die 12 RGB-Bits
# aus einem DMA-Ringpuffer. 1 Wort (32 Bit) = 1 Timing-Abschnitt:
#   bit0    = HSYNC (1=idle HIGH, 0=Puls LOW)
#   bit1    = VSYNC (1=idle HIGH, 0=Puls LOW)
#   bit2-5  = ROT  (GP2..GP5, 4 Bit)
#   bit6-9  = GRUEN (GP6..GP9)
#   bit10-13= BLAU (GP10..GP13)
#   bit14-27= Loop-Zaehler (Abschnittsdauer in PIO-Takten)
# Programm: pull; out pins,14; set x,0; out x,14; loop: jmp x--
# WICHTIG: Farbe NUR im sichtbaren Bereich (Porches schwarz) - Video-Glied
# ist AC-gekoppelt/geklemmt, Back-Porch definiert Schwarz-Niveau.
#
# Zeile: 96+576+288+3840 = 4800 Takte @ 150 MHz (6 Takte/Pixel -> 25,0 MHz)
# Frame: 480 sichtbar + 10 Front + 2 VSYNC + 33 Back = 525 Zeilen -> 59,5 Hz
#
# Als code.py auf CIRCUITPY. LED (GP25) blinkt. Beenden: Strg+C.

import board
import rp2pio
import adafruit_pioasm
import digitalio
import time
import array

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

RED = 0b1111 << 2      # GP2..GP5 alle HIGH
IDLE = 0b11            # HSYNC/VSYNC idle (HIGH)


def word(cycles_, hsync_low=False, vsync_low=False, color=0):
    b0 = 0 if hsync_low else 1
    b1 = 0 if vsync_low else 1
    # Abschnitt = pull+out+set+out (4) + (count+1) jmp-Takte -> count = Takte-5
    return (((cycles_ - 5) << 14) | b0 | (b1 << 1) | color) & 0xFFFFFFFF


def line(vsync_low=False, color=0):
    return [
        word(CY_FRONT, False, vsync_low, 0),
        word(CY_SYNC, True, vsync_low, 0),
        word(CY_BACK, False, vsync_low, 0),
        word(CY_VIS, False, vsync_low, color),
    ]


buf = array.array("I")
for _ in range(480):            # sichtbare Zeilen: ROT
    buf.extend(line(color=RED))
for _ in range(10):             # Front Porch
    buf.extend(line())
for _ in range(2):              # VSYNC-Puls
    buf.extend(line(vsync_low=True))
for _ in range(33):             # Back Porch
    buf.extend(line())
print("Timing-Woerter:", len(buf), "(Ziel 2100)")
assert len(buf) == 2100

sm = rp2pio.StateMachine(
    timing_prog,
    frequency=150_000_000,
    first_out_pin=board.GP0,
    out_pin_count=14,
    initial_out_pin_state=IDLE,      # Syncs HIGH, Farbe schwarz
    initial_out_pin_direction=0x3FFF,
    auto_pull=False,                  # explizites pull im Programm
)
sm.background_write(loop=buf)
print("Sync+Pixel-SM @", sm.frequency, "Hz, DMA-Loop phasestabil (59,5 Hz).")

# GP21 nOUTPUT_EN = HIGH (wie BIOS; betrifft Expander-CS, schadet nicht)
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

print("ROT im sichtbaren Bereich, Porches schwarz.")

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
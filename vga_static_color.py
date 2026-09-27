# vga_static_color.py - ISOLATION: exakt der color_test-Frame (bewiesen
# laufend) mit Stufen-Markern - der Unterschied zum kippenden static_v9:
# KEIN Doppel-Write (color_test schreibt EINMAL direkt).
import board
import rp2pio
import adafruit_pioasm
import digitalio
import time
import array

led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT

def blink(n, dt=0.12):
    for _ in range(n):
        led.value = True; time.sleep(dt)
        led.value = False; time.sleep(dt)

blink(3)
print("[1] Start")

timing_pio = """
    pull
    out pins, 14
    set x, 0
    out x, 14
period_loop:
    jmp x-- period_loop
"""
timing_prog = adafruit_pioasm.assemble(timing_pio)

print("[2] PIO-Asm ok")

CY_FRONT = 16 * 6
CY_SYNC = 96 * 6
CY_BACK = 48 * 6
CY_VIS = 640 * 6
RED = 0b1111 << 2
IDLE = 0b11

def word(cycles_, hsync_low=False, vsync_low=False, color=0):
    b0 = 0 if hsync_low else 1
    b1 = 0 if vsync_low else 1
    return (((cycles_ - 5) << 14) | b0 | (b1 << 1) | color) & 0xFFFFFFFF

def line(vsync_low=False, color=0):
    return [
        word(CY_FRONT, False, vsync_low, 0),
        word(CY_SYNC, True, vsync_low, 0),
        word(CY_BACK, False, vsync_low, 0),
        word(CY_VIS, False, vsync_low, color),
    ]

buf = array.array("I")
for _ in range(480):
    buf.extend(line(color=RED))
for _ in range(10):
    buf.extend(line())
for _ in range(2):
    buf.extend(line(vsync_low=True))
for _ in range(33):
    buf.extend(line())
print("[3] Frame:", len(buf), "Woerter")

sm = rp2pio.StateMachine(
    timing_prog,
    frequency=150_000_000,
    first_out_pin=board.GP0,
    out_pin_count=14,
    initial_out_pin_state=IDLE,
    initial_out_pin_direction=0x3FFF,
    auto_pull=False,
)
print("[4] SM ok")

sm.background_write(loop=buf)   # EIN Write, kein Dummy!
print("[5] geschrieben - Monitor ROT?")

try:
    noutput_en = digitalio.DigitalInOut(board.GP21)
    noutput_en.direction = digitalio.Direction.OUTPUT
    noutput_en.value = True
    print("[6] GP21 HIGH")
except Exception as e:
    print("WARN GP21:", e)

n = 0
while True:
    time.sleep(1)
    n += 1
    led.value = not led.value
    print("alive", n)

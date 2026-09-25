# vga_isolate_test.py - ISOLIERUNGSTEST: 4-Woerter-Struktur (wie Farb-Test)
# Zeilen 0-7 = ROT, Rest schwarz. Wenn DAS synced, ist die DMA-Rate das Problem.
# Wenn nicht, liegt es woanders. LED-Phasen wie Text-Test.
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
        led.value = True; time.sleep(dt); led.value = False; time.sleep(dt)
blink(3)
print("Isolationstest...")

timing_pio = """
    pull
    out pins, 14
    set x, 0
    out x, 14
period_loop:
    jmp x-- period_loop
"""
timing_prog = adafruit_pioasm.assemble(timing_pio)

def tw(c_, hl=False, vl=False):
    b0 = 0 if hl else 1
    b1 = 0 if vl else 1
    return (((c_ - 5) << 14) | b0 | (b1 << 1)) & 0xFFFFFFFF

CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840
W_FRONT = tw(CY_FRONT)
W_SYNC = tw(CY_SYNC, True)
W_BACK = tw(CY_BACK)
RED = (15 << 2)
W_VIS_RED = tw(CY_VIS) | RED
W_VIS_BLACK = tw(CY_VIS)

frame = array.array("I")
for vline in range(480):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK)
    frame.append(W_VIS_RED if vline < 8 else W_VIS_BLACK)
for _ in range(10):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(W_VIS_BLACK)
for _ in range(2):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(tw(CY_VIS, vl=True))
for _ in range(33):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(W_VIS_BLACK)
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
noutput_en = digitalio.DigitalInOut(board.GP21)
noutput_en.direction = digitalio.Direction.OUTPUT
noutput_en.value = True
print("GP21 nOUTPUT_EN = HIGH")
sm.background_write(loop=frame)
print("Isolationstest aktiv.")
n = 0
while True:
    time.sleep(1)
    n += 1
    led.value = not led.value
    print("alive", n)

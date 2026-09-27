# putloop_chunk: Der KOMPLETTE Frame als EIN put()-Aufruf
# (der CircuitPython-aehnlichste Feed, kein DMA)
from machine import Pin, freq
import rp2
import time
from array import array
freq(150_000_000)
Pin(21, Pin.OUT).value(1)

@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH,) * 14,
             out_shiftdir=rp2.PIO.SHIFT_RIGHT,
             autopull=False, pull_thresh=32)
def timing_prog():
    pull()
    out(pins, 14)
    set(x, 0)
    out(x, 14)
    label("period_loop")
    jmp(x_dec, "period_loop")

def word(cycles, hsync_low=False, vsync_low=False, color=0):
    b0 = 0 if hsync_low else 1
    b1 = 0 if vsync_low else 1
    return (((cycles - 5) << 14) | color | b0 | (b1 << 1)) & 0xFFFFFFFF

CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840
RED = 0b1111 << 2
W_FRONT = word(CY_FRONT)
W_SYNC = word(CY_SYNC, hsync_low=True)
W_BACK = word(CY_BACK)
W_VIS_RED = word(CY_VIS, color=RED)
W_BLANK = word(CY_VIS)

frame = array("I", [0] * (525 * 4))
i = 0
for _ in range(480):
    frame.extend((W_FRONT, W_SYNC, W_BACK, W_VIS_RED))
for _ in range(10):
    frame.extend((W_FRONT, W_SYNC, W_BACK, W_BLANK))
for _ in range(2):
    frame.extend((word(CY_FRONT, vsync_low=True),
                  word(CY_SYNC, True, True),
                  word(CY_BACK, vsync_low=True),
                  word(CY_VIS, vsync_low=True)))
for _ in range(6):
    frame.extend((W_FRONT, W_SYNC, W_BACK, W_BLANK))
# VORAB auffuellen? Nein: Der Frame ist 525*4 = 2100 - der Chunk-
# Weg: put(frame) schiebt ALLE - der PIO verbraucht je Wort 8 us:
# 2100 Wörter = 16.8 ms - der put blockt bis der FIFO Platz hat
# (der PIO verbraucht live) - DAS ist ein SYNCHRONER Feed-Loop.
frame = array("I", [])
for _ in range(480):
    frame.extend((W_FRONT, W_SYNC, W_BACK, W_VIS_RED))
for _ in range(10):
    frame.extend((W_FRONT, W_SYNC, W_BACK, W_BLANK))
for _ in range(2):
    frame.extend((word(CY_FRONT, vsync_low=True),
                  word(CY_SYNC, True, True),
                  word(CY_BACK, vsync_low=True),
                  word(CY_VIS, vsync_low=True)))
for _ in range(6):
    frame.extend((W_FRONT, W_SYNC, W_BACK, W_BLANK))
print("Frame:", len(frame), "Woerter")

sm = rp2.StateMachine(0, timing_prog, freq=150_000_000, out_base=0)
sm.active(1)
print("SM aktiv - Chunk-put (kompletter Frame je put)")

led = Pin(25, Pin.OUT)
n = 0
try:
    while True:
        sm.put(frame)   # der KOMPLETTE Frame auf einmal
        led.toggle()
        n += 1
        if n % 30 == 0:
            print("Frames:", n)
except KeyboardInterrupt:
    print("Frames:", n)


from machine import Pin, freq
import rp2
freq(150_000_000)
Pin(0, Pin.OUT); Pin(1, Pin.OUT)
Pin(21, Pin.OUT).value(1)

@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH),
             out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def tp():
    pull()
    out(pins, 2)
    out(x, 30)
    label("wait")
    jmp(x_dec, "wait")
    pull()

sm = rp2.StateMachine(0, tp, freq=150_000_000, out_base=0)
sm.active(1)
# Ein paar Zeilen-Woerter manuell schieben (ohne DMA):
import uarray as array
W = (96 << 2) | 3          # Front (HSYNC/VSYNC HIGH, 96 Takte)
S = (576 << 2) | 1         # Sync (HSYNC LOW)
B = (288 << 2) | 3         # Back
V = (3840 << 2) | 3        # Visible
while True:
    for _ in range(2): sm.put(S); sm.put(B); sm.put(W)   # vereinfachte Zeile

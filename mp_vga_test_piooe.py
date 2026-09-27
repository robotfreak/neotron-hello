# OE-BEWEIS: Der PIO treibt GP0 (out-Zug 1/0/1), der Output-Enable
# (Pad-Treiber) via SIO_GPIO_OE (0xD0000030, bit0 = GP0) lesen
from machine import mem32, freq
import rp2
import time
freq(150_000_000)

@rp2.asm_pio(out_init=rp2.PIO.OUT_HIGH, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def out0_prog():
    pull()
    out(pins, 1)
    pull()
    out(pins, 1)

sm = rp2.StateMachine(0, out0_prog, freq=150_000_000, out_base=0)
sm.active(1)
print("GP0: put(1) -> HIGH...")
sm.put(1)
time.sleep(0.5)
oe1 = (mem32[0xD0000030] >> 0) & 1
in1 = (mem32[0xD0000004] >> 0) & 1
print("GP0 OE:", oe1, "IN:", in1, "(erwartet OE=1, IN=1)")
sm.put(0)
time.sleep(0.5)
oe2 = (mem32[0xD0000030] >> 0) & 1
in2 = (mem32[0xD0000004] >> 0) & 1
print("GP0 OE:", oe2, "IN:", in2, "(erwartet OE=1, IN=0)")
print("ERGEBNIS: OE=1 heisst der Pad-Treiber ist aktiv (der Monitor muesste das Signal sehen)")
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

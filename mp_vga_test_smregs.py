# PIO-SM-REGISTER-STATUS: Der komplette SM0-Register-Dump
# (PIO0 = 0x50200000, je SM: CLKDIV 0xC8, EXECCTRL 0xCC,
# SHIFTCTRL 0xD0, ADDR 0xD4, INSTR 0xD8, PINCTRL 0xDC)
from machine import mem32, freq
import rp2
import time
freq(150_000_000)

@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH) + (rp2.PIO.OUT_LOW,) * 12,
             out_shiftdir=rp2.PIO.SHIFT_RIGHT,
             autopull=False, pull_thresh=32)
def timing_prog():
    pull()
    out(pins, 14)
    set(x, 0)
    out(x, 14)
    label("period_loop")
    jmp(x_dec, "period_loop")

sm = rp2.StateMachine(0, timing_prog, freq=150_000_000, out_base=0)
sm.active(1)
print("SM aktiv - put 4 Woerter...")
for w in (96, 576, 288, 3840):
    sm.put(((w - 5) << 14) | 3 | (0xFFF << 2))

time.sleep(0.2)
base = 0x50200000
def r(off): return mem32[base + off]
print("PIO0-SM0-Register:")
print("  CLKDIV   (0xC8): 0x%08X  (INT=%d FRAC=%d -> Teiler %g)" % (
    r(0xC8), (r(0xC8) >> 16) & 0xFFFF, (r(0xC8) >> 8) & 0xFF,
    ((r(0xC8) >> 16) & 0xFFFF) + ((r(0xC8) >> 8) & 0xFF) / 256.0))
print("  EXECCTRL (0xCC): 0x%08X" % r(0xCC))
print("  SHIFTCTRL(0xD0): 0x%08X" % r(0xD0))
print("  PINCTRL  (0xDC): 0x%08X" % r(0xDC))
print("  INSTR    (0xD8): 0x%04X" % (r(0xD8) & 0xFFFF))
print("  ADDR     (0xD4): %d" % (r(0xD4) & 0x1F))
print("  FDEBUG:  0x%08X" % r(0x8))
print("  FSTAT:   0x%08X" % r(0x0C))
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

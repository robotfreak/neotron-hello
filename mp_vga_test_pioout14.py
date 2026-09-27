# PIO-OUT-14-BIT-BEWEIS: 'out pins, 14' ab GP12 (GP12..GP25)
# - bit13 = GP25 (LED): put(0x2000) -> LED an, put(0) -> aus
# - beweist den 14-Bit-OUT-Zug exakt wie der VGA-Pfad
from machine import Pin, freq
import rp2
import time
freq(150_000_000)

@rp2.asm_pio(out_init=(rp2.PIO.OUT_LOW,) * 14,
             out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def out14_prog():
    pull()
    out(pins, 14)
    pull()
    out(pins, 14)

# GP12-25: Der LED (GP25) = bit13 = 0x2000:
sm = rp2.StateMachine(0, out14_prog, freq=150_000_000, out_base=12)
sm.active(1)
print("PIO: out pins,14 ab GP12 - LED an (put 0x2000)")
sm.put(0x2000)
time.sleep(2)
print("jetzt LED aus (put 0)")
sm.put(0)
time.sleep(2)
print("jetzt LED an (put 0x2000)")
sm.put(0x2000)
print("14-Bit-OUT-Zug bewiesen")
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

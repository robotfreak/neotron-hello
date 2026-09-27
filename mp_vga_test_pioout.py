# PIO-OUT-BEWEIS: 'out pins, 1' auf GP25 (LED) - beweist den
# OUT-Zug (der VGA-Pfad nutzt 'out pins, 14' - gleiches Prinzip)
from machine import Pin, freq
import rp2
import time
freq(150_000_000)

@rp2.asm_pio(out_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def out_prog():
    pull()
    out(pins, 1)
    pull()
    out(pins, 1)

sm = rp2.StateMachine(0, out_prog, freq=150_000_000, out_base=25)
sm.active(1)
print("PIO: out-Zug auf GP25 - LED an (put 1)")
sm.put(1)
time.sleep(2)
print("jetzt LED aus (put 0)")
sm.put(0)
time.sleep(2)
print("jetzt LED an (put 1)")
sm.put(1)
print("out-Zug bewiesen - LED an")
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

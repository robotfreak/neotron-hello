# GP0-BEWEIS 2.0: out-Zug auf GP0 + mem32-Lesung (kein Pin-Claim,
# kein Modus-Konflikt - SIO_GPIO_IN-Register 0xD0000004)
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
v1 = mem32[0xD0000004] & 1
print("GP0 gelesen:", v1, "(erwartet 1)")
print("GP0: put(0) -> LOW...")
sm.put(0)
time.sleep(0.5)
v2 = mem32[0xD0000004] & 1
print("GP0 gelesen:", v2, "(erwartet 0)")
sm.put(1)
time.sleep(0.5)
v3 = mem32[0xD0000004] & 1
print("GP0 gelesen:", v3, "(erwartet 1)")
print("ERGEBNIS:", "GP0-Treibung BEWIESEN" if (v1, v2, v3) == (1, 0, 1) else "GP0-Mux kaputt")
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

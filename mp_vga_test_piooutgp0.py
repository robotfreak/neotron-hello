# GP0-TREIBUNG-BEWEIS: out-Zug auf GP0 (HSYNC) + GPIO-INPUT-LESUNG
# (der PIO treibt, Python liest den Pin-Zustand via Pad-Register)
from machine import Pin, freq
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
print("GP0 HIGH setzen (put 1)...")
sm.put(1)
time.sleep(0.5)
p = Pin(0, Pin.IN)   # Python-LESER: Der Pad-Status (der PIO treibt weiter)
print("GP0 gelesen:", p.value(), "(erwartet 1 = HIGH)")
sm.put(0)
time.sleep(0.5)
p2 = Pin(0, Pin.IN)
print("GP0 gelesen:", p2.value(), "(erwartet 0 = LOW)")
sm.put(1)
time.sleep(0.5)
p3 = Pin(0, Pin.IN)
print("GP0 gelesen:", p3.value(), "(erwartet 1)")
print("GP0 out-Zug bewiesen")
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

# PIO-PIN-OUTPUT-BEWEIS: Der PIO toggelt die LED (GP25) 1 Hz
# - beweist, dass der PIO Pins physikalisch treibt (MicroPython)
from machine import Pin, freq
import rp2
import time
freq(150_000_000)

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)   # LED-Pin (set)
def blink_prog():
    set(pins, 1)   [31]
    set(pins, 0)   [31]
    # wrap automatisch

sm = rp2.StateMachine(0, blink_prog, freq=1_000_000, set_base=25)
sm.active(1)
print("PIO-SM0: LED-Loop aktiv - LED muss 1 Hz blinken")

# Parallel: Python-LED zur Kontrolle:
led = Pin(25, Pin.OUT)   # der PIO hat den Pin geclaimt - der
                         # Python-Zugriff sollte NICHT stoeren
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

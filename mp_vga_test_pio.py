# PIO-Isolation: 1 SM, 1 Wort via put(), LED bleibt.
from machine import Pin, freq
import rp2
import time
freq(150_000_000)
led = Pin(25, Pin.OUT)
hs = Pin(0, Pin.OUT)
vs = Pin(1, Pin.OUT)

@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH),
             out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def tp():
    pull()
    out(pins, 2)
    out(x, 30)
    label("wait")
    jmp(x_dec, "wait")

sm = rp2.StateMachine(0, tp, freq=150_000_000, out_base=0)
sm.active(1)
print("SM aktiv - 1 Wort schieben")
sm.put((96 - 3) << 2 | 3)   # 96-Takt-Puls, beide Pins HIGH
print("Wort geschoben - LED lebt weiter?")
n = 0
while True:
    led.toggle()
    print("alive", n)
    n += 1
    time.sleep(0.5)

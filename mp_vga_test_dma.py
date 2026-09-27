# DMA-Isolation: 1 Wort via DMA in den PIO-SM schieben.
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
print("SM aktiv - DMA schiebt 1 Wort")

import uarray as array
wort = array.array("I", [(96 - 3) << 2 | 3])
d = rp2.DMA()
c = d.pack_ctrl(inc_write=False, treq_sel=0)
d.config(read=wort, write=sm, count=1, ctrl=c, trigger=True)
print("DMA-Transfer gestartet")
import time
time.sleep(1)
print("1s spaeter - DMA.active():", d.active())
print("LED lebt?")
n = 0
while True:
    led.toggle()
    print("alive", n)
    n += 1
    time.sleep(0.5)

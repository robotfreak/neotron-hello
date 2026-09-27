# MINIMAL-TEST: GPIO-Toggle (kein PIO, kein DMA)
from machine import Pin, freq
import time
freq(150_000_000)
led = Pin(25, Pin.OUT)
hs = Pin(0, Pin.OUT)
vs = Pin(1, Pin.OUT)
Pin(21, Pin.OUT).value(1)   # GP21 = nOUTPUT_EN (VGA-Treiber-Enable!)
print("Toggle-Loop laeuft - 10 Sekunden")
t0 = time.ticks_ms()
n = 0
while time.ticks_diff(time.ticks_ms(), t0) < 10000:
    hs.value(n & 1)          # HSYNC wechselt JE Loop (schnell)
    vs.value(1 if (n & 0xFFF) else 0)   # VSYNC-Puls alle 4096
    n += 1
    if n % 500000 == 0:
        led.toggle()
        print("n =", n)
print("Toggle-Test fertig - LED/Serial lebten, Monitor?")

# freq-Test: Hält machine.freq(150MHz) die REPL?
from machine import freq
print("REPL alive - teste freq(150MHz)...")
freq(150_000_000)
print("freq OK - jetzt 150 MHz")
from machine import Pin
import time
led = Pin(25, Pin.OUT)
n = 0
while True:
    led.toggle()
    print("alive 150MHz", n)
    n += 1
    time.sleep(0.5)

# Nur LED-Blink (kein freq, kein VGA) - lebt die REPL?
from machine import Pin
import time
led = Pin(25, Pin.OUT)
while True:
    led.toggle()
    print("alive")
    time.sleep(0.5)

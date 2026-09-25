# LED-Blink-Test - erster Test nach CircuitPython-Flash
# Funktioniert auf Pico UND Pico 2 (beide: Onboard-LED = GP25)
# Auf CIRCUITPY/code.py kopieren, Pico startet automatisch neu
import board
import digitalio
import time

led = digitalio.DigitalInOut(board.GP25)  # Onboard-LED beim Pico
led.direction = digitalio.Direction.OUTPUT

print("LED-Blink-Test laeuft - 0.5s Intervall")

while True:
    led.value = True
    time.sleep(0.5)
    led.value = False
    time.sleep(0.5)
# vga_stripes_test.py - VOLLES RLE-Streifenmuster (alle 480 Zeilen)
# 16px-Runs abwechselnd gelb/blau -> beweist RLE-DMA bei Farb-Test-Rate.
# LED: 3x Start, danach 1x/s.
import board
import rp2pio
import adafruit_pioasm
import digitalio
import time
import array

led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT
def blink(n, dt=0.12):
    for _ in range(n):
        led.value = True; time.sleep(dt); led.value = False; time.sleep(dt)
blink(3)
print("Streifen-Test...")

timing_pio = """
    pull
    out pins, 14
    set x, 0
    out x, 14
period_loop:
    jmp x-- period_loop
"""
timing_prog = adafruit_pioasm.assemble(timing_pio)

def tw(c_, hl=False, vl=False):
    b0 = 0 if hl else 1
    b1 = 0 if vl else 1
    return (((c_ - 5) << 14) | b0 | (b1 << 1)) & 0xFFFFFFFF

YELLOW = (15 << 2) | (15 << 6)   # 0x3FC
BLUE = 15 << 10                   # 0x3C00

frame = array.array("I")
for vline in range(480):
    frame.append(tw(96)); frame.append(tw(576, True)); frame.append(tw(288))
    # 40 Runs a 16 px, Start-Farbe wechselt pro Zeile (Schachbrett-Effekt):
    start = YELLOW if (vline // 8) % 2 == 0 else BLUE
    col1, col2 = start, (BLUE if start == YELLOW else YELLOW)
    for i in range(40):
        col = col1 if i % 2 == 0 else col2
        frame.append((((16 * 6 - 5) << 14) | col) & 0xFFFFFFFF)
for _ in range(10):
    frame.append(tw(96)); frame.append(tw(576, True)); frame.append(tw(288)); frame.append(tw(3840))
for _ in range(2):
    frame.append(tw(96)); frame.append(tw(576, True)); frame.append(tw(288)); frame.append(tw(3840, vl=True))
for _ in range(33):
    frame.append(tw(96)); frame.append(tw(576, True)); frame.append(tw(288)); frame.append(tw(3840))
print("Woerter:", len(frame), "=", len(frame) * 4, "Bytes")

sm = rp2pio.StateMachine(
    timing_prog,
    frequency=150_000_000,
    first_out_pin=board.GP0,
    out_pin_count=14,
    initial_out_pin_state=0b11,
    initial_out_pin_direction=0x3FFF,
    auto_pull=False,
)
noutput_en = digitalio.DigitalInOut(board.GP21)
noutput_en.direction = digitalio.Direction.OUTPUT
noutput_en.value = True
print("GP21 nOUTPUT_EN = HIGH")
sm.background_write(loop=frame)
print("Streifen aktiv (alle 480 Zeilen RLE).")
n = 0
while True:
    time.sleep(1)
    n += 1
    led.value = not led.value
    print("alive", n)

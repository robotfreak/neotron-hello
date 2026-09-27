# putloop_rawtuple: Das Decorator-9-Tuple als RAW-Programm 1:1
# (die exakte Schablone aus Peters asmcompare-Ausgabe)
from machine import Pin, freq
import rp2
import time
from array import array
freq(150_000_000)
Pin(21, Pin.OUT).value(1)

# Das EXAKTE 9-Feld-Tuple (Peters Schablone):
PROG = (array("H", [32928, 24590, 57376, 24622, 68]),
        -1, -1, -1,
        16384,      # EXECCTRL: wrap_top=4
        524288,     # SHIFTCTRL: out_shiftdir right
        (3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3),  # out_init
        None,       # set_pins
        None)       # sideset_pins

sm = rp2.StateMachine(0, PROG, freq=150_000_000, out_base=0)
sm.active(1)
print("SM aktiv (RAW-9-Tuple) - put-Feed ROT")

def word(cycles, hsync_low=False, vsync_low=False, color=0):
    b0 = 0 if hsync_low else 1
    b1 = 0 if vsync_low else 1
    return (((cycles - 5) << 14) | color | b0 | (b1 << 1)) & 0xFFFFFFFF

CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840
RED = 0b1111 << 2
W_FRONT = word(CY_FRONT)
W_SYNC = word(CY_SYNC, hsync_low=True)
W_BACK = word(CY_BACK)
W_VIS_RED = word(CY_VIS, color=RED)
W_BLANK = word(CY_VIS)

led = Pin(25, Pin.OUT)
n = 0
try:
    while True:
        for _ in range(480):
            for w in (W_FRONT, W_SYNC, W_BACK, W_VIS_RED):
                sm.put(w)
        for _ in range(10):
            for w in (W_FRONT, W_SYNC, W_BACK, W_BLANK):
                sm.put(w)
        for _ in range(2):
            for w in (word(CY_FRONT, vsync_low=True),
                      word(CY_SYNC, True, True),
                      word(CY_BACK, vsync_low=True),
                      word(CY_VIS, vsync_low=True)):
                sm.put(w)
        for _ in range(33):   # Back-Porch (525 = 480+10+2+33!)
            for w in (W_FRONT, W_SYNC, W_BACK, W_BLANK):
                sm.put(w)
        led.toggle()
        n += 1
        if n % 30 == 0:
            print("Frames:", n)
except KeyboardInterrupt:
    print("Frames:", n)

# vga_bands_test.py - Diagnose/Fallback: Farbbaender + RLE-Streifen in Bildmitte
#
# Beweis-Test, falls der Textmodus keinen Text zeigt:
#   Zeilen 80-95  : GELBER Block  (1 Vis-Wort/Zeile - bewiesene Farb-Test-Struktur)
#   Zeilen 96-111 : WEISSER Block (dito)
#   Zeilen 240-271: RLE-Zebra (16px gelb/blau, 40 kurze Woerter/Zeile - Phase-D-Struktur)
# Rest: blau. Porches SCHWARZ (AC-Kopplung! Farbe nur im Sichtbaren).
#
# Deutung:
#   Bloecke + Zebra sichtbar -> Frame-Geometrie + RLE ok -> Bug liegt im Glyph-Rendering
#   Nur Bloecke, kein Zebra  -> kurze RLE-Woerter kommen nicht durch
#   Nichts sichtbar          -> Problem vor dem Rendering (DMA/Buffer)
#
# LED: 3x Start, danach 1x/s Heartbeat.
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
        led.value = True
        time.sleep(dt)
        led.value = False
        time.sleep(dt)

blink(3)
print("Bands-Test (Diagnose)...")

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

YELLOW = (15 << 2) | (15 << 6)
WHITE = (15 << 2) | (15 << 6) | (15 << 10)
BLUE = 15 << 10

CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840
W_FRONT = tw(CY_FRONT)
W_SYNC = tw(CY_SYNC, True)
W_BACK = tw(CY_BACK)
W_BLANK = tw(CY_VIS)
W_BLUE = W_BLANK | BLUE

frame = array.array("I")
for vline in range(480):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK)
    if 80 <= vline < 96:
        frame.append(W_BLANK | YELLOW)
    elif 96 <= vline < 112:
        frame.append(W_BLANK | WHITE)
    elif 240 <= vline < 272:
        start = YELLOW if (vline // 8) % 2 == 0 else BLUE
        c1 = start
        c2 = BLUE if start == YELLOW else YELLOW
        for i in range(40):
            col = c1 if i % 2 == 0 else c2
            frame.append((((16 * 6 - 5) << 14) | col) & 0xFFFFFFFF)
    else:
        frame.append(W_BLUE)
for _ in range(10):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(W_BLANK)
for _ in range(2):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(tw(CY_VIS, vl=True))
for _ in range(33):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(W_BLANK)
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

# Workaround (Phase-D-Beweis): 1. background_write haengt oft,
# der 2. Aufruf aktiviert die DMA-Kette sauber.
dummy = array.array("I", (W_FRONT, W_SYNC, W_BACK, W_BLANK) * 480
                    + (W_FRONT, W_SYNC, W_BACK, tw(CY_VIS, vl=True)) * 2
                    + (W_FRONT, W_SYNC, W_BACK, W_BLANK) * 43)
sm.background_write(loop=dummy)
time.sleep(0.5)
sm.background_write(loop=frame)
print("Bands aktiv (59,52 Hz). Monitor-Erwartung:")
print("  gelber Block + weisser Block (Mitte-oben), Zebra-Streifen (Mitte)")
n = 0
while True:
    time.sleep(1)
    n += 1
    led.value = not led.value
    print("alive", n)
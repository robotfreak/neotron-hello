# vga_anchor_bait.py - Lock-Anker-Koeder: 2 feine RLE-Streifen vor VBLANK
#
# Bewiesener Anker: Der Monitor lockt auf das detailreichste Muster (RLE/Text)
# und legt dessen START auf Screen x=462. Der Koeder: 2 Zeilen mit feinem
# Streifenmuster (RLE, alle 8px Farbwechsel) bei f=470-471 - STRUKTURELL
# wie Text, aber kaum sichtbar (1cm-Streifen am Bildrand).
# Wenn der Monitor auf den KOEDER lockt: S = 470-462 = 8 -> Text f=200
# erscheint bei Screen 192 (Bildmitte-oben, voll sichtbar).
# Wenn er beim TEXT bleibt: Koeder detailreicher machen (naechster Schritt).
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
print("Koeder-Test (2 RLE-Streifen f=470)...")
import math

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
W_WHITE = W_BLANK | WHITE

TEXT = "NEOTRON PICO"
TEXT_ROW = 25          # f=200-227
BAIT_ROW = 470         # Koeder: f=470-471 (2 Zeilen)
SCALE = 4

GLYPHS = {
    32: [0, 0, 0, 0, 0, 0, 0, 0],
    67: [60, 102, 3, 3, 3, 102, 60, 0],
    69: [127, 70, 22, 30, 22, 70, 127, 0],
    73: [30, 12, 12, 12, 12, 12, 30, 0],
    78: [99, 103, 111, 123, 115, 99, 99, 0],
    79: [28, 54, 99, 99, 99, 54, 28, 0],
    80: [63, 102, 102, 62, 6, 6, 15, 0],
    82: [63, 102, 102, 62, 54, 102, 103, 0],
    84: [63, 45, 12, 12, 12, 12, 30, 0],
}

def rle_words(colors):
    out = []
    i = 0
    n = len(colors)
    while i < n:
        j = i
        while j < n and colors[j] == colors[i]:
            j += 1
        out.append((((j - i) * 6 - 5) << 14) | colors[i])
        i = j
    return out

frame = array.array("I")
for vline in range(480):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK)
    if BAIT_ROW <= vline < BAIT_ROW + 2:
        # Koeder: feine Streifen alle 8 px (gelb/weiss)
        rc = [YELLOW if (x // 8) % 2 == 0 else WHITE for x in range(640)]
        frame.extend(rle_words(rc))
    elif TEXT_ROW * 8 <= vline < TEXT_ROW * 8 + 8 * SCALE:
        frow = (vline - TEXT_ROW * 8) // SCALE
        rc = [WHITE] * 640
        for ch_idx, ch in enumerate(TEXT):
            bits = GLYPHS[ord(ch)][frow]
            base = (6 + ch_idx) * 8 * SCALE
            for px in range(8):
                col = base + px * SCALE
                on = BLUE if ((bits >> px) & 1) else WHITE
                for k in range(SCALE):
                    if 0 <= col + k < 640:
                        rc[col + k] = on
        frame.extend(rle_words(rc))
    else:
        frame.append(W_WHITE)
for _ in range(10):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(W_BLANK)
for _ in range(2):
    frame.extend((tw(CY_FRONT, vl=True), tw(CY_SYNC, True, vl=True), tw(CY_BACK, vl=True), tw(CY_VIS, vl=True)))
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

dummy = array.array("I", (W_FRONT, W_SYNC, W_BACK, W_BLANK) * 525)
sm.background_write(loop=dummy)
time.sleep(0.5)
sm.background_write(loop=frame)
print("Koeder aktiv. Erwartung: Text bei ~40% Bildhoehe, feine Streifen unten.")
n = 0
while True:
    time.sleep(1)
    n += 1
    led.value = not led.value
    print("alive", n)
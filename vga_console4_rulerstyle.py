# vga_console4_rulerstyle.py - ISOLATION: exakt die ruler-Struktur
# (bewiesen laufend heute) mit Stativ-Text. Variabler RLE, leere
# Zeilen 1 Wort, KEIN Patch, KEIN SPI. Wenn das laeuft: Struktur
# bewiesen, naechster Schritt: Patch-Technik auf ruler-Basis.
import board
import rp2pio
import adafruit_pioasm
import digitalio
import time
import array
import font8x8

FONT = font8x8.FONT
led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT

def blink(n, dt=0.12):
    for _ in range(n):
        led.value = True; time.sleep(dt)
        led.value = False; time.sleep(dt)

blink(3)
print("[1] Start")

timing_pio = """
    pull
    out pins, 14
    set x, 0
    out x, 14
period_loop:
    jmp x-- period_loop
"""
timing_prog = adafruit_pioasm.assemble(timing_pio)
print("[2] PIO-Asm ok")

CY_FRONT = 16 * 6
CY_SYNC = 96 * 6
CY_BACK = 48 * 6
CY_VIS = 640 * 6
BLUE = 15 << 10
YELLOW = 0x3FC
WHITE = (15 << 2) | (15 << 6) | (15 << 10)
FG, BG = BLUE, WHITE
IDLE = 0b11

def word(cycles_, hsync_low=False, vsync_low=False, color=0):
    b0 = 0 if hsync_low else 1
    b1 = 0 if vsync_low else 1
    return (((cycles_ - 5) << 14) | b0 | (b1 << 1) | color) & 0xFFFFFFFF

W_FRONT = word(CY_FRONT)
W_SYNC = word(CY_SYNC, True)
W_BACK = word(CY_BACK)
W_BLANK = word(CY_VIS, color=BG)

def tw(c_, hl=False, vl=False, col=0):
    return (((c_ - 5) << 14) | (0 if hl else 1) | ((0 if vl else 1) << 1) | col) & 0xFFFFFFFF

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

TEXT = "NEOTRON PICO"
SCALE = 2
TEXT_ROW = 25

frame = array.array("I")
for vline in range(480):
    if vline % 64 == 63:
        time.sleep(0)
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK)
    if TEXT_ROW * 8 <= vline < TEXT_ROW * 8 + 8 * SCALE:
        frow = (vline - TEXT_ROW * 8) // SCALE
        rc = [BG] * 640
        for ch_idx, ch in enumerate(TEXT):
            bits = FONT[ord(ch)][frow]
            base = (6 + ch_idx) * 8 * SCALE
            for px in range(8):
                col = base + px * SCALE
                on = FG if ((bits >> px) & 1) else BG
                for k in range(SCALE):
                    if 0 <= col + k < 640:
                        rc[col + k] = on
        frame.extend(rle_words(rc))
    else:
        frame.append(W_BLANK)
for _ in range(10):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(W_BLANK)
for _ in range(2):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(tw(CY_VIS, vl=True))
for _ in range(33):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(W_BLANK)
print("[3] Frame:", len(frame), "Woerter =", len(frame) * 4, "Bytes")

sm = rp2pio.StateMachine(
    timing_prog,
    frequency=150_000_000,
    first_out_pin=board.GP0,
    out_pin_count=14,
    initial_out_pin_state=IDLE,
    initial_out_pin_direction=0x3FFF,
    auto_pull=False,
)
print("[4] SM ok")

sm.background_write(loop=frame)
print("[5] geschrieben - Monitor: NEOTRON PICO?")

try:
    noutput_en = digitalio.DigitalInOut(board.GP21)
    noutput_en.direction = digitalio.Direction.OUTPUT
    noutput_en.value = True
except Exception as e:
    print("WARN GP21:", e)

n = 0
while True:
    time.sleep(1)
    n += 1
    led.value = not led.value
    print("alive", n)

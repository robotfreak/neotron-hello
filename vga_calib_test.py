# vga_calib_test.py - Vertikal-Kalibration: Lineal + 2 Textkopien
#
# Auf Basis des LAUFENDEN Text-Tests (v9: Text sichtbar, aber unten abgeschnitten).
# Ziel: Die vertikale Verschiebung des Monitors messen.
#
# Monitor-Erwartung:
#   - 5 gelbe Lineal-Balken (je 2 Zeilen) bei Bildzeilen 0, 120, 240, 360, 420
#   - "NEOTRON PICO" (gelb, 32 Zeilen hoch) bei Zeilen 60-91 UND 250-281
#   - Rest: blaues Vollbild, unten schwarzer Balken (VBLANK, normal)
#
# Peter meldet: Balken ganz oben sichtbar? Wie viele Balken? Wo ist der letzte?
#               Welche Textkopie(n) vollstaendig sichtbar?
# -> Daraus berechnet Hermes die exakte Zeilenverschiebung und setzt
#    die finale Text-Position in vga_text_test.py.
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
print("Kalibrationstest (Lineal + 2 Textkopien)...")

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
BLUE = 15 << 10

CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840
W_FRONT = tw(CY_FRONT)
W_SYNC = tw(CY_SYNC, True)
W_BACK = tw(CY_BACK)
W_BLANK = tw(CY_VIS)
W_BLUE = W_BLANK | BLUE
W_YELLOW = W_BLANK | YELLOW

TEXT = "NEOTRON PICO"
TEXT_ZONES = (60, 250)   # Startzeilen der beiden Textkopien (je 32 Zeilen hoch)
SCALE = 4                # Font-Pixel = 4x4 Screen-Pixel
BAR_ROWS = (0, 1, 120, 121, 240, 241, 360, 361, 420, 421)

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

def text_row_colors(start, frow):
    rc = [BLUE] * 640
    for ch_idx, ch in enumerate(TEXT):
        bits = GLYPHS[ord(ch)][frow]
        base = (6 + ch_idx) * 8 * SCALE
        for px in range(8):
            col = base + px * SCALE
            on = YELLOW if ((bits >> px) & 1) else BLUE
            for k in range(SCALE):
                if 0 <= col + k < 640:
                    rc[col + k] = on
    return rc

frame = array.array("I")
for vline in range(480):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK)
    if vline in BAR_ROWS:
        frame.append(W_YELLOW)
    else:
        zone = None
        for start in TEXT_ZONES:
            if start <= vline < start + 8 * SCALE:
                zone = start
                break
        if zone is not None:
            frow = (vline - zone) // SCALE
            frame.extend(rle_words(text_row_colors(zone, frow)))
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

# Workaround (bewiesen): 1. background_write haengt oft,
# der 2. Aufruf aktiviert die DMA-Kette sauber.
dummy = array.array("I", (W_FRONT, W_SYNC, W_BACK, W_BLANK) * 525)
sm.background_write(loop=dummy)
time.sleep(0.5)
sm.background_write(loop=frame)
print("Kalibration aktiv (59,52 Hz).")
print("Erwartung: 5 gelbe Balken + 2x NEOTRON PICO auf Blau")
n = 0
while True:
    time.sleep(1)
    n += 1
    led.value = not led.value
    print("alive", n)
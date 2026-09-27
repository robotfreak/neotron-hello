# vga_console2.py - BASIC-Konsole auf bewiesenem Ein-Write-Weg
#
# Beweise:
#   - color_test-Struktur (je Zeile 3 Sync + 1 Vis-Wort) LÄUFT
#   - Doppel-Write (dummy+frame) KILLT den Sync (heute isoliert)
#   - BMC-Poll neben VGA-DMA: verdächtig, deshalb 2x/s gedrosselt
#   - In-Place-Edits am laufenden DMA-Buffer: CP-Doku beweist, dass
#     die DMA die neuen Werte übernimmt
# Textzeilen: FEST 30 Wörter je Fontzeile (balancierte Splits,
#   pixelidentisch, min ~20px = 115+ Takte je Wort -> DMA-sicher)
# Frame: 2100 - 32 + 32*30 = 3028 Woerter = 12112 B (unter 12288)
import board
import rp2pio
import adafruit_pioasm
import digitalio
import microcontroller
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

# ============ Wort-Formel (color_test-Identisch) ============
CY_FRONT = 16 * 6
CY_SYNC = 96 * 6
CY_BACK = 48 * 6
CY_VIS = 640 * 6
WHITE = (15 << 2) | (15 << 6) | (15 << 10)
BLUE = 15 << 10
FG, BG = BLUE, WHITE
IDLE = 0b11

def word(cycles_, hsync_low=False, vsync_low=False, color=0):
    b0 = 0 if hsync_low else 1
    b1 = 0 if vsync_low else 1
    return (((cycles_ - 5) << 14) | b0 | (b1 << 1) | color) & 0xFFFFFFFF

W_FRONT = word(CY_FRONT)
W_SYNC = word(CY_SYNC, True)
W_BACK = word(CY_BACK)
W_VIS = word(CY_VIS, color=BG)

# ============ FEST-30-Run-Technik ============
WORDS_PER_ROW = 30

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

def fit_words(runs_words, n=WORDS_PER_ROW):
    """Runs auf EXAKT n bringen (pixelidentisch):
    letzten Run verlaengern, GROESSTEN Run halbieren (balanciert ->
    alle Runs gross genug, kein FIFO-Underrun)."""
    if len(runs_words) > n:
        return None
    words = list(runs_words)
    total_px = sum(((w >> 14) + 5) // 6 for w in words)
    last = words[-1]
    col = last & 0x3FFF
    last_px = (((last >> 14) + 5) // 6)
    need = 640 - (total_px - last_px)
    words[-1] = ((need * 6 - 5) << 14) | col
    while len(words) < n:
        idx = None
        best_px = 3
        for k in range(len(words)):
            w = words[k]
            px = (((w >> 14) + 5) // 6)
            if px > best_px:
                best_px = px
                idx = k
        if idx is None:
            return None
        w = words[idx]
        col = w & 0x3FFF
        px = best_px
        half = px // 2
        words[idx:idx+1] = [((half * 6 - 5) << 14) | col,
                            (((px - half) * 6 - 5) << 14) | col]
    return words

MAX_CHARS = 26   # 6 + 26*16 = 422 < 640; genug für BASIC-Zeilen

def line_words(text):
    """16 Fontzeilen je EXAKT 30 Wörter (None = Text kürzen)."""
    rows = []
    for frow in range(8 * 2):   # SCALE=2 -> 16 RLE-Zeilen
        rc = [BG] * 640
        for ch_idx, ch in enumerate(text[:MAX_CHARS]):
            bits = FONT.get(ord(ch), FONT[63])[frow % 8]
            base = (6 + ch_idx) * 16
            for px in range(8):
                col = base + px * 2
                on = FG if ((bits >> px) & 1) else BG
                rc[col] = on; rc[col + 1] = on
        f = fit_words(rle_words(rc))
        if f is None:
            return None
        rows.append(f)
    return rows

# ============ Frame mit festen Text-Spans ============
TEXT_ROWS = (25, 35)   # Zeile A (Eingabe) f=200-215, Zeile B (Ausgabe) f=280-295

spans = {}
frame = array.array("I")
for vline in range(480):
    if vline % 64 == 63:
        time.sleep(0)
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK)
    tri = None
    for t_i, trow in enumerate(TEXT_ROWS):
        if trow * 8 <= vline < trow * 8 + 16:
            tri = t_i
            break
    if tri is not None:
        if vline == TEXT_ROWS[tri] * 8:
            span = []
        words = line_words("")   # leere Zeile: 30 Woerter
        if words is None:
            # Leere Zeile sollte immer passen - Fallback: W_VIS
            frame.append(word(CY_VIS, color=BG))
            continue
        span.append(len(frame))
        frame.extend(words[0])
        if vline == TEXT_ROWS[tri] * 8 + 15:
            spans[tri] = span
    else:
        frame.append(word(CY_VIS, color=BG))
for _ in range(10):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(word(CY_VIS))
for _ in range(2):
    frame.extend((word(CY_FRONT), word(CY_SYNC, True, True), word(CY_BACK, True, True), word(CY_VIS, True, True)))
for _ in range(33):
    frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(word(CY_VIS))
print("[3] Frame:", len(frame), "Woerter =", len(frame) * 4, "Bytes")

# ============ SM + EIN Write ============
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

sm.background_write(loop=frame)   # EIN Write - kein Dummy!
print("[5] VGA aktiv - Monitor weiss mit 2 Zeilen?")

# ============ Zeilen-Renderer (In-Place) ============
cur_a, cur_b = "", ""
pend_a, pend_b, pend = "", "", False

def show(text_a=None, text_b=None):
    global pend_a, pend_b, pend
    if text_a is not None:
        pend_a = text_a
    if text_b is not None:
        pend_b = text_b
    pend = True

def render_span(tri, text):
    """Textzeile in-place patchen (Text so lange kürzen bis 30 Runs)."""
    span = spans[tri]
    words = line_words(text)
    for _ in range(20):
        if words is not None:
            break
        text = text[:-2]
        words = line_words(text)
    if words is None:
        words = line_words("")
    if tri == 0:
        cur_a = text
    else:
        cur_b = text
    for frow, w30 in enumerate(words):
        start = span[frow]
        frame[start:start + WORDS_PER_ROW] = array.array("I", w30)

# ============ BMC-Tastatur (bewiesener Code) ============

print("[6] In-Place-Patch-Demo: Zeile A zaehlt hoch")
n = 0
while True:
    n += 1
    show("[%d] NEOTRON PICO" % (n % 10), None)
    # Patch anwenden (In-Place, ohne background_write):
    pend = False
    if pend_a != cur_a:
        words = line_words(pend_a)
        for _ in range(20):
            if words is not None:
                break
            pend_a = pend_a[:-2]
            words = line_words(pend_a)
        if words is None:
            words = line_words("")
        cur_a = pend_a
        span = spans[0]
        for frow, w30 in enumerate(words):
            start = span[frow]
            frame[start:start + 30] = array.array("I", w30)
    led.value = n % 2
    time.sleep(1)

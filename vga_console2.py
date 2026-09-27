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
import busio
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
print("[6] SPI...")
spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
while not spi.try_lock():
    pass
spi.configure(baudrate=2_000_000, polarity=0, phase=0, bits=8)
cs = digitalio.DigitalInOut(board.GP17)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True

def crc8(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

def mcp23s17_write(reg, value):
    cs.value = False
    try:
        spi.write(bytes([0x40, reg, value]))
    finally:
        cs.value = True

mcp23s17_write(0x00, 0x00)
mcp23s17_write(0x01, 0xFF)
mcp23s17_write(0x12, 0x00)
mcp23s17_write(0x14, 0x00)
mcp23s17_write(0x15, 0xFF)
print("[7] MCP23S17 ok")

nirq = digitalio.DigitalInOut(board.GP20)
nirq.direction = digitalio.Direction.INPUT
nirq.pull = digitalio.Pull.UP

use_alt = False
buf1 = bytearray(1)

def bmc_transfer(req_bytes, response_len, quiet=False):
    global use_alt
    noutput_en = digitalio.DigitalInOut(board.GP21)
    noutput_en.direction = digitalio.Direction.OUTPUT
    noutput_en.value = False
    try:
        spi.write(req_bytes)
        result = None
        for retry in range(128):
            microcontroller.delay_us(6)
            spi.readinto(buf1)
            if buf1[0] in (0xA0, 0xA1, 0xA2, 0xA3, 0xA4):
                result = buf1[0]
                break
        if result is None:
            return None
        rest = bytearray(response_len - 1)
        spi.readinto(rest)
        return bytes([buf1[0]]) + bytes(rest)
    finally:
        noutput_en.value = True

def bmc_read(register, length, quiet=False):
    global use_alt
    t = 0xC1 if use_alt else 0xC0
    use_alt = not use_alt
    req = bytes([t, register, length])
    req += bytes([crc8(req)])
    return bmc_transfer(req, length + 2, quiet)

# ============ PS/2-Set-2 Scancodes (osdev-verifiziert) ============
SC = {}
_c = {'Q':0x15,'W':0x1D,'E':0x24,'R':0x2D,'T':0x2C,'Y':0x35,'U':0x3C,
      'I':0x43,'O':0x44,'P':0x4D,'A':0x1C,'S':0x1B,'D':0x23,'F':0x2B,
      'G':0x34,'H':0x33,'J':0x3B,'K':0x42,'L':0x4B,'Z':0x1A,'X':0x22,
      'C':0x21,'V':0x2A,'B':0x32,'N':0x31,'M':0x3A}
for ch, code in _c.items(): SC[code] = (ch.lower(), ch)
SC[0x29] = (' ', ' ')
for i, code in enumerate([0x16,0x1E,0x26,0x25,0x2E,0x36,0x3D,0x3E,0x46,0x45]):
    SC[code] = (str(i + 1), "!@#$%^&*()"[i])
SC[0x66] = (chr(8), chr(8))
SC[0x5A] = (chr(13), chr(13))
SC[0x0D] = (chr(9), chr(9))
SC[0x0E] = ('`', '~')
SC[0x54] = ('[', '{'); SC[0x5B] = (']', '}'); SC[0x5D] = ('\\', '|')
SC[0x41] = (',', '<'); SC[0x49] = ('.', '>'); SC[0x4A] = ('/', '?')
SC[0x4C] = (';', ':'); SC[0x52] = ("'", '"'); SC[0x4E] = ('-', '_')
SC[0x55] = ('=', '+')

# ============ Tiny-BASIC-Kopplung ============
print("[8] tinybasic import...")
import tinybasic

shift = [False]
last_build = [0.0]
_poll_skip = [0]

def console_out(s):
    parts = [p for p in s.split("\n") if p]
    if parts:
        show(None, parts[-1][:MAX_CHARS])
    print(s, end="")

tinybasic.out = console_out

def bmc_readline(prompt=""):
    line = ""
    shift[0] = False
    show(prompt + "_", None)
    while True:
        # BMC-Poll gedrosselt (2x/s): Je Transfer blockt die CPU ~1ms
        # (128x delay_us(6)) - Kollisionsrisiko mit der VGA-DMA.
        _poll_skip[0] += 1
        resp = None
        if _poll_skip[0] >= 25:
            _poll_skip[0] = 0
            if not nirq.value:
                resp = bmc_read(0x40, 9, quiet=True)
        if resp and resp[0] == 0xA0 and resp[1] > 0 and resp[1] != 0xFF:
                n_scans = resp[1]
                data = resp[2:2 + n_scans]
                i = 0
                while i < len(data):
                    b = data[i]
                    if b == 0xE0:
                        i += 2; continue
                    if b == 0xF0:
                        i += 2; continue
                    if b == 0x12 or b == 0x59:
                        shift[0] = True
                        i += 1; continue
                    entry = SC.get(b)
                    if entry:
                        ch = entry[1] if shift[0] else entry[0]
                        shift[0] = False
                        if ch == chr(13):
                            show(prompt + line, None)
                            return line
                        if ch == chr(8):
                            if line:
                                line = line[:-1]
                        elif ch:
                            if len(line) + len(prompt) < MAX_CHARS:
                                line += ch
                        show(prompt + line + "_", None)
                    i += 1
        ui_tick()
        time.sleep(0.02)
        if (time.monotonic() - last_build[0]) > 1.0:
            last_build[0] = time.monotonic()
            led.value = not led.value
            # diag alle 5s:
            if (time.monotonic() - last_build[0]) > 4.0:
                last_build[0] = time.monotonic()
                r = bmc_read(0x40, 9)
                print("diag 0x40->", r.hex() if r else "None")

def ui_tick():
    """In-Place-Patch (KEIN background_write - bewiesen tödlich)."""
    global pend
    if not pend:
        return
    t0 = time.monotonic()
    if pend_a is not None and pend_a != cur_a:
        render_span(0, pend_a)
    if pend_b is not None and pend_b != cur_b:
        render_span(1, pend_b)
    pend = False
    import gc
    gc.collect()
    print("ui_tick: patch %d ms" % ((time.monotonic() - t0) * 1000))

tinybasic.input = bmc_readline

print("[9] repl()")
print("Tiny-BASIC auf VGA+PS/2. Tipp los!")
try:
    tinybasic.repl()
except KeyboardInterrupt:
    pass
led.value = False
print("Gestoppt.")

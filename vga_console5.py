# vga_console4_rulerstyle.py - ISOLATION: exakt die ruler-Struktur
# (bewiesen laufend heute) mit Stativ-Text. Variabler RLE, leere
# Zeilen 1 Wort, KEIN Patch, KEIN SPI. Wenn das laeuft: Struktur
# bewiesen, naechster Schritt: Patch-Technik auf ruler-Basis.
import board
import rp2pio
import adafruit_pioasm
import digitalio
import time
import busio
import microcontroller
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

try:
    noutput_en = digitalio.DigitalInOut(board.GP21)
    noutput_en.direction = digitalio.Direction.OUTPUT
    noutput_en.value = True
except Exception as e:
    print("WARN GP21:", e)

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

use_alt = [False]
buf1 = bytearray(1)

def bmc_transfer(req_bytes, response_len):
    # GP21 ist EINMAL oben geclaimed - hier nur Pegel toggeln
    # (DigitalInOut im Transfer -> 'GP21 in use'-Crash).
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

def bmc_read(register, length):
    t = 0xC1 if use_alt[0] else 0xC0
    use_alt[0] = not use_alt[0]
    req = bytes([t, register, length])
    req += bytes([crc8(req)])
    return bmc_transfer(req, length + 2)

SC = {}
_c = {'Q':0x15,'W':0x1D,'E':0x24,'R':0x2D,'T':0x2C,'Y':0x35,'U':0x3C,
      'I':0x43,'O':0x44,'P':0x4D,'A':0x1C,'S':0x1B,'D':0x23,'F':0x2B,
      'G':0x34,'H':0x33,'J':0x3B,'K':0x42,'L':0x4B,'Z':0x1A,'X':0x22,
      'C':0x21,'V':0x2A,'B':0x32,'N':0x31,'M':0x3A}
for ch, code in _c.items(): SC[code] = (ch.lower(), ch)
SC[0x29] = (' ', ' ')
for i, code in enumerate([0x16,0x1E,0x26,0x25,0x2E,0x36,0x3D,0x3E,0x46,0x45]):
    SC[code] = (str(i + 1), "!\u0022\u00a3$%^&*()"[i])   # UK-Layout (86 Tasten)
SC[0x66] = (chr(8), chr(8))
SC[0x5A] = (chr(13), chr(13))
SC[0x54] = ('[', '{'); SC[0x5B] = (']', '}')
SC[0x41] = (',', '<'); SC[0x49] = ('.', '>'); SC[0x4A] = ('/', '?')
SC[0x4C] = (';', ':'); SC[0x52] = (chr(39), chr(64))   # UK: Shift+Apostroph=@

SC[0x4E] = ('-', '_')
SC[0x55] = ('=', '+')
print("[8] tinybasic import...")
import tinybasic

shift = [False]
MAX_CHARS = 26
TEXT_ROW_A = 25   # Zurueck auf Lauf-1-Zustand (Balken sichtbar, beweisnah)
TEXT_ROW_B = 35   # Zeile B unter A (wie Lauf 1)

def render_line(text):
    rows = []
    for frow in range(16):
        rc = [BG] * 640
        for ch_idx, ch in enumerate(text[:MAX_CHARS]):
            bits = FONT.get(ord(ch), FONT[63])[frow % 8]
            base = (6 + ch_idx) * 16
            for px in range(8):
                col = base + px * 2
                on = FG if ((bits >> px) & 1) else BG
                rc[col] = on; rc[col + 1] = on
        rows.append(rle_words(rc))
    return rows

cur_a, cur_b = "", ""
pend_a, pend_b = None, None
last_write = [0.0]
poll_skip = [0]
led_t = [0.0]

def write_frame(text_a, text_b):
    frame = array.array("I")
    ra = render_line(text_a) if text_a else None
    rb = render_line(text_b) if text_b else None
    for vline in range(480):
        if vline % 64 == 63:
            time.sleep(0)
        frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK)
        if TEXT_ROW_A * 8 <= vline < TEXT_ROW_A * 8 + 16:
            frow = (vline - TEXT_ROW_A * 8) // 2
            frame.extend(ra[frow] if ra else [W_BLANK])
        elif TEXT_ROW_B * 8 <= vline < TEXT_ROW_B * 8 + 16:
            frow = (vline - TEXT_ROW_B * 8) // 2
            frame.extend(rb[frow] if rb else [W_BLANK])
        else:
            frame.append(W_BLANK)
    for _ in range(10):
        frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(W_BLANK)
    for _ in range(2):
        frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(tw(CY_VIS, vl=True))
    for _ in range(33):
        frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK); frame.append(W_BLANK)
    sm.background_write(loop=frame)
    import gc
    gc.collect()
    return len(frame)

def ui_tick():
    global cur_a, cur_b, pend_a, pend_b
    t0 = time.monotonic()
    n = 0
    if pend_a is not None and pend_a != cur_a:
        n = write_frame(pend_a, cur_b if cur_b else None)
        cur_a = pend_a; pend_a = None
        last_write[0] = t0
    elif pend_b is not None and pend_b != cur_b:
        n = write_frame(cur_a if cur_a else None, pend_b)
        cur_b = pend_b; pend_b = None
        last_write[0] = t0
    if n:
        print("ui_tick: build+write %d ms, %d Woerter" % ((time.monotonic() - t0) * 1000, n))

def console_out(s):
    global pend_b
    parts = [p for p in s.split(chr(10)) if p]
    if parts:
        pend_b = parts[-1][:MAX_CHARS]
    print(s, end="")

tinybasic.out = console_out

def bmc_readline(prompt=""):
    global pend_a
    line = ""
    shift[0] = False
    pend_a = prompt + "_"
    while True:
        poll_skip[0] += 1
        if poll_skip[0] >= 2:   # 20 Polls/s (0.04s) - fluessiges Echo
            poll_skip[0] = 0
            resp = bmc_read(0x40, 9)  # OHNE nirq-Gate (bewiesen: INT kommt nie)
            if resp and resp[0] == 0xA0 and resp[1] > 0 and resp[1] != 0xFF:
                n_scans = resp[1]
                data = resp[2:2 + n_scans]
                i = 0
                while i < len(data):
                    b = data[i]
                    if b == 0xE0 or b == 0xF0:
                        i += 2; continue
                    if b == 0x12 or b == 0x59:
                        shift[0] = True
                        i += 1; continue
                    entry = SC.get(b)
                    if entry is None and b:
                        print("RAW-Scancode:", hex(b))
                    if entry:
                        ch = entry[1] if shift[0] else entry[0]
                        shift[0] = False
                        if ch == chr(13):
                            pend_a = prompt + line
                            ui_tick()
                            return line
                        if ch == chr(8):
                            if line: line = line[:-1]
                        elif ch:
                            if len(line) + len(prompt) < MAX_CHARS:
                                line += ch
                        pend_a = prompt + line + "_"
                    i += 1
        if (pend_a is not None and pend_a != cur_a) and (time.monotonic() - last_write[0]) > 0.1:
            ui_tick()
        if time.monotonic() - led_t[0] > 1.0:
            led_t[0] = time.monotonic()
            led.value = not led.value
        time.sleep(0.02)

tinybasic.input = bmc_readline

print("[9] repl()")
print("Tiny-BASIC auf VGA+PS/2. Tipp los!")
n = write_frame("] _", None)
print("Start-Frame:", n, "Woerter")
try:
    tinybasic.repl()
except KeyboardInterrupt:
    pass
led.value = False
print("Gestoppt.")

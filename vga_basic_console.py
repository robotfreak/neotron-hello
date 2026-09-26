# vga_basic_console.py - Tiny-BASIC auf VGA + PS/2-Tastatur (Neotron-Pico)
#
# Bewiesene Bausteine kombiniert:
#   VGA: vga_text_final-Struktur (weisser BG, SCALE=2, 525 Zeilen, RLE)
#   Tastatur: bmc_keyboard_test (BMC-SPI Register 0x40, verifiziert)
#   BASIC: tinybasic.py (17/17 Tests) via out()/input()-Shim
#
# Konzept: 2 Textzeilen im Frame (32 RLE-Zeilen gesamt = bewiesene Grenze):
#   Zeile A (TEXT_ROW 25, f=200-215): Eingabezeile mit Cursor
#   Zeile B (TEXT_ROW 35, f=280-295): letzte BASIC-Ausgabe
# Nach jedem Tastendruck: kompletter Frame-Rebuild + background_write
# (bewiesener Doppel-Write-Pfad, stabil).
#
# LED: 3x Start, danach Heartbeat im Poll-Loop.
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
        led.value = True
        time.sleep(dt)
        led.value = False
        time.sleep(dt)

blink(3)
print("[1] Start")

# ============ VGA-Frame (bewiesene Struktur) ============
timing_pio = """
    pull
    out pins, 14
    set x, 0
    out x, 14
period_loop:
    jmp x-- period_loop
"""
print("[2] PIO-Asm...")
timing_prog = adafruit_pioasm.assemble(timing_pio)

def tw(c_, hl=False, vl=False):
    b0 = 0 if hl else 1
    b1 = 0 if vl else 1
    return (((c_ - 5) << 14) | b0 | (b1 << 1)) & 0xFFFFFFFF

WHITE = (15 << 2) | (15 << 6) | (15 << 10)
BLUE = 15 << 10
FG, BG = BLUE, WHITE

CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840
W_FRONT = tw(CY_FRONT)
W_SYNC = tw(CY_SYNC, True)
W_BACK = tw(CY_BACK)
W_BLANK = tw(CY_VIS)
W_WHITE = W_BLANK | WHITE

TEXT_ROWS = (25, 35)   # Zeile A (Eingabe) f=200-215, Zeile B (Ausgabe) f=280-295
SCALE = 2
MAX_CHARS = 30         # 6 + 30*16 = 486 < 640

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

def build_frame(text_a, text_b):
    """Kompletter Frame: 480 sichtbare Zeilen (2 Textzeilen), 45 VBLANK.
    text_a -> Zeile A (Eingabe), text_b -> Zeile B (Ausgabe).
    Alle 64 Zeilen time.sleep(0): VM-yield, USB/CTRL-C bleibt bedienbar."""
    f = array.array("I")
    for vline in range(480):
        if vline % 64 == 63:
            time.sleep(0)   # VM-yield: USB/Keyboard-IRQs durchlassen
        f.append(W_FRONT); f.append(W_SYNC); f.append(W_BACK)
        tri = None
        for t_i, trow in enumerate(TEXT_ROWS):
            if trow * 8 <= vline < trow * 8 + 8 * SCALE:
                tri = t_i
                break
        if tri is not None:
            text = text_a if tri == 0 else text_b
            frow = (vline - TEXT_ROWS[tri] * 8) // SCALE
            rc = [BG] * 640
            for ch_idx, ch in enumerate(text[:MAX_CHARS]):
                bits = FONT.get(ord(ch), FONT[63])[frow]
                base = (6 + ch_idx) * 8 * SCALE
                for px in range(8):
                    col = base + px * SCALE
                    on = FG if ((bits >> px) & 1) else BG
                    for k in range(SCALE):
                        if 0 <= col + k < 640:
                            rc[col + k] = on
            f.extend(rle_words(rc))
        else:
            f.append(W_WHITE)
    for _ in range(10):
        f.append(W_FRONT); f.append(W_SYNC); f.append(W_BACK); f.append(W_BLANK)
    for _ in range(2):
        f.extend((tw(CY_FRONT, vl=True), tw(CY_SYNC, True, vl=True), tw(CY_BACK, vl=True), tw(CY_VIS, vl=True)))
    for _ in range(33):
        f.append(W_FRONT); f.append(W_SYNC); f.append(W_BACK); f.append(W_BLANK)
    return f

print("[3] Frame-Bau...")
frame = build_frame("", "")
print("Woerter:", len(frame), "=", len(frame) * 4, "Bytes")

print("[4] StateMachine...")
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

print("[5] Dummy-Write...")
dummy = array.array("I", (W_FRONT, W_SYNC, W_BACK, W_BLANK) * 525)
sm.background_write(loop=dummy)
time.sleep(0.5)
sm.background_write(loop=frame)
print("[6] VGA ok")
print("VGA aktiv (weisser BG, 2 Textzeilen).")

WORD_LIMIT = 3068   # bewiesene Kipp-Grenze (v9 lief exakt hierunter)

def show(text_a=None, text_b=None):
    """Zeilen nur QUEUE'N; der zentrale UI-Loop rendert max 1x/100ms.
    Mindestens 6 saubere DMA-Loops zwischen Writes (bewiesener Rhythmus)."""
    global pend_a, pend_b, pend
    if text_a is not None:
        pend_a = text_a
    if text_b is not None:
        pend_b = text_b
    pend = True

cur_a, cur_b = "", ""
pend_a, pend_b, pend = "", "", False

# ============ BMC-Tastatur (bewiesener Code) ============
print("[7] SPI...")
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

print("[8] MCP23S17...")
mcp23s17_write(0x00, 0x00)
mcp23s17_write(0x01, 0xFF)
mcp23s17_write(0x12, 0x00)
mcp23s17_write(0x14, 0x00)
mcp23s17_write(0x15, 0xFF)

nirq = digitalio.DigitalInOut(board.GP20)
nirq.direction = digitalio.Direction.INPUT
nirq.pull = digitalio.Pull.UP

use_alt = False
buf1 = bytearray(1)

def bmc_transfer(req_bytes, response_len, quiet=False):
    global use_alt
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

# ============ PS/2-Set-2 Scancode-Tabelle (osdev-verifiziert) ============
SC = {}
_c = {'Q':0x15,'W':0x1D,'E':0x24,'R':0x2D,'T':0x2C,'Y':0x35,'U':0x3C,
      'I':0x43,'O':0x44,'P':0x4D,'A':0x1C,'S':0x1B,'D':0x23,'F':0x2B,
      'G':0x34,'H':0x33,'J':0x3B,'K':0x42,'L':0x4B,'Z':0x1A,'X':0x22,
      'C':0x21,'V':0x2A,'B':0x32,'N':0x31,'M':0x3A}
for ch, code in _c.items(): SC[code] = (ch.lower(), ch)
SC[0x29] = (' ', ' ')
for i, code in enumerate([0x16,0x1E,0x26,0x25,0x2E,0x36,0x3D,0x3E,0x46,0x45]):
    SC[code] = (str(i + 1), "!@#$%^&*()"[i])
SC[0x66] = (chr(8), chr(8))       # Backspace
SC[0x5A] = (chr(13), chr(13))     # Enter
SC[0x0D] = (chr(9), chr(9))       # Tab
SC[0x0E] = ('`', '~')
SC[0x54] = ('[', '{'); SC[0x5B] = (']', '}'); SC[0x5D] = ('\\', '|')
SC[0x41] = (',', '<'); SC[0x49] = ('.', '>'); SC[0x4A] = ('/', '?')
SC[0x4C] = (';', ':'); SC[0x52] = ("'", '"'); SC[0x4E] = ('-', '_')
SC[0x55] = ('=', '+')

# ============ Tiny-BASIC-Kopplung ============
print("[9] tinybasic import...")
import tinybasic

shift = [False]

def console_out(s):
    """tinybasic out() -> VGA-Zeile B + Serial-Spiegel."""
    parts = [p for p in s.split("\n") if p]
    if parts:
        show(None, parts[-1][:MAX_CHARS])
    print(s, end="")

tinybasic.out = console_out

_last_blink = [0.0]

def bmc_readline(prompt=""):
    """Zeile von der PS/2-Tastatur (VGA-Zeile A, Echo, Cursor)."""
    global cur_a
    line = ""
    shift[0] = False
    show(prompt + "_", None)
    while True:
        if not nirq.value:
            resp = bmc_read(0x40, 9, quiet=True)
            if resp and resp[0] == 0xA0 and resp[1] > 0:
                n_scans = resp[1]
                data = resp[2:2 + n_scans]
                i = 0
                while i < len(data):
                    b = data[i]
                    if b == 0xE0:
                        i += 2
                        continue
                    if b == 0xF0:
                        i += 2
                        continue
                    if b == 0x12 or b == 0x59:
                        shift[0] = True
                        i += 1
                        continue
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
        if (time.monotonic() - _last_blink[0]) > 1.0:
            _last_blink[0] = time.monotonic()
            led.value = not led.value

def ui_tick():
    """Zentraler Renderer: max 1 Write pro 100ms, nur bei Aenderung."""
    global pend, frame
    if not pend:
        return
    t0 = time.monotonic()
    na, nb = pend_a, pend_b
    frame = build_frame(na, nb)
    while len(frame) > WORD_LIMIT and (na or nb):
        if len(nb) > len(na) and nb:
            nb = nb[:-2]
        else:
            na = na[:-2]
        frame = build_frame(na, nb)
    cur_a, cur_b = na, nb
    sm.background_write(loop=frame)
    pend = False
    import gc
    gc.collect()
    print("ui_tick: build+write %d ms, %d Woerter" % ((time.monotonic() - t0) * 1000, len(frame)))

# Shim: tinybasic-Namensraum (Modul-Attr schlaegt Builtin dort)
tinybasic.input = bmc_readline

print("[10] repl()")
print("Tiny-BASIC auf VGA+PS/2. Tipp los!")
try:
    tinybasic.repl()
except KeyboardInterrupt:
    pass
led.value = False
print("Gestoppt.")
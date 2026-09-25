# vga_text_test.py - VGA Textmodus "NEOTRON PICO" (RLE, Inline-Font, LED-Diagnose)
#
# BIOS-Architektur: EINE PIO-SM @150 MHz, GP0..GP13, DMA-Ringpuffer.
#   32-Bit-Woerter: bit0-1 HSYNC/VSYNC (1=idle), bit2-13 RGB, bit14-31 Loop.
#   RLE: Lauf gleicher Farbe = 1 Wort. Zeile exakt 4800 Takte, 525 Zeilen.
# LED-Phasen: 3x kurz = Start, 5x schnell = FEHLER (siehe Serial), danach
#   dauerhaft AN + 1-Blink/s = laeuft.
#
# Beenden: Strg+C. Keine zusaetzlichen Dateien noetig.

import board
import rp2pio
import adafruit_pioasm
import digitalio
import time
import array

# LED zuerst - fuer Crash-Diagnose
led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT

def blink(n, dt=0.12):
    for _ in range(n):
        led.value = True
        time.sleep(dt)
        led.value = False
        time.sleep(dt)

blink(3)
print("Start...")

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

TEXT = "NEOTRON PICO"
TEXT_ROW, TEXT_COL = 2, 8
FG = (15 << 2) | (15 << 6)   # Gelb
BG = 0b1111 << 10            # Blau (Vollbild-Hintergrund, ECO-Schutz)
SCALE = 4   # Font-Pixel = 2 Bildschirmpixel (DMA-Last halbiert)

timing_pio = """
    pull
    out pins, 14
    set x, 0
    out x, 14
period_loop:
    jmp x-- period_loop
"""

try:
    timing_prog = adafruit_pioasm.assemble(timing_pio)
    CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840

    def tw(c_, hl=False, vl=False):
        b0 = 0 if hl else 1
        b1 = 0 if vl else 1
        return (((c_ - 5) << 14) | b0 | (b1 << 1)) & 0xFFFFFFFF

    W_FRONT, W_SYNC, W_BACK = tw(CY_FRONT), tw(CY_SYNC, True), tw(CY_BACK)
    W_BLACK_VIS = tw(CY_VIS)

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

    def build_frame():
        buf = array.array("I")
        for vline in range(480):
            buf.append(W_FRONT)
            buf.append(W_SYNC)
            buf.append(W_BACK)
            if TEXT_ROW * 8 <= vline < (TEXT_ROW + 1) * 8:
                frow = vline - TEXT_ROW * 8
                rc = [BG] * 640
                for ch_idx, ch in enumerate(TEXT):
                    bits = GLYPHS[ord(ch)][frow]
                    base = (TEXT_COL + ch_idx) * 8
                    for px in range(8):
                        col = base + px * SCALE
                        on = FG if ((bits >> px) & 1) else BG
                        for k in range(SCALE):
                            if 0 <= col + k < 640:
                                rc[col + k] = on
                buf.extend(rle_words(rc))
            else:
                buf.append(W_BLACK_VIS)
        for _ in range(10):
            buf.append(W_FRONT); buf.append(W_SYNC); buf.append(W_BACK); buf.append(W_BLANK)
        for _ in range(2):
            buf.append(W_FRONT); buf.append(W_SYNC); buf.append(W_BACK); buf.append(tw(CY_VIS, vsync_low=True))
        for _ in range(33):
            buf.append(W_FRONT); buf.append(W_SYNC); buf.append(W_BACK); buf.append(W_BLANK)
        for _ in range(2):
            buf.append(W_FRONT); buf.append(W_SYNC); buf.append(W_BACK); buf.append(W_BLANK)
        return buf

    print("Baue Frame (RLE)...")
    frame = build_frame()
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
    print("Textmodus aktiv (DMA-Loop, 59,5 Hz).")

    n = 0
    while True:
        time.sleep(1)
        n += 1
        led.value = not led.value
        print("alive", n)
except Exception as e:
    # Crash-Diagnose: 5x schnell blinken + Fehler auf Serial
    print("FEHLER:", repr(e))
    while True:
        blink(5, 0.08)
        time.sleep(1)

# mp_vga_ring.py - VGA 640x480@60 in MicroPython mit DMA-Hardware-Ring
#
# Der Unterschied zu CircuitPython: Der DMA (rp2.DMA) laeuft als
# HARDWARE-RING (ring_size=13, wrap bei 8192 B) - die CPU schlaeft,
# KEIN gc-Jitter, KEIN IRQ. Das Frame-Array = exakt 2048 Woerter.
#
# Zeilen-Plan (2048 Woerter = 512 Zeilen je 4 Woerter):
#   480 sichtbare Zeilen (4 Woerter je Zeile)
#   10 Front-Porch-Zeilen
#    2 VSYNC-Zeilen
#    6 Back-Porch-Zeilen
#   14 W_BLANK-Fuellwoerter (je 4 = 56... 480+10+2+6 = 498 Zeilen
#   = 1992 Woerter + 56 BLANK = 2048 ✓)
import machine
import rp2
import uarray as array
from rp2 import PIO, asm_pio

# ============ PIO-Timing-Programm ============
# Je Wort: [HSYNC, VSYNC, Dauer14] - die Sync-Pegel setzen, X Takte
# warten, naechstes Wort ziehen (der DMA liefert nach).
@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH),
             out_shiftdir=rp2.PIO.SHIFT_LEFT, autopull=False,
             pull_thresh=32, fifo_join=rp2.PIO.JOIN_TX)
def timing_prog():
    pull()
    out(pins, 2)
    out(x, 30)                 # 30 Bit Dauer (bits 2-31)
    label("wait")
    jmp(x_dec, "wait")
    pull()

# Das Timing-Wort: bit0=HSYNC(1=HIGH), bit1=VSYNC, bits 2-31=Dauer
def tw(period, hsync=False, vsync=False):
    return (period << 2) | (0 if hsync else 1) | ((0 if vsync else 1) << 1)

# 150 MHz PIO / 6 = 25 MHz Pixel-Takt (nahe 25.175)
T = lambda px: px * 6
CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = T(16), T(96), T(48), T(640)

W_FRONT = tw(CY_FRONT)
W_SYNC  = tw(CY_SYNC, hsync=True)
W_BACK  = tw(CY_BACK)
W_BLANK = tw(CY_VIS)
W_VSYNC = [tw(CY_FRONT), tw(CY_SYNC, hsync=True, vsync=True),
           tw(CY_BACK, vsync=True), tw(CY_VIS, vsync=True)]

WHITE = (15 << 2) | (15 << 6) | (15 << 10)
BLUE  = 15 << 10

def build_frame(text=None, font=None):
    f = []
    for vline in range(480):
        f.extend((W_FRONT, W_SYNC, W_BACK, W_BLANK))
    for _ in range(10):
        f.extend((W_FRONT, W_SYNC, W_BACK, W_BLANK))
    for _ in range(2):
        f.extend((tw(CY_FRONT), tw(CY_SYNC, True, True),
                  tw(CY_BACK, True, True), tw(CY_VIS, True, True)))
    for _ in range(6):
        f.extend((W_FRONT, W_SYNC, W_BACK, W_BLANK))
    assert len(f) == 498 * 4, len(f)
    while len(f) < 2048:
        f.append(W_BLANK)
    return f

# ============ SM + DMA-Hardware-Ring ============
# Der timing-SM PULLT aus dem TX-FIFO - die DMA schreibt rein.
sm = rp2.StateMachine(0, timing_prog, freq=150_000_000,
                      out_base=0)

frame = array.array("I", build_frame())
print("Frame:", len(frame), "Woerter =", len(frame) * 4, "Bytes")

# Der DMA: ring_size=13 = Wrap bei 8192 B (2048 Woerter) im
# READ-Adresszeiger - der Ring laeuft OHNE CPU, OHNE IRQ!
# treq_sel = 0 (PIO0-SM0-TX-Request): die DMA pusht nur, wenn
# der SM pullt (kein FIFO-Overflow).
d = rp2.DMA()
c = d.pack_ctrl(inc_write=False, ring_size=13, ring_sel=False,
                treq_sel=0)
d.config(read=frame, write=sm, count=0xFFFFFFFF, ctrl=c, trigger=True)
print("DMA-Ring laeuft - CPU frei!")

# Text-Aenderung: IN-PLACE im laufenden Ring (der DMA liest
# direkt aus dem array - die Aenderung greift im naechsten
# Frame-Durchlauf automatisch):
def patch(row_frame, words):
    off = row_frame
    for i, w in enumerate(words):
        frame[off + i] = w

# mem32-RING-TEST: Der VGA-Timing-SM KOMPLETT via Register
# (PIO0 = 0x50200000, CTRL = 0x00, INSTR_MEM = 0x48) - die MP-
# Firmware-API wird komplett umgangen. Der put()-Feed schiebt die
# roten Beweis-Woerter.
from machine import mem32, freq
import rp2
import time
freq(150_000_000)

PIO0 = 0x50200000
RESETS = 0x40020000
IO_BANK0 = 0x40028000
PADS_BANK0 = 0x40038000

# 1. GPIO21 (nOUTPUT_EN) via Register: FUNCSEL=5 (SIO), Pad ISO=0:
mem32[IO_BANK0 + 4 + 8 * 21] = 5     # FUNCSEL=5 (SIO)
mem32[PADS_BANK0 + 4 + 4 * 21] = 0x52
mem32[0xD0000010] |= (1 << 21)       # SIO GPIO_OUT_SET bit21
mem32[0xD0000038] |= (1 << 21)       # SIO GPIO_OE_SET bit21
print("GP21 nOUTPUT_EN HIGH (Register-Weg)")

# 2. Die 14 VGA-Pins auf PIO0 (FUNCSEL=6):
for pin in range(14):
    mem32[IO_BANK0 + 4 + 8 * pin] = 6
print("14 Pins -> PIO0")

# 3. Der PIO-Programm (5 Instr) an Offset 0:
for i, w in enumerate([0x80A0, 0x600E, 0xE020, 0x602E, 0x0044]):
    mem32[PIO0 + 0x48 + 4 * i] = w

# 4. Die SM0-Config (exakt der Beweis-Code):
mem32[PIO0 + 0xC8] = 0x00010000   # CLKDIV = 1.0 (150 MHz)
mem32[PIO0 + 0xCC] = 0x00004000   # EXECCTRL: wrap_top=4 (5 Instr)
mem32[PIO0 + 0xD0] = 0x00080000   # SHIFTCTRL: out-right, no autopull
mem32[PIO0 + 0xDC] = 0x00E00000   # PINCTRL: out_base=0, count=14

# 5. Der SM-START (CTRL: bit0 = SM0-Enable):
mem32[PIO0 + 0x00] = 1
print("SM0 via Register gestartet - put-Feed ROT")

def word(cycles, hsync_low=False, vsync_low=False, color=0):
    b0 = 0 if hsync_low else 1
    b1 = 0 if vsync_low else 1
    return (((cycles - 5) << 14) | color | b0 | (b1 << 1)) & 0xFFFFFFFF

CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840
RED = 0b1111 << 2
W_FRONT = word(CY_FRONT)
W_SYNC = word(CY_SYNC, hsync_low=True)
W_BACK = word(CY_BACK)
W_VIS_RED = word(CY_VIS, color=RED)
W_BLANK = word(CY_VIS)

def put(w):
    # TX-FIFO-Write via Register: PIO0-TXF0 = 0x50200010 (FIFO):
    # Der PIO-TXF-Layout: TXF0 = 0x50200010? Der pio.h:
    # TXF0-3: 0x10-0x1C (je PIO-SM-Index):
    mem32[PIO0 + 0x10] = w & 0xFFFFFFFF   # TXF0 (SM0)

n = 0
try:
    while True:
        for _ in range(480):
            for w in (W_FRONT, W_SYNC, W_BACK, W_VIS_RED):
                put(w)
        for _ in range(10):
            for w in (W_FRONT, W_SYNC, W_BACK, W_BLANK):
                put(w)
        for _ in range(2):
            for w in (word(CY_FRONT, vsync_low=True),
                      word(CY_SYNC, True, True),
                      word(CY_BACK, vsync_low=True),
                      word(CY_VIS, vsync_low=True)):
                put(w)
        for _ in range(33):
            for w in (W_FRONT, W_SYNC, W_BACK, W_BLANK):
                put(w)
        n += 1
        if n % 30 == 0:
            print("Frames:", n)
except KeyboardInterrupt:
    print("Frames:", n)

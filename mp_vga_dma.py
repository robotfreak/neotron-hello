# mp_vga_timing.py - VGA 640x480@60 in MicroPython
# Architektur (BIOS-nachgebaut): 2 PIO-SMs + 2 DMA-Kanaele mit
# CHAIN_TO-Ring - die CPU schlaeft, kein IRQ, kein Jitter!
#
# Timing-SM (GP0=HSYNC, GP1=VSYNC): schiebt 2 Bit je Wort
# Pixel-SM (GP2-13): 12 Bit Farbe je Wort (R-2R)
# Die Frame-Woerter: je Zeile 4 Woerter (Front/Sync/Back/Vis)
# im Timing-SM + die Pixel-Daten im Pixel-SM.
import machine
import rp2
from rp2 import PIO, StateMachine, asm_pio
import uarray as array

@asm_pio(out_init=(PIO.OUT_HIGH, PIO.OUT_HIGH), out_shiftdir=PIO.SHIFT_LEFT,
         autopull=False, pull_thresh=32)
def timing_prog():
    pull()                    # HSYNC/VSYNC-Wort (2 Bit + Dauer in X)
    out(pins, 2)              # Sync-Pegel setzen
    out(x, 14)                # Dauer nach X
    label("wait")
    jmp(x_dec, "wait")        # X Takte warten (150 MHz!)
    pull()                    # naechstes Sync-Wort

# Das Timing-Wort: bit0=HSYNC, bit1=VSYNC, bit2-15=Dauer
# (BIOS: value = (period - 5) << 14 | sync-Bits)
# 640x480@60: Front 16px=96 Tak, Sync 96px=576, Back 48px=288, Vis 640px=3840
# PIO bei 150 MHz: Takte je Pixel = 6? NEIN: 25.175 MHz Pixel = 150/6
# -> Pixel-SM mit out pins,12 [5] = 6 Takte je Pixel.
# Timing-SM je Wort: 1 pull + 1 out(2) + 1 out(14) + X dec + jmp = ~X+4
# Takte - die Dauer X muss die PERIODE sein (minus Overhead).
def tw(period_cycles, hsync=False, vsync=False):
    # HSYNC/VSYNC = LOW-aktiv: bit0/bit1 = 0 wenn LOW
    return (period_cycles << 2) | (0 if hsync else 1) | (0 if vsync else 1) << 1

# 150 MHz / 6 = 25 MHz Pixel-Takt (nahe 25.175 - der Monitor lockt!)
T = lambda px: px * 6   # Takte je Pixel-Zeile-Teil

CY_FRONT = T(16)
CY_SYNC = T(96)
CY_BACK = T(48)
CY_VIS = T(640)

def line_words(color=0, vsync=False):
    return [tw(CY_FRONT, False, False),
            tw(CY_SYNC, True, vsync),
            tw(CY_BACK, False, vsync),
            tw(CY_VIS, False, vsync)]

# ============ Pixel-SM (GP2-13, 12 Bit R-2R) ============
@asm_pio(out_init=0x3FFC << 16, out_shiftdir=PIO.SHIFT_LEFT,
         pull_thresh=32)
def pixel_prog():
    out(pins, 12)             # 12 Bit Farbe (GP2-13)
    nop() [4]                 # 6 Takte je Pixel (150MHz/25MHz)

# Der DMA-Ring (MicroPython rp2.DMA, chain_to):
# timing_dma: laedt das Timing-Wort-Array (loop, 525*4 Woerter)
# pixel_dma: laedt die Pixel-Zeile (640 Woerter je Zeile)
# chain_to: timing_dma -> pixel_dma -> timing_dma (Ring!)

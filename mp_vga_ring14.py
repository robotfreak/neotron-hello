# mp_vga_ring14.py - MicroPython mit dem BEWIESENEN CP-PIO-Programm
# (14 Pins je Wort: bits0-1 Sync + bits2-13 Farbe + bits14-27 Dauer)
from machine import Pin, freq
import rp2
import uarray as array
import time

freq(150_000_000)
Pin(21, Pin.OUT).value(1)   # nOUTPUT_EN HIGH

# EXAKT das laufende CP-PIO-Programm:
@rp2.asm_pio(out_init=0x3FFF, out_shiftdir=rp2.PIO.SHIFT_RIGHT,
             autopull=False, pull_thresh=32)
def timing_prog():
    pull()
    out(pins, 14)
    set(x, 0)
    out(x, 14)
    label("period_loop")
    jmp(x_dec, "period_loop")

# Das Wort-Format (CP-Beweis): bit0=HSYNC, bit1=VSYNC, bits2-13=RGB,
# bits14-27=Dauer-1 (der 'jmp x--' macht Dauer+1 Iterationen)
def word(cycles, hsync=False, vsync=False, color=0):
    b0 = 0 if hsync else 1
    b1 = 0 if vsync else 1
    return (((cycles - 1) << 14) | (color << 2) | b0 | (b1 << 1)) & 0xFFFFFFFF

CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840
W_FRONT = word(CY_FRONT)
W_SYNC  = word(CY_SYNC, hsync=True)
W_BACK  = word(CY_BACK)
W_BLANK = word(CY_VIS)

def build_frame():
    f = []
    for vline in range(480):
        f.extend((W_FRONT, W_SYNC, W_BACK, word(CY_VIS, color=0x3FFC >> 2)))
    for _ in range(10):
        f.extend((W_FRONT, W_SYNC, W_BACK, W_BLANK))
    for _ in range(2):
        f.extend((word(CY_FRONT), word(CY_SYNC, True, True),
                  word(CY_BACK, True, True), word(CY_VIS, True, True)))
    for _ in range(6):
        f.extend((W_FRONT, W_SYNC, W_BACK, W_BLANK))
    # Auf 2048 auffuellen (Ring!):
    while len(f) < 2048:
        f.append(W_BLANK)
    return f

frame = array.array("I", build_frame())
print("Frame:", len(frame), "=", len(frame) * 4, "Bytes")

sm = rp2.StateMachine(0, timing_prog, freq=150_000_000, out_base=0,
                      set_base=0)
d = rp2.DMA()
c = d.pack_ctrl(inc_write=False, ring_size=13, ring_sel=False, treq_sel=0)
d.config(read=frame, write=sm, count=0xFFFFFFFF, ctrl=c, trigger=True)
print("DMA-Ring laeuft (14-Pin-CP-Programm)")

led = Pin(25, Pin.OUT)
n = 0
while True:
    led.toggle()
    n += 1
    time.sleep(1)

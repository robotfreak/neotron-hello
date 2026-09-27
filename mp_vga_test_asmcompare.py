# ASM-STRUKTUR: Das komplette Decorator-Programm-Tuple drucken
from machine import Pin
import rp2
Pin(25, Pin.OUT)

@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH,) * 14,
             out_shiftdir=rp2.PIO.SHIFT_RIGHT,
             autopull=False, pull_thresh=32)
def timing_prog():
    pull()
    out(pins, 14)
    set(x, 0)
    out(x, 14)
    label("period_loop")
    jmp(x_dec, "period_loop")

prog = timing_prog
print("Typ:", type(prog), "Laenge:", len(prog))
for i, v in enumerate(prog):
    print("[%d]" % i, repr(v))

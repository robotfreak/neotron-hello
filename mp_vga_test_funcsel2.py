# FUNCSEL-BEWEIS 2.0: Die RICHTIGE IO_BANK0-Adresse (0x40028000,
# pico-sdk-Quelle verifiziert): GPIO0_STATUS = Basis+0,
# GPIO0_CTRL = Basis+4 (OETOPAD bit13, OUTTOPAD bit9, FUNCSEL bits0-4)
from machine import mem32, freq
import rp2
import time
freq(150_000_000)

def gp0_state(tag):
    st = mem32[0x40028000]        # GPIO0_STATUS
    ct = mem32[0x40028004]        # GPIO0_CTRL
    oe = (st >> 13) & 1           # OETOPAD
    out = (st >> 9) & 1           # OUTTOPAD
    fs = (ct >> 0) & 0x1F         # FUNCSEL (6=PIO0, 5=SIO)
    print(tag, "| FUNCSEL:", fs, "| OETOPAD:", oe, "| OUTTOPAD:", out,
          "| IN:", (mem32[0xD0000004] >> 0) & 1)

print("--- VOR dem PIO-Start ---")
gp0_state("VOR ")

@rp2.asm_pio(out_init=rp2.PIO.OUT_HIGH, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def out0_prog():
    pull()
    out(pins, 1)
    pull()
    out(pins, 1)

sm = rp2.StateMachine(0, out0_prog, freq=150_000_000, out_base=0)
sm.active(1)
print("--- NACH dem PIO-Start ---")
gp0_state("NACH")
print("--- put(1) ---")
sm.put(1)
time.sleep(0.3)
gp0_state("HIGH")
print("--- put(0) ---")
sm.put(0)
time.sleep(0.3)
gp0_state("LOW ")
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

# FUNCSEL-BEWEIS: Welche Funktion hat GP0? (GPIO0_CTRL bits0-4)
# RP2350-FUNCSEL: 6 = PIO0, 7 = PIO1, 8 = PIO2, 5 = SIO, 0 = JTAG?
# IO_BANK0-Basis RP2350: 0x40084000 (GPIO0_CTRL = Basis+4)
from machine import mem32, freq
import rp2
import time
freq(150_000_000)

print("--- VOR dem PIO-Start ---")
st = mem32[0x40084004]
print("GPIO0_CTRL: 0x%08X | FUNCSEL:", st, (st >> 0) & 0x1F)

@rp2.asm_pio(out_init=rp2.PIO.OUT_HIGH, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def out0_prog():
    pull()
    out(pins, 1)
    pull()
    out(pins, 1)

sm = rp2.StateMachine(0, out0_prog, freq=150_000_000, out_base=0)
sm.active(1)
print("--- NACH dem PIO-Start ---")
st = mem32[0x40084004]
print("GPIO0_CTRL: 0x%08X | FUNCSEL:" % st, (st >> 0) & 0x1F, "(6=PIO0?)")
sm.put(1)
time.sleep(0.5)
# Der Pad-OE-Status: Der GPIO-Status-Register: RP2350 IO_BANK0:
# Der STATUS-Register: 0x40084000 (GPIO0_STATUS):
st2 = mem32[0x40084000]
print("GPIO0_STATUS: 0x%08X" % st2, "| OETOPAD(bit13):", (st2 >> 13) & 1,
      "| OUTTOPAD(bit9):", (st2 >> 9) & 1)
print("alive-Loop...")
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

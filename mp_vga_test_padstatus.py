# PAD-OE-BEWEIS: Der effektive Pad-Output-Enable via GPIO0_STATUS
# (RP2350: IO_BANK0 = 0x40084000, GPIO0_STATUS = Basis, bit13=OETOPAD,
# bit17=INFROMPERI) + der Pad-Wert via SIO_GPIO_IN
from machine import mem32, freq
import rp2
import time
freq(150_000_000)

@rp2.asm_pio(out_init=rp2.PIO.OUT_HIGH, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def out0_prog():
    pull()
    out(pins, 1)
    pull()
    out(pins, 1)

sm = rp2.StateMachine(0, out0_prog, freq=150_000_000, out_base=0)
sm.active(1)
print("GP0: put(1) -> HIGH...")
sm.put(1)
time.sleep(0.5)
st = mem32[0x40084000]
in1 = (mem32[0xD0000004] >> 0) & 1
print("GPIO0_STATUS: 0x%08X" % st, "| OETOPAD(bit13):", (st >> 13) & 1, "| IN:", in1)
sm.put(0)
time.sleep(0.5)
st = mem32[0x40084000]
in2 = (mem32[0xD0000004] >> 0) & 1
print("GPIO0_STATUS: 0x%08X" % st, "| OETOPAD(bit13):", (st >> 13) & 1, "| IN:", in2)
sm.put(1)
time.sleep(0.5)
st = mem32[0x40084000]
in3 = (mem32[0xD0000004] >> 0) & 1
print("GPIO0_STATUS: 0x%08X" % st, "| OETOPAD(bit13):", (st >> 13) & 1, "| IN:", in3)
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

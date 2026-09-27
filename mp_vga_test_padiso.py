# PAD-ISO-BEWEIS: Der Pad-Register (PADS_BANK0 0x40038000,
# GPIO0-Pad = Basis+4): ISO (bit8) = Pad-Isolation!
# Der CircuitPython-Code setzt ISO=0, MicroPython evtl. nicht.
from machine import mem32, freq
import rp2
import time
freq(150_000_000)

def pad_state(tag):
    v = mem32[0x40038004]   # PADS_BANK0_GPIO0
    print(tag, "| Pad-Reg: 0x%08X" % v, "| ISO(bit8):", (v >> 8) & 1,
          "| IE(bit6):", (v >> 6) & 1, "| PDE(bit2):", (v >> 2) & 1,
          "| DRIVE:", (v >> 4) & 0x3)

print("--- VOR dem PIO ---")
pad_state("VOR ")

@rp2.asm_pio(out_init=rp2.PIO.OUT_HIGH, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def out0_prog():
    pull()
    out(pins, 1)
    pull()
    out(pins, 1)

sm = rp2.StateMachine(0, out0_prog, freq=150_000_000, out_base=0)
sm.active(1)
print("--- NACH dem PIO ---")
pad_state("NACH")
# Die ALLE 14 VGA-Pins:
print("--- Pad-ISO aller 14 VGA-Pins (GP0-13) ---")
iso_pins = []
for pin in range(14):
    v = mem32[0x40038004 + 4 * pin]
    if (v >> 8) & 1:
        iso_pins.append(pin)
print("ISO=1 (isoliert) Pins:", iso_pins if iso_pins else "KEINE - alle aktiv")
n = 0
while True:
    time.sleep(1)
    n += 1
    print("alive", n)

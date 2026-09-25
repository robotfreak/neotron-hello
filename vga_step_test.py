# vga_step_test.py - Phasen-Test: Farb-Ref -> Blau-Vollbild -> Blau+Text-RLE
# Je Phase 12 s, Serial meldet die Phase. LED blinkt durchgehend 1x/s.
# Beobachtung pro Phase: Monitor-Sync? Bildinhalt?
#  - Phase A muss Sync + ROT zeigen (Beweis-Referenz)
#  - Phase B: Blau (wie A, nur Farbe anders)
#  - Phase C: Blau + gelber Text oben links (RLE-Woerter aktiv)
# Das isoliert: A ok aber B/C nicht -> DMA-Rate/Wortdaten
#                              B ok, C nicht -> RLE-Rate ist das Problem
#                              A schon nicht -> Hardware/Setup-Problem

import board
import rp2pio
import adafruit_pioasm
import digitalio
import time
import array

led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT
led.value = True
print("Step-Test...")

timing_pio = """
    pull
    out pins, 14
    set x, 0
    out x, 14
period_loop:
    jmp x-- period_loop
"""
timing_prog = adafruit_pioasm.assemble(timing_pio)

def tw(c_, hl=False, vl=False):
    b0 = 0 if hl else 1
    b1 = 0 if vl else 1
    return (((c_ - 5) << 14) | b0 | (b1 << 1)) & 0xFFFFFFFF

CY_FRONT, CY_SYNC, CY_BACK, CY_VIS = 96, 576, 288, 3840
RED = 15 << 2
BLUE = 15 << 10
YELLOW = (15 << 2) | (15 << 6)

def build_frame(vis_color, text_line=False):
    frame = array.array("I")
    W_FRONT = tw(CY_FRONT)
    W_SYNC = tw(CY_SYNC, True)
    W_BACK = tw(CY_BACK)
    W_VIS = tw(CY_VIS) | vis_color
    W_BLANK = tw(CY_VIS)
    for vline in range(480):
        frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BACK)
        if text_line and 16 <= vline < 24:
            # RLE-Textzeile: 64px schwarz, "NEOTRON PICO" gelb auf schwarz,
            # Rest schwarz - RLE:
            # (vereinfacht: wir malen 3 gelbe Bloecke als Text-Proxy)
            runs = [(64, 0), (8, YELLOW), (16, 0), (8, YELLOW), (536, 0)]
            for n_px, col in runs:
                frame.append((((n_px * 6 - 5) << 14) | col) & 0xFFFFFFFF)
        else:
            frame.append(W_VIS)
    for _ in range(10):
        frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BLANK)
    for _ in range(2):
        frame.append(W_FRONT); frame.append(W_SYNC); frame.append(tw(CY_VIS, vl=True))
    for _ in range(33):
        frame.append(W_FRONT); frame.append(W_SYNC); frame.append(W_BLANK)
    return frame

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

print("Phase A: VOLLES ROT (Beweis-Referenz) - 10 s")
frameA = build_frame(RED)
sm.background_write(loop=frameA)
time.sleep(10)

print("Phase B: VOLLES BLAU - 10 s")
frameB = build_frame(BLUE)
sm.background_write(loop=frameB)
time.sleep(10)

print("Phase C: BLAU + gelbe Bloecke oben (RLE) - 10 s")
frameC = build_frame(BLUE, text_line=True)
sm.background_write(loop=frameC)
time.sleep(10)

print("Phase D: BLAU + echtes RLE-Textzeilen-Muster - 10 s")
# Zeile 16: abwechselnd gelb/blau im 8-Pixel-Takt (RLE-Raten-Test)
frameD = array.array("I")
for vline in range(480):
    frameD.append(tw(96)); frameD.append(tw(576, True)); frameD.append(tw(288))
    if 16 <= vline < 24:
        # RLE: 40 Wechsel a 16 px = 640
        for i in range(40):
            col = YELLOW if (i % 2 == 0) else BLUE
            frameD.append((((16 * 6 - 5) << 14) | col) & 0xFFFFFFFF)
    else:
        frameD.append(tw(CY_VIS) | BLUE)
for _ in range(10):
    frameD.append(tw(96)); frameD.append(tw(576, True)); frameD.append(tw(CY_VIS))
for _ in range(2):
    frameD.append(tw(96)); frameD.append(tw(576, True)); frameD.append(tw(CY_VIS, vl=True))
for _ in range(33):
    frameD.append(tw(96)); frameD.append(tw(576, True)); frameD.append(tw(CY_VIS))
print("Phase D: Streifen-RLE (16-px-Runs) - 10 s")
sm.background_write(loop=frameD)
time.sleep(10)

print("Fertig. Beobachtungen an Hermes melden!")
print("A:", "ROT?" , " B:", "BLAU?", " C:", "Bloecke?", " D:", "Streifen?")
n = 0
while True:
    time.sleep(1)
    n += 1
    led.value = not led.value

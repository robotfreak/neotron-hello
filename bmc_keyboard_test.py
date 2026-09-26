# bmc_keyboard_test.py - PS/2-Tastatur ueber BMC-SPI (Neotron-Pico)
#
# Protokoll (aus Neotron-BIOS main.rs + neotron-bmc-protocol):
#   SPI: GP18=CLK, GP19=COPI(MOSI), GP16=CIPO(MISO), GP17=nSPI_CS_IO (LOW=aktiv),
#   BMC-Clock = 2 MHz, MSB first, Mode 0.
#   Request (4 Bytes): [TYPE, REGISTER, LEN/DATA, CRC8(poly 0x07, init 0)]
#     Read      = 0xC0 / Alt 0xC1
#     ShortWrite= 0xC2 / Alt 0xC3
#   Response: [RESULT(0xA0=OK), DATA..., CRC8] - BMC braucht ~6us Reaktionszeit,
#     BIOS pollt bis zu 128x mit 0xFF-Clock-Woertern bis RESULT-Byte kommt.
#   PS/2-Keyboard-FIFO = Register 0x40: Read liefert [len, data0..data7].
#   Alt-Flag muss pro Request flippen (UseAlt-Toggle, BIOS-Verhalten).
#
# Dieser Test: Initialisierung (Interrupt-Enable + IRQ-Pin GP20), dann
#   endloses Pollen von Register 0x40 - gedrueckte Tasten erscheinen als
#   PS/2-Scancodes auf der Serial-Konsole (Hex).
#
# Als code.py auf CIRCUITPY (mit Tastatur an PS/2-Port 1). LED blinkt.

import board
import busio
import digitalio
import time
import microcontroller

# --- CRC-8 (Poly 0x07, init 0x00, nicht reflektiert) ---
def crc8(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

# --- SPI + CS ---
spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
while not spi.try_lock():
    pass
spi.configure(baudrate=2_000_000, polarity=0, phase=0, bits=8)
cs = digitalio.DigitalInOut(board.GP17)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True  # nSPI_CS_IO: HIGH = MCP/BMC nicht selektiert

# GP21 nOUTPUT_EN: MUSS LOW sein damit BMC-CS-Durchschaltung aktiv!
# (BIOS: drive_cs_lines() setzt noutput_en LOW, release setzt HIGH)
noutput_en = digitalio.DigitalInOut(board.GP21)
noutput_en.direction = digitalio.Direction.OUTPUT
noutput_en.value = True  # Start hochohmig, nur waehrend Transfers LOW

# GP20 = nIRQ_IO (Interrupt-Input vom MCP23S17)
nirq = digitalio.DigitalInOut(board.GP20)
nirq.direction = digitalio.Direction.INPUT
nirq.pull = digitalio.Pull.UP

# LED
led = digitalio.DigitalInOut(board.GP25)
led.direction = digitalio.Direction.OUTPUT
led.value = True

use_alt = False
buf1 = bytearray(1)

def bmc_transfer(req_bytes, response_len):
    """Request senden, Antwort lesen (BIOS-Protokoll)."""
    global use_alt
    cs.value = False
    try:
        spi.write(req_bytes)
        # Antwort-Clock: BIOS pollt bis 128x mit Delay 6us
        buf = bytearray(response_len)
        result = None
        for retry in range(128):
            microcontroller.delay_us(6)
            spi.readinto(buf1)
            if buf1[0] in (0xA0, 0xA1, 0xA2, 0xA3, 0xA4):
                result = buf1[0]
                break
            # sonst: 0xFF-Clock, weiterschieben
        if result is None:
            return None
        # Rest der Antwort (incl. CRC) lesen
        rest = bytearray(response_len - 1)
        spi.readinto(rest)
        return bytes([buf1[0]]) + bytes(rest)
    finally:
        cs.value = True

def bmc_read(register, length):
    global use_alt
    t = 0xC1 if use_alt else 0xC0
    use_alt = not use_alt
    req = bytes([t, register, length])
    req += bytes([crc8(req)])
    return bmc_transfer(req, length + 2)

def mcp23s17_write(reg, value):
    """Direkt an MCP23S17 (nSPI_CS_IO = GP17, Opcode 0x40 = Write)."""
    cs.value = False
    try:
        spi.write(bytes([0x40, reg, value]))
    finally:
        cs.value = True

print("BMC-Tastatur-Test: Initialisiere...")

# WICHTIG: Vor BMC-Zugriff muss der MCP23S17 so konfiguriert sein, dass
# der 74HC138-Decoder CS0 (BMC) am richtigen Pin ausgibt.
# BIOS: GPIOA = led_state << 3 | cs (cs=0 fuer BMC)
# Hier: GPIOA = 0x00 (alle CS auf 0, kein LED-Bit), noutput_en LOW waehrend Transfer
# MCP23S17 konfigurieren: GPIOA = CS/LED-Ausgaenge (0x00), GPIOB = IRQ-Inputs
mcp23s17_write(0x00, 0x00)   # IODIRA = alle Output
mcp23s17_write(0x01, 0xFF)   # IODIRB = alle Inputs
mcp23s17_write(0x12, 0x00)   # GPIOA = 0 (led_state 0, cs 0 -> BMC-CS aktiv bei noutput_en LOW)
mcp23s17_write(0x14, 0x00)   # GPPUA = keine Pullups
mcp23s17_write(0x15, 0xFF)   # GPPUB = Pullups an IRQ-Leitungen
print("MCP23S17 konfiguriert (GPIOA out, GPIOB in + Pullup)")
print("Teste BMC-Kommunikation (Firmware-Version, Register 0x01, len 32)...")
for attempt in range(3):
    resp = bmc_read(0x01, 32)
    if resp and resp[0] == 0xA0:
        print("BMC Antwort OK! Version:", resp[1:-1].replace(b"\x00", b"").decode(errors="ignore"))
        break
    print("Versuch", attempt + 1, "fehlgeschlagen:", resp)
else:
    print("BMC antwortet nicht - Verkabelung/Power pruefen.")

print("Polling PS/2-Keyboard-FIFO (Register 0x40)...")
n = 0
try:
    while True:
        # IRQ-Leitung pruefen (LOW = pending)
        if nirq.value == False:
            resp = bmc_read(0x40, 9)
            if resp and resp[0] == 0xA0 and resp[1] > 0:
                n_scans = resp[1]
                print("Scancodes:", resp[2:2 + n_scans].hex())
        time.sleep(0.05)
        n += 1
        if n % 20 == 0:
            led.value = not led.value
except KeyboardInterrupt:
    led.value = False
    cs.value = True
    print("Gestoppt.")
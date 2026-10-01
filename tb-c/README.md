# TinyBASIC-C-Port (Workshop "Programmieren wie in die 80er")

Feather RP2350 + DispHSTX (Panda381/Nemecek) + PS/2-Tastatur.
Der BASIC-Interpreter ist ein 1:1-C-Port des Python-tinybasic.py
(20/20 Host-Tests bestanden).

## Struktur
- `src/basic.h`  - Interpreter (Tokenizer/Expr/Statements/REPL, header-only)
- `src/fat16.h`  - Mini-FAT16/FAT32 (MBR/Boot/Root/Cluster, Block-I/O via Hook)
- `src/sdspi.h`  - SD-Karte via SPI (CMD0/CMD8/ACMD41, CSD, 512-B-Blocks)
- `src/main.cpp` - ATEXT-Textmodus 80x30 + PS/2 + Line-Editor + REPL + SD-Mount
- `tests/tbtest.c`   - BASIC-Host-Tests (gcc, 22 Tests: 20 Basic + SAVE/LOAD)
- `tests/fat16test.c`- FAT-Host-Tests (RAM-Disk, 20 Tests)

## Host-Tests (pi)
    cd tests
    gcc -o tbtest tbtest.c && ./tbtest

## Board-Build (pi)
Build braucht PicoLibSDK-Klon + DispHSTX-Header (siehe DispHSTX-Setup
im Workshop-Log / README der TEXTDEMO-Umgebung):
    bash c.sh pico2   # im DispHSTX/Pico/DispHSTX/TEXTDEMO-Kontext

## Beweis-Stand (2026-09-29)
- DVI-Bild (HSTX GP12-19, Adafruit-HDMI-Adapter) ✅
- ATEXT 80x30 CGA-Farben (COLOR16(G,B,R)-Rotation, char/attr interleaved) ✅
- PS/2 Set-2 UK (GP0=CLK, GP1=DAT; l=0x4B ;=0x4C '=0x52 1=0x16) ✅
- 22/22 BASIC-Host-Tests (+ SAVE/LOAD, LOAD-Fehlerpfad) ✅
- 20/20 FAT16-Host-Tests (RAM-Disk: mkfs/read/write/delete) ✅
- SD-Card am Board ✅ ("SD: OK", SDHC 4GB erkannt, Sektoren via CSD)
- SAVE "N" / LOAD "N" live am Board (8.3-Namen, .BAS im Root, am PC lesbar) ✅

## SD-Fallen (bewiesen durch Debug)
- CMD8-CRC ist 0x87 (nicht 0x95) - sonst ignoriert die Karte CMD8.
- CMD8-Echo sind GENAU 4 Bytes nach R1 (00 00 01 AA) - Dummy-Bytes
  vor dem Echo lesen verschiebt die Pruefung -> Karte gilt als SDv1
  -> ACMD41 ohne HCS -> SDHC bleibt ewig "idle" (ACMD41=0x01).
- ACMD41 fuer SDHC mit Arg 0x40000000 (HCS-Bit) - sonst kein Ready.
- Diagnose-Trick: R1 von CMD0/CMD8/ACMD41 + Loop-Count in die
  Statuszeile drucken (Zeile 2) - hat den Fehler sofort gezeigt.

## Bekannte Fallen
- `GPIO_Init` (FUNCSEL=SIO) muss vor JEDEM GPIO-Output gerufen werden,
  sonst bleibt der Pad im Reset-Funcsel "None" = Output wirkt nicht.
- Pins NICHT massenweise initialisieren (Boot-Crash beim Feather).
- PS/2: das Break-Flag (`0xF0`-Prefix) muss bis zum Release-Code leben,
  sonst werden Release-Codes als Press erkannt (doppelte Zeichen).
- Scancode 0x0F ist F1 — die Zifferntaste '1' ist 0x16!

## Offen
- WiFi-Phase 2 (Pico 2W: Telnet/Remote-BASIC, BBS-Mailbox) - eigenes Projekt
- Neotron-PCB-HSTX→VGA-Adapter (spätere PCB-Rev)

## Pico 2W-Port (bewiesen am Board, 30.09.2026)
Umstieg Feather RP2350 → Pico 2W (Lochraster-Aufbau):
- **SD-MOSI GP23→GP3** (GP23-29 intern am CYW43; funcsel-Tabelle bewies:
  GP3=spi0_tx funcsel 1). CS=GP5, SCK=GP22, MISO=GP20 bleiben.
- Onboard-LED hängt am CYW43 (WL_GPIO0), nicht an einem RP-GPIO — ohne
  CYW43-Treiber (PicoLibSDK hat keinen) unbenutzbar. Externe LED an GP7.
- ATEXT 80x30 + PS/2 (GP0/GP1) + SD (SPI0) + SAVE/LOAD: alles bewiesen ✅
- HDMI-Pin-Reihenfolge (DVI-breakout config 0): GP12=D0+, GP13=D0-,
  GP14=CLK+, GP15=CLK-, GP16=D2+, GP17=D2-, GP18=D1+, GP19=D1-.
  NICHT die Picopad-Reihenfolge (die hat CLK an 12/13)!
- USB-CDC-Diagnose: `UsbPrint` droppt still, wenn kein Host-CDC mounted;
  PC-USB-Stau kann ttyACM0 killen (PC-Restart nötig) — Diagnose-Firmware
  mit USB zuerst gegen die Minimal-Firmware (BOOTDIAG) testen.

## Beispiele (beispiele/)
Alle getestet gegen die Host-Suite (tbex, 10/10 ok):
- `zaehlen.bas` — FOR/NEXT-Zählschleife (erste Schritte)
- `quadrate.bas` — Quadrattabelle, PRINT mit Semikolon
- `gauss.bas` — Summe 1..100 (Akkumulator)
- `schach.bas` — CLS + Schleife
- `sterne.bas` — geschachtelte FOR (Treppe)
- `tabelle.bas` — INPUT + Multiplikationstabelle
- `bahn.bas` — Formatierung mit String-Feldern
- `raten.bas` — Spiel: RND/INPUT/IF/GOTO (Zahlenraten 1-100)

Namen ≤ 8 Zeichen = SD-Card-8.3-kompatibel (SAVE/LOAD "name").

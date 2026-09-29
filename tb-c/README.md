# TinyBASIC-C-Port (Workshop "Programmieren wie in die 80er")

Feather RP2350 + DispHSTX (Panda381/Nemecek) + PS/2-Tastatur.
Der BASIC-Interpreter ist ein 1:1-C-Port des Python-tinybasic.py
(20/20 Host-Tests bestanden).

## Struktur
- `src/basic.h`  - Interpreter (Tokenizer/Expr/Statements/REPL, header-only)
- `src/main.cpp` - ATEXT-Textmodus 80x30 + PS/2-Treiber + Line-Editor + REPL
- `tests/tbtest.c` - Host-Test-Suite (gcc, 20 Tests)

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
- 20/20 Host-Tests + RUN/LIST/NEW live auf dem Monitor ✅

## Bekannte Fallen
- `GPIO_Init` (FUNCSEL=SIO) muss vor JEDEM GPIO-Output gerufen werden,
  sonst bleibt der Pad im Reset-Funcsel "None" = Output wirkt nicht.
- Pins NICHT massenweise initialisieren (Boot-Crash beim Feather).
- PS/2: das Break-Flag (`0xF0`-Prefix) muss bis zum Release-Code leben,
  sonst werden Release-Codes als Press erkannt (doppelte Zeichen).
- Scancode 0x0F ist F1 — die Zifferntaste '1' ist 0x16!

## Offen
- SD-Card (SAVE/LOAD im BASIC)
- Workshop-Phase (Beispielprogramme + Bedienanleitung)

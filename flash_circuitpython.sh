#!/bin/bash
# Flash-Skript fuer Neotron Pico: CircuitPython auf den Pico kopieren
# Usage: ./flash_circuitpython.sh [pfad-zur-uf2]

set -e

UF2="${1:-$HOME/Downloads/adafruit-circuitpython-raspberry_pi_pico-en_US-10.3.1.uf2}"

if [ ! -f "$UF2" ]; then
    echo "FEHLER: UF2 nicht gefunden: $UF2"
    exit 1
fi

# Auf RPI-RP2 Bootloader-Laufwerk warten
MOUNT=""
for i in $(seq 1 20); do
    if [ -d /media/pi/RPI-RP2 ]; then
        MOUNT=/media/pi/RPI-RP2
        break
    fi
    sleep 0.5
done

if [ -z "$MOUNT" ]; then
    echo "FEHLER: RPI-RP2 nicht gefunden."
    echo "Pico mit gedrueckter BOOTSEL-Taste einstecken!"
    exit 1
fi

echo "UF2 gefunden: $UF2"
echo "Ziel: $MOUNT"
cp "$UF2" "$MOUNT/" && sync
echo "OK - Pico startet neu mit CircuitPython (erscheint als CIRCUITPY)"
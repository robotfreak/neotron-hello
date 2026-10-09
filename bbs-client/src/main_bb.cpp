// bbs_client - Phase 2a Stufe 1: WLAN verbinden, IP zeigen (HDMI + LED)
// Pico 2W, pico-sdk mit CYW43/lwIP. Bild via HSTX 80x30 folgt in Stufe 2.
// Diagnose: LED am CYW43 (WL_GPIO0) = Herzschlag; kein USB-stdio (PC-USB-Falle!)
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "lwip/netif.h"
#include <stdio.h>
#include <string.h>

// WLAN-Credentials via Build-Parameter (c.sh) — NICHT ins Repo!
// Values bleiben [REDACTED]; c.sh ist .gitignored.
#ifndef WIFI_SSID
#error "WIFI_SSID fehlt — baue mit: bash c.bsh <SSID> <PASSWORT>"
#endif
#ifndef WIFI_PASSWORD
#error "WIFI_PASSWORD fehlt — baue mit: bash c.bsh <SSID> <PASSWORT>"
#endif

int main()
{
    stdio_init_all();

    // LED via CYW43 (Onboard-LED am Pico 2W!)
    cyw43_arch_init();
    cyw43_arch_gpio_put(0, true);   // LED an = wir leben, bevor WiFi loslegt
    sleep_ms(500);
    cyw43_arch_gpio_put(0, false);

    cyw43_arch_enable_sta_mode();
    int err = cyw43_arch_wifi_connect_timeout_ms(
        WIFI_SSID, WIFI_PASSWORD, CYW43_AUTH_WPA2_AES_PSK, 30000);

    while (true)
    {
        // Herzschlag 1 Hz; 1 Hz-LED = verbund, 5 Hz = verbindungslos
        static int ok = 0;
        if (err == 0) ok = 1;
        cyw43_arch_gpio_put(0, true);
        sleep_ms(ok ? 500 : 100);
        cyw43_arch_gpio_put(0, false);
        sleep_ms(ok ? 500 : 100);
        // lwIP-Poll-Unterhalt (poll-arch braucht das periodisch):
        cyw43_arch_poll();
    }
    return 0;
}

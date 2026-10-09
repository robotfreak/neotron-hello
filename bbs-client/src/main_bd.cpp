// BOOTDIAG_W v5 - UART0-Diagnose (GP0 TX, kein USB! Die USB/WLAN-Kombi
// ist der Kandidat: v3 ohne USB lief, v4 mit USB: kein ttyACM0).
// LED: 4x kurz = init ok | 2x lang = sta ok | schnell = connect | 1 Hz = UP
// UART: 115200 8N1, alle 2 s: "WL: err=.. n=.. ip=.."
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "lwip/netif.h"
#include <stdio.h>

int main() {
    stdio_init_all();
    int err = cyw43_arch_init();
    for (int i = 0; i < 4; i++) {
        cyw43_arch_gpio_put(0, true); sleep_ms(150);
        cyw43_arch_gpio_put(0, false); sleep_ms(350);
    }
    printf("BOOT 1: cyw43_arch_init rc=%d\n", err);
    cyw43_arch_enable_sta_mode();
    for (int i = 0; i < 2; i++) { cyw43_arch_gpio_put(0, true); sleep_ms(600);
        cyw43_arch_gpio_put(0, false); sleep_ms(400); }
    printf("BOOT 2: sta mode ok\n");
    err = cyw43_arch_wifi_connect_timeout_ms(WIFI_SSID, WIFI_PASSWORD,
        CYW43_AUTH_WPA2_AES_PSK, 30000);
    printf("BOOT 3: connect rc=%d\n", err);
    int n = 0;
    while (true) {
        cyw43_arch_poll();
        static int st = 0; st = 1 - st;
        cyw43_arch_gpio_put(0, st);
        if ((n % 4) == 0)
            printf("WL: err=%d n=%d ip=%s\n", err, n,
                ip4addr_ntoa(netif_ip4_addr(netif_default)));
        n++;
        sleep_ms(err == 0 ? 500 : 100);
    }
    return 0;
}

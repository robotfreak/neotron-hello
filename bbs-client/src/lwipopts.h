// lwipopts.h - lwIP-Konfiguration für BBS-Client (pico_cyw43_arch_lwip_poll)
#ifndef _LWIPOPTS_H
#define _LWIPOPTS_H

// Polling-Architektur (kein Background-IRQ): wir pollen im main-Loop
#define CYW43_LWIP              1
#define NO_SYS                  1									//nur Raw API
#define PICO_CYW43_ARCH_POLL    1

// TCP
#define LWIP_TCP                1
#define LWIP_SOCKET             0	// Raw-API only (NO_SYS=1)
#define LWIP_NETCONN            0
#define TCP_MSS                 1436

// DNS
#define LWIP_DNS                1
// DHCP
#define LWIP_DHCP               1

#define MEM_SIZE                16384
#define MEMP_NUM_TCP_PCB        4
#define MEMP_NUM_TCP_SEG        32
#define PBUF_POOL_SIZE          16

// stdio über UART/USB aus (PC-USB-Falle!); alles via LED/HDMI
#define LWIP_PLATFORM_ASSERT(x) do { (void)(x); } while(0)

#endif

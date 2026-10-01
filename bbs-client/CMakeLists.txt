cmake_minimum_required(VERSION 3.13)
include($ENV{PICO_SDK_PATH}/pico_sdk_init.cmake)

project(bbs_client C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(bbs_client
    src/main.cpp
)

target_include_directories(bbs_client PRIVATE src)

# WLAN-Credentials (vom Befehl -DWIFI_SSID= / -DWIFI_PASSWORD=)
if (NOT DEFINED WIFI_SSID OR NOT DEFINED WIFI_PASSWORD)
    message(FATAL_ERROR "WIFI_SSID/WIFI_PASSWORD fehlen: cmake -DWIFI_SSID=<...> -DWIFI_PASSWORD=<...>")
endif()
target_compile_definitions(bbs_client PRIVATE WIFI_SSID="${WIFI_SSID}" WIFI_PASSWORD="${WIFI_PASSWORD}")

# lwipopts.h muss auch beim Kompilieren der lwIP-lib-sourcen sichtbar sein:
if (TARGET pico_lwip_core_headers)
    target_include_directories(pico_lwip_core_headers INTERFACE ${CMAKE_CURRENT_LIST_DIR}/src)
endif()

target_link_libraries(bbs_client
    pico_stdlib
    pico_cyw43_arch_lwip_poll
    hardware_spi
)

pico_enable_stdio_usb(bbs_client 0)
pico_enable_stdio_uart(bbs_client 0)

pico_add_extra_outputs(bbs_client)

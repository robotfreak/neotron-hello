//! Hello World fuer Neotron Pico
//!
//! Build: cargo build --release --target thumbv6m-none-eabi
//! Copy: target/thumbv6m-none-eabi/release/neotron-hello auf SD-Karte (0:/APPS/)

#![cfg_attr(target_os = "none", no_std)]
#![cfg_attr(target_os = "none", no_main)]

// Fuer Host-Tests (Linux/Windows)
#[cfg(not(target_os = "none"))]
fn main() {
    neotron_sdk::init();
}

// Eigentliche Anwendung
mod app {
    use neotron_sdk::prelude::*;
    
    pub fn run() -> i32 {
        // Einfache Ausgabe
        neoprintln!("\n========================================");
        neoprintln!("       NEOTRON PICO - HELLO WORLD       ");
        neoprintln!("========================================\n");
        neoprintln!("Willkommen auf deinem Neotron Pico!");
        neoprintln!("Geschrieben in Rust, RP2040 CPU\n");
        
        // Menue anzeigen
        show_menu();
        
        0
    }
    
    fn show_menu() {
        neoprintln!("\n--- Menue ---");
        neoprintln!("  [1] Info");
        neoprintln!("  [2] Farbtest");
        neoprintln!("  [q] Beenden\n");
        
        loop {
            neo!("Deine Wahl: ");
            
            // Auf Tastendruck warten
            if let Some(ch) = wait_for_key() {
                match ch {
                    b'1' => {
                        neoprintln!("1");
                        show_info();
                        break;
                    }
                    b'2' => {
                        neoprintln!("2");
                        show_colors();
                        break;
                    }
                    b'q' | b'Q' => {
                        neoprintln!("q");
                        break;
                    }
                    _ => {
                        neoprintln!("Ungueltig! Versuch nochmal:");
                    }
                }
            }
        }
    }
    
    fn show_info() {
        neoprintln!("\nSystem-Info:");
        neoprintln!("  Neotron SDK: 0.2");
        neoprintln!("  App: neotron-hello v0.1.0");
        neoprintln!("  CPU: RP2040 @ 133MHz");
        neoprintln!("  RAM: 256KB SRAM\n");
        
        let _ = wait_for_enter("Enter fuer Menue");
        show_menu();
    }
    
    fn show_colors() {
        neoprintln!("\nFarbtest:");
        
        // ANSI Escape Sequenzen fuer Farben
        neo!("\x1b[31mRot\x1b[0m\n");
        neo!("\x1b[32mGruen\x1b[0m\n");
        neo!("\x1b[34mBlau\x1b[0m\n");
        neo!("\x1b[33mGelb\x1b[0m\n");
        
        let _ = wait_for_enter("Enter fuer Menue");
        show_menu();
    }
    
    fn wait_for_key() -> Option<u8> {
        let api = neotron_sdk::get_api();
        let mut buf = [0u8; 1];
        
        // KBD$ oeffnen und lesen
        if let Ok(kbd) = api.open(b"KBD$".into(), neotron_api::file::Flags::READ) {
            loop {
                if let Ok(n) = api.read(kbd, buf.as_mut_slice().into()) {
                    if n > 0 {
                        return Some(buf[0]);
                    }
                }
            }
        }
        None
    }
    
    fn wait_for_enter(msg: &str) -> i32 {
        neo!("{}: ", msg);
        
        let api = neotron_sdk::get_api();
        let mut buf = [0u8; 1];
        
        if let Ok(kbd) = api.open(b"KBD$".into(), neotron_api::file::Flags::READ) {
            loop {
                if let Ok(n) = api.read(kbd, buf.as_mut_slice().into()) {
                    if n > 0 && (buf[0] == b'\n' || buf[0] == b'\r') {
                        neoprintln!("");
                        return 0;
                    }
                }
            }
        }
        0
    }
}

#[no_mangle]
extern "C" fn neotron_main() -> i32 {
    #[cfg(target_os = "none")]
    return app::run();
    
    #[cfg(not(target_os = "none"))]
    {
        app::run();
        0
    }
}

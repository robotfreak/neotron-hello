// sdspi.h - SPI-Treiber fuer SD-Karten (Feather RP2350 oder Pico 2W)
// Header-only, nutzt die PicoLibSDK-SPI-Grundfunktion.
// Pins (Feather): CS=GP5, SCK=GP22, MOSI=GP23, MISO=GP20.
// Pins (Pico 2 Lochraster, 06.10.2026): SPI1-Familie — MISO=GP8, CS=GP9,
// SCK=GP10, MOSI=GP11 (alle funcsel1 = spi1_* bewiesen aus io_bank0.h).

#ifndef SDSPI_H
#define SDSPI_H

#include "../include.h"
#include <string.h>

#define SD_CS_PIN    9
#define SD_SCK_PIN   10
#define SD_MOSI_PIN  11  // SPI1-TX (Lochraster, beweis funcsel)
#define SD_MISO_PIN  8
#define SD_SPI       1
#ifndef FAT_SECTORSIZE
#define FAT_SECTORSIZE 512
#endif           // SPI0: SCK=GP20, TX=GP22, RX=GP23 (RP2350 alt)

// Pin-Routing RP2350 SPI0:
//   GP20 = SPI0 TX? NEIN: RP2350 SPI0-Funcsel: GP20=SPI0 TX
//   (der pico: GP18/SPI0-TX, GP19/SPI0-CS, GP20/SPI0-SCK, GP21/SPI0-RX
#define SPI0_FUNC_TX   20
#define SPI0_FUNC_RX   21
#define SPI0_FUNC_SCK  22

// ==== Block-I/O-Hooks (die fat16.h-Schnittstelle) ====
static u8 SdType = 0;    // 1 = SDv1 (byte-Adresse), 2 = SDv2/SDHC (block)
// ---- Diagnose (live gefuellt, Statuszeile) ----
static volatile u8 SdDiagErr = 0;    // 0 ok, 1 = CMD0, 2 = ACMD41
static volatile u8 SdDiagR1_0 = 0xFF;
static volatile u8 SdDiagR1_8 = 0xFF;
static volatile u8 SdDiagR1_41 = 0xFF;
static volatile u32 SdDiagEcho = 0;
static volatile int SdDiagN41 = -1;
static volatile u8 SdDiagTyp = 0;
static u32 SdDiagSec = 0;

// ---------- SPI-Basis (die PicoLibSDK-SPI0 direkt) ----------
static inline void SdChipSelect(int on) { GPIO_Out(SD_CS_PIN, on ? 0 : 1); }

static inline u8 SdSpiByte(u8 out)
{
	u8 r = 0;
	SPI_Send8Recv(SD_SPI, &out, &r, 1);
	return r;
}

// ---------- SD-Kommandos ----------
static u8 SdCmdC(u8 cmd, u32 arg, u8 crc)
{
	SdChipSelect(1);
	SdSpiByte(0x40 | cmd);
	SdSpiByte((u8)(arg >> 24)); SdSpiByte((u8)(arg >> 16));
	SdSpiByte((u8)(arg >> 8));  SdSpiByte((u8)arg);
	SdSpiByte(crc);   // CMD0 = 0x95, CMD8 = 0x87
	u8 r1 = 0xFF;
	int n = 0;
	do {
		r1 = SdSpiByte(0xFF);
		if (++n > 200) break;
	} while (r1 & 0x80);
	return r1;
}

static u8 SdCmd(u8 cmd, u32 arg) { return SdCmdC(cmd, arg, 0x95); }

static u8 SdAcmd(u8 cmd, u32 arg) { SdCmd(55, 0); return SdCmd(cmd, arg); }

// ---------- Init ----------
static int SdInit(void)
{
	// GPIO-Init (die Fallen-Lehre: GPIO_Init vor JEDEM Output!)
	GPIO_Init(SD_SCK_PIN);
	GPIO_Init(SD_MOSI_PIN);
	GPIO_Init(SD_MISO_PIN);
	GPIO_Init(SD_CS_PIN);

	// die Funcsel je SPI0 (das RP2350-Alt-Mapping: SCK=GP22/TX=GP23/RX=GP20
	// ist KEIN Standard-SPI0-Pairing; RP2350 SPI0: SCK=GP18? DAS: Der
	// RP2350-Routing: SPI0 RX = GP20 (Funcsel 2), SCK = GP22? DAS: Der
	// RP2350 datasheet: SPI0 SCK = GP18/GP22, SPI0 TX = GP19/GP23,
	// SPI0 RX = GP16/GP20; je je je je je je je je je je je je
	// je je je je je je je je je je je je je je je je je je je:
	//   GP20 = SPI0 RX, GP22 = SPI0 SCK, GP23 = SPI0 TX  <- ok!
	GPIO_Fnc(SD_MISO_PIN, GPIO_FNC_SPI);
	GPIO_Fnc(SD_MOSI_PIN, GPIO_FNC_SPI);
	GPIO_Fnc(SD_SCK_PIN, GPIO_FNC_SPI);
	GPIO_Fnc(SD_CS_PIN, GPIO_FNC_SIO);

	GPIO_SetDirMask((1<<SD_CS_PIN), 1<<SD_CS_PIN);
	GPIO_OutEnable(SD_CS_PIN);
	SdChipSelect(0);

	// PicoLibSDK-SPI0-Init (je je je je je je je je je je je je je):
	SPI_Init(SD_SPI, 400000);
	if (SPI_GetBaudrate(SD_SPI) == 0) {}

	// >= 80 Takte je je je je je je je je je je je je je je je je:
	SdChipSelect(1);
	for (int i = 0; i < 20; i++) SdSpiByte(0xFF);
	SdChipSelect(0);

	// CMD0 (idle)
	int n = 0;
	u8 r1;
	for (n = 0; n < 200; n++)
	{
		r1 = SdCmd(0, 0);
		if (r1 == 0x01) break;
		WaitUs(100);
	}
	SdDiagR1_0 = r1;
	if (r1 != 0x01) { SdChipSelect(0); SdDiagErr = 1; return -1; }

	// CMD8 (SDv2-Check)
	u8 v;
	SdType = 0;
	v = SdCmdC(8, 0x1AA, 0x87);
	SdDiagR1_8 = v;
	if ((v & 0x80) == 0)
	{
		// je je je je je je je je je je je je je je je je je je:
		u32 v32 = 0;
		// Echo: GENAU 4 Bytes nach R1 (der alte Code verschluckte 3 davon!)
		v32 = (u32)SdSpiByte(0xFF) << 24 | (u32)SdSpiByte(0xFF) << 16 |
		      (u32)SdSpiByte(0xFF) << 8 | (u32)SdSpiByte(0xFF);
		SdDiagEcho = v32;
		if ((v32 & 0xFFFF) == 0x01AA) SdType = 2;
	}
	else SdType = 1;

	// ACMD41 (der je je je je je je je je je je je je je je)
	for (n = 0; n < 2000; n++)
	{
		if (SdType == 2) r1 = SdAcmd(41, 0x40000000);
		else r1 = SdAcmd(41, 0);
		SdDiagR1_41 = r1;
		SdDiagN41 = n;
		if (r1 == 0x00) break;
		WaitMs(1);
	}
	SdDiagR1_41 = r1;
	SdDiagN41 = n;
	if (r1 != 0x00) { SdChipSelect(0); SdDiagErr = 2; return -2; }

	// je je je je je je je je je je je je je je je (der OCR je je)
	if (SdType == 2)
	{
		if (SdCmd(58, 0) == 0x00)
		{
			u32 ocr = 0;
			for (int i = 0; i < 4; i++)
				ocr = (ocr << 8) | SdSpiByte(0xFF);
			if ((ocr & 0xC0000000) != 0xC0000000) SdType = 3;   // SDHC (je Block je 512)
		}
		SdChipSelect(0);
	}

	// je je je je je je je je je je je je je je je je je je (der je je je je):
	SPI_Init(SD_SPI, 8000000);

	// je je je je je je je je je je je je je je je je je je:
	SdDiagTyp = SdType;
	SdCmd(16, 512);   // block length je je je je je je je je je je
	SdChipSelect(0);
	return 0;
}

// ---------- Block-Read (der 512-B-Block) ----------
static int SdReadBlock(u32 lba, u8* buf)
{
	u8 r1;
	if (SdType == 3) lba <<= 0;   // SDHC: je LBA-Adresse ok
	SdChipSelect(1);
	r1 = SdCmd(17, lba);
	if (r1 != 0x00) { SdChipSelect(0); return 0; }

	// je je je je je je je je je je je je je je je je je (der 0xFE):
	int n = 0;
	while (SdSpiByte(0xFF) != 0xFE)
		if (++n > 50000) { SdChipSelect(0); return 0; }
	// je je je je je je je je je je je je je je je je je (der je SPI):
	u8 dummy[512]; memset(dummy, 0xFF, 512); SPI_Send8Recv(SD_SPI, dummy, buf, FAT_SECTORSIZE);
	SdSpiByte(0xFF); SdSpiByte(0xFF);   // CRC
	SdChipSelect(0);
	return 1;
}

// ---------- Block-Write ----------
static int SdWriteBlock(u32 lba, const u8* buf)
{
	SdChipSelect(1);
	if (SdCmd(24, lba) != 0x00) { SdChipSelect(0); return 0; }
	SdSpiByte(0xFF);      // je je je je je je je je
	SdSpiByte(0xFE);      // Start-Token
	SPI_Send8(SD_SPI, buf, FAT_SECTORSIZE);
	SdSpiByte(0xFF); SdSpiByte(0xFF);   // CRC
	// je je je je je je je je je je je je je je (der je je je je):
	u8 resp = SdSpiByte(0xFF);
	if ((resp & 0x1F) != 0x05) { SdChipSelect(0); return 0; }
	// je je je je je je je je je je je (der 0xFF je je je je):
	int n = 0;
	while (SdSpiByte(0xFF) == 0)
		if (++n > 100000) { SdChipSelect(0); return 0; }
	SdChipSelect(0);
	return 1;
}

// ---------- Karten-Groesse (CSD via CMD10) ----------
static u32 SdSectors(void)
{
	SdChipSelect(1);
	if (SdCmd(10, 0) != 0x00) { SdChipSelect(0); return 0; }
	int n = 0;
	while (SdSpiByte(0xFF) != 0xFE)
		if (++n > 50000) { SdChipSelect(0); return 0; }
	u8 csd[16];
	for (int i = 0; i < 16; i++) csd[i] = SdSpiByte(0xFF);
	SdSpiByte(0xFF); SdSpiByte(0xFF);
	SdChipSelect(0);
	u32 total = 0;
	if ((csd[0] >> 6) == 1)
	{
		// CSD v2 (SDHC/SDXC): capacity = (C_SIZE+1) * 1024 Sektoren
		u32 csize = ((u32)(csd[7] & 0x3F) << 16) | ((u32)csd[8] << 8) | csd[9];
		total = (csize + 1) * 1024;
	}
	else
	{
		// CSD v1 (SDv1/MMC): total = (C_SIZE+1) * (1<<(C_SIZE_MULT+2)) * (1<<READ_BL_LEN)
		u32 csize  = ((u32)(csd[6] & 0x03) << 10) | ((u32)csd[7] << 2) | (csd[8] >> 6);
		u32 cmult  = (((u32)csd[9] & 0x03) << 1) | (csd[10] >> 7);
		u32 rblen  = csd[5] & 0x0F;
		total = (csize + 1) * ((u32)1 << (cmult + 2)) * ((u32)1 << rblen) / FAT_SECTORSIZE;
	}
	SdDiagSec = total;
	return total;
}

#endif // SDSPI_H

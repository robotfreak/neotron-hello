// ****************************************************************************
//
//                Neotron Workshop - TinyBASIC 80x30 Konsole
//        ATEXT 80x30 text mode + PS/2 keyboard + BASIC-Interpreter
//            based on DispHSTX (Panda381 / Miroslav Nemecek)
//
// Wiring (Pico 2W, HSTX DVI on GPIO12-19, SD-MOSI=GP3):
//   GP0 = PS/2 Clock, GP1 = PS/2 Data (pull-ups to 3V3!)
//   PS/2 +5V pin -> VBUS (5V), GND common
//   Mini-DIN 6 (socket front view): 1=Data, 3=GND, 4=+5V, 5=Clock
//
// ****************************************************************************

#include "../include.h"

// Diagnose-Ausgabe nur mit USB-stdio (sonst no-op)
#if USE_USB_STDIO
#define DIAGUSB(...) UsbPrint(__VA_ARGS__)
#else
#define DIAGUSB(...)
#endif
#include "basic.h"
#include "sdspi.h"
#include "fat16.h"

// LED: onboard-LED des Pico 2 (non-W) = GP25 (kein CYW43!)
#undef LED_PIN
#define LED_PIN 25
#define CHECK_ERR() while (res != DISPHSTX_ERR_OK) { GPIO_Flip(LED_PIN); WaitMs(100); }

// ==== CGA-16 palette: COLOR16(G_t, B_t, R_t) - channel rotation proof
static const u16 pal16[16] = {
	//  BLACK          BLUE             GREEN            CYAN
	COLOR16(  0,  0,  0),	COLOR16(  0,128,  0),	COLOR16(128,  0,  0),	COLOR16(  0,128,128),
	//  RED            MAGENTA          BROWN            LTGRAY
	COLOR16(  0,  0,128),	COLOR16(  0,128,128),	COLOR16(128,  0,128),	COLOR16(192,192,192),
	//  DKGRAY         LTBLUE           LTGREEN          LTCYAN
	COLOR16( 64, 64, 64),	COLOR16(  0,255,  0),	COLOR16(255,  0,  0),	COLOR16(255,255,  0),
	//  LTRED          LTMAGENTA        YELLOW           WHITE
	COLOR16(  0,  0,255),	COLOR16(  0,255,255),	COLOR16(255,  0,255),	COLOR16(255,255,255),
};

// ==== text screen
#define TEXTCOLS	80
#define TEXTROWS	30
#define STATUSROW	29		// die unterste Zeile: fixe Statuszeile (scrollt nicht)
#define TEXTPITCH	(TEXTCOLS*2)
static u8 ALIGNED TextBuf[TEXTPITCH*TEXTROWS];
static u8 ALIGNED FontBuf[sizeof(FontBold8x16)];

// cursor position (console state)
static int CurCol = 0, CurRow = 0;

// ==== simple text functions
static void PutCharAt(int col, int row, char ch, u8 attr)
{
	u8* line = &TextBuf[row*TEXTPITCH];
	line[col*2] = (u8)ch;
	line[col*2 + 1] = attr;
}

static void PutString(int col, int row, const char* text, u8 attr)
{
	while (*text != 0)
	{
		PutCharAt(col, row, *text, attr);
		col++;
		text++;
	}
}

static void ClearText(char ch, u8 attr)
{
	for (int row = 0; row < TEXTROWS; row++)
	{
		u8* line = &TextBuf[row*TEXTPITCH];
		for (int col = 0; col < TEXTCOLS; col++)
		{
			line[col*2] = (u8)ch;
			line[col*2 + 1] = attr;
		}
	}
}

// scroll screen up 1 row
static void ScrollText()
{
	memmove(TextBuf, &TextBuf[TEXTPITCH], TEXTPITCH*(TEXTROWS-2));
	u8* line = &TextBuf[(TEXTROWS-2)*TEXTPITCH];
	for (int col = 0; col < TEXTCOLS; col++)
	{
		line[col*2] = ' ';
		line[col*2 + 1] = 0x07;
	}
}

// put console char at cursor (with scroll)
static void ConsoleChar(char ch)
{
	if (ch == '\n')
	{
		CurCol = 0;
		CurRow++;
	}
	else if (ch == '\r')
	{
		CurCol = 0;
	}
	else if (ch == '\t')
	{
		int n = 4 - (CurCol & 3);
		while (n-- > 0) ConsoleChar(' ');
	}
	else if (ch == '\b')
	{
		if (CurCol > 0) CurCol--;
		PutCharAt(CurCol, CurRow, ' ', 0x07);
	}
	else if (ch >= ' ')
	{
		PutCharAt(CurCol, CurRow, ch, 0x07);
		CurCol++;
		if (CurCol >= TEXTCOLS)
		{
			CurCol = 0;
			CurRow++;
		}
	}
	if (CurRow > TEXTROWS-2)      // Statuszeile (29) ausnehmen
	{
		ScrollText();
		CurRow = TEXTROWS-2;
	}
}

// ==== BASIC I/O hooks (der Interpreter <-> Konsole)
static void BasOutHook(char ch) { ConsoleChar(ch); }

// ==== PS/2 keyboard (Set-2 scan codes, GPIO bit-bang via IRQ)
// GP0 = clock (falling edge IRQ), GP1 = data
#define PS2_CLK_PIN		3
#define PS2_DAT_PIN		2

static volatile int IrqCount = 0;	// IRQ-Feuer-Zähler (Diagnose)
static volatile u8 Ps2Bit = 0;
static volatile u8 Ps2Data = 0;
static volatile u8 Ps2Parity = 0;
static volatile int Ps2Count = 0;
static volatile u8 Ps2Buf[16];
static volatile int Ps2Wr = 0;
static volatile int Ps2Rd = 0;

// GPIO IRQ callback (falling clock edge)
static void Ps2Irq(uint pin, u32 events)
{
	if (pin != PS2_CLK_PIN) return;
	IrqCount++;

	int bit = GPIO_In(PS2_DAT_PIN);

	if (Ps2Bit == 0)
	{
		Ps2Data = 0;
		Ps2Parity = 0;
		Ps2Bit = 1;
	}
	else if (Ps2Bit <= 8)
	{
		Ps2Data >>= 1;
		if (bit != 0) Ps2Data |= 0x80;
		Ps2Parity ^= bit;
		Ps2Bit++;
	}
	else if (Ps2Bit == 9)
	{
		Ps2Bit = 10;	// parity bit (skipped)
	}
	else
	{
		Ps2Bit = 0;	// stop bit
		Ps2Buf[Ps2Wr] = Ps2Data;
		Ps2Wr = (Ps2Wr + 1) & 15;
		if (Ps2Count < 16) Ps2Count++;
	}
}

// ==== Set-2 scan code decoder (UK/ISO)
typedef struct sKeyMap { u8 code; char normal; char shifted; } sKeyMap;
static const sKeyMap KeyMap[] = {
	{ 0x0E, '`', '|' },	{ 0x16, '1', '!' },	{ 0x1E, '2', '"' },	{ 0x26, '3', (char)0x9C },
	{ 0x25, '4', '$' },	{ 0x2E, '5', '%' },	{ 0x36, '6', '^' },	{ 0x3D, '7', '&' },
	{ 0x3E, '8', '*' },	{ 0x46, '9', '(' },	{ 0x45, '0', ')' },
	{ 0x4E, '-', '_' },	{ 0x55, '=', '+' },
	{ 0x15, 'q', 'Q' },	{ 0x1D, 'w', 'W' },	{ 0x24, 'e', 'E' },	{ 0x2D, 'r', 'R' },
	{ 0x2C, 't', 'T' },	{ 0x35, 'y', 'Y' },	{ 0x3C, 'u', 'U' },	{ 0x43, 'i', 'I' },
	{ 0x44, 'o', 'O' },	{ 0x4D, 'p', 'P' },	{ 0x54, '[', '{' },	{ 0x5B, ']', '}' },
	{ 0x1C, 'a', 'A' },	{ 0x1B, 's', 'S' },	{ 0x23, 'd', 'D' },	{ 0x2B, 'f', 'F' },
	{ 0x34, 'g', 'G' },	{ 0x33, 'h', 'H' },	{ 0x3B, 'j', 'J' },	{ 0x42, 'k', 'K' },
	{ 0x4B, 'l', 'L' },	{ 0x4C, ';', ':' },	{ 0x52, (char)0x27, (char)0x22 },
	{ 0x4A, '/', '?' },	{ 0x5D, '#', '~' },
	{ 0x1A, 'z', 'Z' },	{ 0x22, 'x', 'X' },	{ 0x21, 'c', 'C' },	{ 0x2A, 'v', 'V' },
	{ 0x32, 'b', 'B' },	{ 0x31, 'n', 'N' },	{ 0x3A, 'm', 'M' },	{ 0x41, ',', '<' },
	{ 0x49, '.', '>' },
	{ 0x29, ' ', ' ' },
	{ 0x66, 8, 8 },		// backspace
	{ 0, 0, 0 },
};

// ==== Line editor (PS/2 -> Zeile, mit Prompt + Echo + Backspace + Enter)
// liefert 1 bei Enter, 0 bei Abbruch (kein Byte)
#define LINEMAX 100
static char LBuf[LINEMAX];
static int LLen = 0;

// read one key from PS/2 ring buffer (blockiert bis Zeichen, je VSync)
static int ReadKey(unsigned* pstate)
{
	static u8 relbreak = 0;
	static int shift = 0;
	while (Ps2Count == 0) DispHstxWaitVSync();

	u8 code = Ps2Buf[Ps2Rd];
	Ps2Rd = (Ps2Rd + 1) & 15;
	Ps2Count--;

	int ret = -2;   // Default: ignorierbar
	if (code == 0xF0) { relbreak = 1; return -2; }   // Break-Prefix: Flag bleibt
	else if (code == 0xE0) { relbreak = 0; return -2; }   // Extended-Prefix
	else if (code == 0x5A) { ret = relbreak ? -2 : '\n'; relbreak = 0; }
	else if ((code == 0x12) || (code == 0x59)) { shift = relbreak ? 0 : 1; relbreak = 0; }
	else if (code == 0x76) { ret = 27; relbreak = 0; }   // ESC
	else if (code == 0x5B || code == 0x54) { relbreak = 0; }   // Alt/FN
	else if (relbreak) { relbreak = 0; }   // Release-Code einer Taste: ignorieren
	else
	{
		for (unsigned i = 0; KeyMap[i].code != 0; i++)
		{
			if (KeyMap[i].code == code)
			{
				ret = (u8)(shift ? KeyMap[i].shifted : KeyMap[i].normal);
				break;
			}
		}
		relbreak = 0;
	}
	*pstate = 0;
	return ret;
}

// Zeile mit Prompt einlesen (Enter beendet; 27=ESC bricht ab -> liefert 0)
static char BasReadLineHook(char* buf, int max, const char* prompt)
{
	while (*prompt) ConsoleChar(*prompt++);
	LLen = 0;
	unsigned dummy;
	for (;;)
	{
		int k = ReadKey(&dummy);
		if (k == -2) continue;
		if (k == -1) continue;
		if (k == 27) { ConsoleChar('\n'); return 0; }	// ESC = Abbruch
		if (k == '\n') { ConsoleChar('\n'); break; }
		if (k == 8 || k == 127)
		{
			if (LLen > 0) { LLen--; ConsoleChar('\b'); }
			continue;
		}
		if (k >= ' ' && LLen < max - 1 && LLen < LINEMAX - 1)
		{
			LBuf[LLen++] = (char)k;
			ConsoleChar((char)k);
		}
	}
	LBuf[LLen] = 0;
	ConsoleChar('\n');
	int len = LLen;
	strncpy(buf, LBuf, max - 1);
	buf[max - 1] = 0;
	if (len > 0) return 1;
	return 1;	// auch Leerzeile liefern
}

// ==== REPL-Zustand (der Prompt '] ')
static sDispHstxVSlot* slot;

// ==== SD-Card + FAT16 State ====
static int SdOk = 0;   // 0 = keine Karte / Mount-Fehler

static int BasSaveHook(const char* name, const char* src)
{
	if (!SdOk) return 1;
	return f16_write_file(name, (const u8*)src, StrLen(src)) == F16_ERR_OK ? 0 : 1;
}

static int BasLoadHook(const char* name, char* dst, int max)
{
	if (!SdOk) return 1;
	u8 e83[11];
	f16_name_to83(name, e83);
	FatFile ff;
	if (f16_dir_find(e83, &ff) != F16_ERR_OK) return 1;
	u32 got = 0;
	if (f16_read_file(&ff, (u8*)dst, max - 1, &got) != F16_ERR_OK) return 1;
	dst[got] = 0;
	if (got > (u32)(max - 1)) dst[max - 1] = 0;
	return 0;
}

// die BasIs-Demo-Bank (die Beispiele beim Start)
static const char* Welcome[] = {
	 "*** TINY BASIC v1.0 (C-Port) ***",
	 "Feather RP2350 + DispHSTX 80x30 + PS/2",
	 "",
	 "Befehle: NEW LIST RUN BYE SAVE \"N\" LOAD \"N\"",
	 "Beispiel: 10 PRINT \"HALLO\"  dann RUN",
	 "",
};

volatile int BootStufe = 0;  // Diagnose: letzte Boot-Stufe (USB)

// SafeWaitVSync: wartet auf VSync, meldet aber ueber USB, wenn der Video-
// DMA keine Zeilen fortlaufend zaehlt (Verdiagnose "kein Bild").
static int NoVsyncCount = 0;
static void SafeWaitVSync()
{
	// wait end of vsync (max 1 frame)
	int n = 0;
	while (DispHstxIsVSync() && (n < 1000000)) { n++; dmb(); }
	int n2 = 0;
	while (!DispHstxIsVSync() && (n2 < 1000000)) { n2++; dmb(); }
	if (n2 >= 1000000)
	{
		// keine Zeilenzaehlung -> Video-DMA tot
		NoVsyncCount++;
		if (NoVsyncCount == 1) DIAGUSB("DIAG: NO VSYNC - Video-DMA zaehlt nicht!\n");
		if ((NoVsyncCount % 120) == 0) DIAGUSB("ALIVE STUFE=%d SD=%d NOVSYNC=%d\n",
			BootStufe, (int)SdOk, NoVsyncCount);
	}
}

int main()
{
	// ==== initialize videomode 640x480@60Hz, 1 strip, 1 ATEXT slot
	int res;
	ClearText(' ', 0x07);
	memcpy(FontBuf, FontBold8x16, sizeof(FontBold8x16));

	memset(&bas, 0, sizeof(bas));
	bas.rnd_seed = 12345;
	bas.out_hook = BasOutHook;
	bas.readline_hook = BasReadLineHook;
	bas.errline = -1;
	bas.save_hook = BasSaveHook;
	bas.load_hook = BasLoadHook;

	DIAGUSB("BOOT 1: basic init ok\n"); BootStufe = 1;
	sDispHstxVModeState* vmode = &DispHstxVMode;
	DispHstxVModeInitTime(vmode, &DispHstxVModeTimeList[vmodetime_640x480_fast]);

	res = DispHstxVModeAddStrip(vmode, 480);
	CHECK_ERR();

	res = DispHstxVModeAddSlot(vmode, 1, 1, 640, DISPHSTX_FORMAT_ATEXT,
		TextBuf, TEXTPITCH, pal16, DispHstxDefVgaPal, FontBuf, 16, 0, 0);
	CHECK_ERR();

	DispHstxSelDispMode(DISPHSTX_DISPMODE_DVI, vmode);
	DIAGUSB("BOOT 2: video started 640x480 DVI\n"); BootStufe = 2;

	// ==== welcome banner (weiß auf blau)
	for (int col = 0; col < TEXTCOLS; col++) PutCharAt(col, 0, ' ', 0x1F);
	PutString(1, 0, " TINYBASIC 80x30  C-Port  -  Pico 2 HSTX ", 0x1F);
	CurRow = 2;
	for (unsigned i = 0; i < sizeof(Welcome)/sizeof(Welcome[0]); i++)
	{
		const char* w = Welcome[i];
		while (*w) ConsoleChar(*w++);
		ConsoleChar('\n');
	}

	// ==== SD-Card init + FAT16 Mount (Haken: save_hook/load_hook)
	SdOk = 0;
	SdDiagErr = 0;
	int f16err = -99;
	int rr1_17 = 0x55, rr1_10 = 0x55;   // diag (0x55 = 'nicht gemessen')
	if (SdInit() == 0)
	{
		fat.io.read_block = SdReadBlock;
		fat.io.write_block = SdWriteBlock;
		fat.io.nsectors = SdSectors();
		f16err = (int)f16_mount();
		if (f16err == F16_ERR_OK)
			SdOk = 1;
		else SdDiagErr = 5;
		// Diag: Roh-Sektor-Read (CMD17, mit Token — der CSD-Run verfälschte!)
		rr1_17 = SdDiagBlock(0);
	}
	else SdDiagErr = 10;
	char sbuf[160];
	if (SdOk)
		MemPrint(sbuf, 150, "SD: OK  %lu MB (FAT16/32, SAVE/LOAD bereit)  ",
			(unsigned long)(SdDiagSec / 2048));
	else
		MemPrint(sbuf, 150, "SD: FEHLT E=%d F=%d M=%lX R=%02X T=%02X N=%d",
			(int)SdDiagErr, f16err, (unsigned long)SdDiagSec,
			(unsigned)rr1_17, (unsigned)SdDiagTok, (int)SdDiagTokN);
	PutString(0, 1, sbuf, 0x2F);
	{ int bl = StrLen(sbuf); if (bl > 64) bl = 64; PutString(bl, 1, "                                                                  ", 0x2F); }
	if (!SdOk)
	{
		// Zeile 3: Sektor[0..19] (der echte Stream-Inhalt!)
		MemPrint(sbuf, 150, "S0: %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X",
			(unsigned)SdDiagBlk[0], (unsigned)SdDiagBlk[1], (unsigned)SdDiagBlk[2], (unsigned)SdDiagBlk[3],
			(unsigned)SdDiagBlk[4], (unsigned)SdDiagBlk[5], (unsigned)SdDiagBlk[6], (unsigned)SdDiagBlk[7],
			(unsigned)SdDiagBlk[8], (unsigned)SdDiagBlk[9], (unsigned)SdDiagBlk[10], (unsigned)SdDiagBlk[11],
			(unsigned)SdDiagBlk[12], (unsigned)SdDiagBlk[13], (unsigned)SdDiagBlk[14], (unsigned)SdDiagBlk[15]);
		PutString(0, 2, sbuf, 0x2F);
		{ int bl = StrLen(sbuf); if (bl > 72) bl = 72; PutString(bl, 2, "                                                                        ", 0x2F); }
		// Zeile 4: Sektor[496..511] (die Endsignatur-Position!)
		MemPrint(sbuf, 150, "S496: %02X %02X %02X %02X   S508: %02X %02X %02X %02X",
			(unsigned)SdDiagBlk[16], (unsigned)SdDiagBlk[17], (unsigned)SdDiagBlk[18], (unsigned)SdDiagBlk[19],
			(unsigned)SdDiagBlk[20], (unsigned)SdDiagBlk[21], (unsigned)SdDiagBlk[22], (unsigned)SdDiagBlk[23]);
		PutString(0, 3, sbuf, 0x2F);
		{ int bl = StrLen(sbuf); if (bl > 72) bl = 72; PutString(bl, 3, "                                                                        ", 0x2F); }
	}

	BootStufe = 3;
	// ==== initialize PS/2 keyboard
	GPIO_Init(PS2_CLK_PIN);
	GPIO_Init(PS2_DAT_PIN);
	GPIO_SetDirMask((1<<PS2_CLK_PIN) | (1<<PS2_DAT_PIN), 0);
	GPIO_PullUp(PS2_CLK_PIN);
	GPIO_PullUp(PS2_DAT_PIN);

	// LED (Pico 2: GP25 = onboard)
	GPIO_Init(LED_PIN);
	GPIO_OutEnable(LED_PIN);
	GPIO_Out(LED_PIN, 0);

	// attach IRQ callback on falling clock edge
	GPIO_IRQSetCallback(Ps2Irq);
	GPIO_IRQEnable(PS2_CLK_PIN, IRQ_EVENT_EDGELOW);
	NVIC_IRQEnable(IRQ_IO_BANK0);

	BootStufe = 4;

	// ==== hardware cursor
	slot = &vmode->strip[0].slot[0];
	slot->curbeg = 14;
	slot->curend = 15;
	slot->curspeed = 12;

	DIAGUSB("BOOT 3: SD=%d REPL ready\n", (int)SdOk); BootStufe = 5;

	// ==== REPL loop (der Prompt '] ', die Zeile je Enter)
	char dbuf[64];
	int ledtimer = 0;
	int promptflag = 0;
	while (True)
	{
		SafeWaitVSync();

		slot->currow = (u8)(CurRow & 0xFF);
		slot->curpos = (u8)(CurCol & 0xFF);

		// LED-Lebenszeichen
		ledtimer++;
		GPIO_Out(LED_PIN, (ledtimer >= 90) ? 1 : 0);
		if (ledtimer >= 120) ledtimer = 0;

		// Diagnose: Boot-Marken zyklisch ueber USB (alle 2 s = 120 Frames)
		static int bootdiagtimer = 0;
		bootdiagtimer++;
		if (bootdiagtimer >= 120)
		{
			bootdiagtimer = 0;
			DIAGUSB("ALIVE STUFE=%d SD=%d\n", BootStufe, (int)SdOk);
		}

		// Diagnose (Statuszeile unten) + RAW-Scancode-Debug
		MemPrint(dbuf, 64, "IRQ=%d CNT=%d RAW=%02X %02X DAT=%d CLK=%d ",
			IrqCount, (int)Ps2Count,
			(unsigned)Ps2Buf[(Ps2Rd + 0) & 15],
			(unsigned)Ps2Buf[(Ps2Rd + 1) & 15],
			(int)GPIO_In(PS2_DAT_PIN), (int)GPIO_In(PS2_CLK_PIN));
		PutString(0, 29, dbuf, 0x0B);
{ int bl = StrLen(dbuf); if (bl < 55) PutString(bl, 29, "                                   ",
0x0B); }

		// Prompt ] ausgeben (einmal je Zeilen-Start)
		if (promptflag == 0)
		{
			ConsoleChar(']');
			promptflag = 1;
		}

		// Eingabe-Zeile lesen (blockiert im Zeichen, mit Prompt)
		unsigned dummy;
		int k = ReadKey(&dummy);

		if (k == -2 || k == -1)
		{
			// ignorierbare oder Modifier-Taste (je VSync weiter)
			continue;
		}

		// Zeichen sammeln (LBuf), Enter -> BasReadLineHook-Logik
		if (k == '\n')
		{
			LBuf[LLen] = 0;
			ConsoleChar('\n');
			// die Zeile (LLen>0) ausfuehren
			if (LLen > 0)
			{
				LBuf[LLen] = 0;
				int bye = bas_exec_line(LBuf);
				(void)bye;
			}
			LLen = 0;
			promptflag = 0;
		}
		else if (k == 8 || k == 127)
		{
			if (LLen > 0) { LLen--; ConsoleChar('\b'); }
		}
		else if (k == 27)
		{
			// ESC: Zeile verwerfen
			while (LLen > 0) { LLen--; ConsoleChar('\b'); }
		}
		else if (k >= ' ' && LLen < LINEMAX - 1)
		{
			LBuf[LLen++] = (char)k;
			ConsoleChar((char)k);
		}
	}
	return 0;
}
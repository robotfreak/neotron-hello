
// fat16test.c - Host-Tests fuer das FAT16-Mini-Filesystem
#include "../src/fat16.h"
#include <stdio.h>
#include <assert.h>

// ---- RAM-Disk (die Simulierte SD-Karte, 64 MB) ----
#define RAM_SECTORS (16*1024*1024/512)
static u8 ramdisk[RAM_SECTORS][FAT_SECTORSIZE];
static u32 ram_n = RAM_SECTORS;

static int ram_read(u32 lba, u8* buf)
{
	if (lba >= ram_n) return 0;
	memcpy(buf, &ramdisk[lba][0], 512);
	return 1;
}
static int ram_write(u32 lba, const u8* buf)
{
	if (lba >= ram_n) return 0;
	memcpy(&ramdisk[lba][0], buf, 512);
	return 1;
}

static int fails = 0, total = 0;
static void check(const char* name, int ok)
{
	total++;
	printf("%s %s\n", ok ? "ok  " : "FAIL", name);
	if (!ok) fails++;
}

static void fat_reset(void)
{
	memset(&fat, 0, sizeof(fat));
	fat.io.read_block = ram_read;
	fat.io.write_block = ram_write;
	memset(ramdisk, 0, sizeof(ramdisk));
}

// ---- Test: Ein FAT16-Image auf der RAM-Disk bauen (die mkfs-Logik)
static void mkfs_fat16(int nfat_secs, int root_secs, int data_secs)
{
	u8 s[FAT_SECTORSIZE];
	memset(s, 0, FAT_SECTORSIZE);
	// Boot-Sektor (FAT16):
	s[0] = 0xEB; s[1] = 0x3C; s[2] = 0x90;
	memcpy(&s[3], "MSDOS5.0", 8);
	s[11] = 0x00; s[12] = 0x02;          // bytes/Sektor = 512
	s[13] = 1;                            // Sektor je Cluster
	s[14] = 0x20; s[15] = 0x00;          // reserved = 32 (der FAT-Basis)
	s[16] = 2;                            // nfats
	s[17] = (u8)(root_secs * 16); s[18] = (u8)((root_secs * 16) >> 8);   // root-entries = root_secs*16
	s[19] = (u8)((32 + nfat_secs * 2 + root_secs + data_secs) & 0xFF);
	s[20] = (u8)(((32 + nfat_secs * 2 + root_secs + data_secs) >> 8) & 0xFF);  // total sectors (16 bit)
	s[21] = 0xF8;                          // media descriptor
	s[22] = (u8)(nfat_secs & 0xFF);
	s[23] = (u8)((nfat_secs >> 8) & 0xFF);
	memcpy(&s[54], "FAT16   ", 8);
	s[510] = 0x55; s[511] = 0xAA;
	ram_write(0, s);
	// FAT (die 2 Kopien):
	for (int fi = 0; fi < 2; fi++)
	{
		for (int ks = 0; ks < nfat_secs; ks++)
		{
			memset(s, 0, FAT_SECTORSIZE);
			if (ks == 0) { s[0] = 0xF8; s[1] = 0xFF; s[2] = 0xFF; s[3] = 0xFF; }   // Cluster 0/1 = media/reserved
			ram_write(32 + fi * nfat_secs + ks, s);
		}
	}
	// Root-Dir (der leere):
	memset(s, 0, FAT_SECTORSIZE);
	for (int rs = 0; rs < root_secs; rs++)
		ram_write(32 + 2 * nfat_secs + rs, s);
	// Data-Region: leer
	u32 data_lba = 32 + 2 * nfat_secs + root_secs;
	memset(s, 0, FAT_SECTORSIZE);
	for (u32 ds = 0; ds < (u32)data_secs && data_lba + ds < ram_n; ds++)
		ram_write(data_lba + ds, s);
	printf("mkfs: fat_lba=%u root_lba=%u data_lba=%u\n", 32, 32 + 2 * nfat_secs, 32 + 2 * nfat_secs + root_secs);
}

#define ROOT_ENTRIES 512
#define NFAT 2

int main(void)
{
	// Test 1: Mount (FAT16)
	fat_reset();
	mkfs_fat16(NFAT, ROOT_ENTRIES * 32 / 512, 8000);
	int e = f16_mount();
	check("mount FAT16", e == F16_ERR_OK);
	check("fat_bits=16", fat.vol.fat_bits == 16);
	check("sec_per_clus=1", fat.vol.sec_per_clus == 1);
	check("reserved=32", fat.vol.reserved == 32);
	check("root_entries=512", fat.vol.root_entries == 512);
	check("data_lba ok", fat.vol.data_lba == 32 + 2 * NFAT + ROOT_ENTRIES * 32 / 512);

	// Test 2: Datei schreiben + lesen (rundtrip)
	{
		const char* text = "10 PRINT \"HELLO\"\n20 GOTO 10\n";
		u32 len = (u32)strlen(text);
		e = f16_write_file("DEMO.BAS", (const u8*)text, len);
		check("write DEMO.BAS", e == F16_ERR_OK);
		FatFile ff;
		u8 e83[11];
		f16_name_to83("DEMO.BAS", e83);
		e = f16_dir_find(e83, &ff);
		check("find DEMO.BAS", e == F16_ERR_OK);
		check("size", ff.size == len);
		u8 buf[512]; u32 got;
		e = f16_read_file(&ff, buf, sizeof(buf), &got);
		check("read roundtrip", e == F16_ERR_OK && got == len && memcmp(buf, text, len) == 0);
	}

	// Test 3: Ueberschreiben (die 2. Save)
	{
		const char* text2 = "REM GEANDERT\n";
		e = f16_write_file("DEMO.BAS", (const u8*)text2, (u32)strlen(text2));
		check("overwrite", e == F16_ERR_OK);
		FatFile ff; u8 e83[11]; f16_name_to83("DEMO.BAS", e83);
		f16_dir_find(e83, &ff);
		u8 buf[512]; u32 got;
		f16_read_file(&ff, buf, sizeof(buf), &got);
		check("overwrite content", got == strlen(text2) && memcmp(buf, text2, got) == 0);
	}

	// Test 4: Mehrere Dateien + Root-Dir-Voll
	{
		for (int i = 0; i < 10; i++)
		{
			char name[16];
			snprintf(name, sizeof(name), "TEST%d.BAS", i);
			e = f16_write_file(name, (const u8*)"DATA", 4);
			if (e != F16_ERR_OK) { printf("  (write %s rc=%d)\n", name, e); break; }
		}
		check("10 Dateien geschrieben", e == F16_ERR_OK);
		FatFile ff; u8 e83[11];
		f16_name_to83("TEST9.BAS", e83);
		check("TEST9 vorhanden", f16_dir_find(e83, &ff) == F16_ERR_OK);
	}

	// Test 5: Loeschen + Wiederbeschreiben
	{
		e = f16_delete("TEST5.BAS");
		check("delete TEST5", e == F16_ERR_OK);
		FatFile ff; u8 e83[11]; f16_name_to83("TEST5.BAS", e83);
		check("TEST5 weg", f16_dir_find(e83, &ff) == F16_ERR_NOFILE);
		// Wiederbeschreiben (der freie Slot)
		e = f16_write_file("TEST5.BAS", (const u8*)"NEU", 3);
		check("TEST5 re-created", e == F16_ERR_OK);
	}

	// Test 6: FAT-Cluster-Kette (die grosse Datei: DAS je 10 Cluster):
	{
		u8 big[10*512];
		memset(big, 'A', sizeof(big));
		e = f16_write_file("BIG.BAS", big, sizeof(big));
		check("BIG.BAS (10 Clus)", e == F16_ERR_OK);
		FatFile ff; u8 e83[11]; f16_name_to83("BIG.BAS", e83);
		f16_dir_find(e83, &ff);
		u8 buf[12*512]; u32 got;
		e = f16_read_file(&ff, buf, sizeof(buf), &got);
		check("BIG roundtrip", e == F16_ERR_OK && got == sizeof(big));
		u8 ok = 1;
		for (int i = 0; i < (int)got; i++) if (buf[i] != 'A') { ok = 0; break; }
		check("BIG content", ok);
	}

	printf("\n%d/%d bestanden\n", total - fails, total);
	return fails ? 1 : 0;
}
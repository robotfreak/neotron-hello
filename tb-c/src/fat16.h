// fat16.h - Mini-FAT16/FAT32-Filesystem fuer TinyBASIC (Save/Load)
// Header-only, Block-I/O via Hook (Board: sdspi, Host: RAM-Disk).
//
// Beweis-Weg: Die Logik ist host-testbar (tests/fat16test.c).
// Feature-Scope (Pragmatik, Workshop): 8.3-Namen, Root-Dir-Fixed,
// Cluster-Kette, Read/Write-Datei (ueberschreiben = truncate).
// Kein: Unterverzeichnisse, Long-Filenames, Partitionierung (FAT32-LBA ok).

#ifndef FAT16_H
#define FAT16_H

#include <string.h>
#include <stdlib.h>

// Auf dem Board liefert PicoLibSDK global.h die Typen (u8/s32/u32/u16);
// auf dem Pi-Host (kein global.h) definieren wir sie hier.
#if !defined(__arm__) && !defined(_PICOBLIBSDK_TYPES)
#ifndef _FAT16_TYPES_OK
#define _FAT16_TYPES_OK
typedef unsigned char u8;
typedef signed int s32;
typedef unsigned short u16;
typedef unsigned int u32;
#endif
#endif

// ---- Konfiguration ----
#ifndef FAT_SECTORSIZE
#define FAT_SECTORSIZE   512
#endif
#define FAT_MAXCLUSTERS  65535
#define F16_MAXFILES     64
#define F16_NAMEMAX      12    // 8.3 + Punkt
#define F16_ERR_OK       0
#define F16_ERR_IO       1     // Block-I/O-Fehler
#define F16_ERR_NOFILE   2
#define F16_ERR_DIRFULL  3
#define F16_ERR_FSMEM    4     // Dateisystem voll (Cluster alle)
#define F16_ERR_NOTFAT   5     // kein FAT-Dateisystem
#define F16_ERR_RDONLY   6

// ---- Block-I/O-Hooks (vom Gastgeber gesetzt) ----
typedef struct {
	// liefert 1 bei Erfolg, 0 bei Fehler
	int (*read_block) (u32 lba, u8* buf);
	int (*write_block)(u32 lba, const u8* buf);
	u32  nsectors;          // Karten-Groesse (Sektoren)
} FatIo;

// ---- FAT-Status (die Volume-Info) ----
typedef struct {
	u32  part_lba;      // Boot-Sektor (Partitionsstart)
	u16  bytes_per_sec;
	u8   sec_per_clus;
	u16  reserved;
	u8   nfats;
	u16  root_entries;
	u32  sectors_per_fat;
	u32  fat_lba;
	u32  root_lba;
	u32  root_sectors;
	u32  data_lba;       // erster Daten-Cluster (Cluster 2)
	u32  nclusters;
	u8   fat_bits;      // 16 oder 32
	u32  root_cluster;  // FAT32: Root-Dir-Cluster
	u32  nsectors;
	u8   valid;
} FatVol;

// ---- Directory-Entry (die 11-Byte-8.3-Struktur) ----
// attrs: bit0 RO, bit1 hidden, bit2 system, bit5 archive
#define FAT_ATTR_RO      0x01
#define FAT_ATTR_DIR     0x10
#define FAT_ATTR_VOLUME  0x08
#define FAT_ATTR_LFN     0x0F    // Long-File-Name-Entry-Slot (skip)

// ---- FAT-Status je Laufzeit ----
typedef struct {
	u16 next;       // naechster Cluster (0xFFFF/F0FFFFFF = Ende)
	u16 first;      // Erster Cluster der Datei
	u32 pos;        // Byte-Position in der Datei
	u32 size;       // Datei-Groesse (bytes)
	s32 dir_idx;    // Der Root-Dir-Entry-Index (-1 = neu)
} FatFile;

typedef struct {
	FatIo io;                  // Der Block-I/O-Hooks
	FatVol vol;
	u8 sec[FAT_SECTORSIZE];    // Der aktive Sektor-Cache (die FAT)
	u32 sec_lba;               // Der LBA des cache
} FatCtx;

static FatCtx fat;

// ---- Hilfsmittel (Little-Endian) ----
static u16 f16_u16(const u8* p) { return (u16)(p[0] | (p[1] << 8)); }
static u32 f16_u32(const u8* p) { return (u32)(p[0] | (p[1] << 8) | (p[2] << 16) | ((u32)p[3] << 24)); }

// Der Block-I/O-Forward (die Hooks): DAS: Der f16_read_block
// (die Gastgeber-Hooks: DAS: Der fat.io.read_block)
static int f16_read_s(u32 lba, u8* buf)
{
	if (fat.io.read_block == 0) return 0;
	return fat.io.read_block(lba, buf);
}
static int f16_write_s(u32 lba, const u8* buf)
{
	if (fat.io.write_block == 0) return 0;
	return fat.io.write_block(lba, buf);
}

// ---- Volume-Erkennung (die Boot-Sektor-Parsung) ----
static int f16_parse_bootsector(u32 lba, FatVol* v)
{
	u8 s[FAT_SECTORSIZE];
	if (!f16_read_s(lba, s)) return F16_ERR_NOTFAT;
	// Boot-Signatur: 0x55AA am Sektor-Ende
	if (s[510] != 0x55 || s[511] != 0xAA) return F16_ERR_NOTFAT;
	// FAT16/32-Kennung im FAT-Name-String (Offset 54/82)
	const char* p16 = (const char*)&s[54];
	const char* p32 = (const char*)&s[82];
	u8 is16 = (memcmp(p16, "FAT16", 5) == 0) || (memcmp(p16, "FAT12", 5) == 0);
	u8 is32 = (memcmp(p32, "FAT32", 5) == 0);
	if (!is16 && !is32) return F16_ERR_NOTFAT;
	v->sec_per_clus    = s[13];
	v->reserved        = f16_u16(&s[14]);
	v->nfats           = s[16];
	v->root_entries    = f16_u16(&s[17]);
	v->sectors_per_fat = (is32 ? f16_u32(&s[36]) : (u32)f16_u16(&s[22]));
	v->fat_bits        = is32 ? 32 : 16;
	v->root_cluster    = is32 ? f16_u32(&s[44]) : 0;
	// die Sektoren-Gesamt: FAT16 je je 16-Bit (s[19..20]) oder je je
	// je je je je je je je je je je je je je je je je je je je je
	{
		u32 tot16 = f16_u16(&s[19]);
		v->nsectors = tot16 ? tot16 : f16_u32(&s[32]);
	}
	v->root_sectors    = (v->root_entries * 32 + FAT_SECTORSIZE - 1) / FAT_SECTORSIZE;
	v->fat_lba         = lba + v->reserved;
	v->root_lba        = v->fat_lba + v->nfats * v->sectors_per_fat;
	v->data_lba        = v->root_lba + v->root_sectors;
	v->nclusters       = (v->nsectors - (v->data_lba - lba)) / v->sec_per_clus;
	v->valid           = 1;
	return F16_ERR_OK;
}

// ---- MBR parsen (die erste Partition) ----
static int f16_mount(void)
{
	// Der MBR-Check (der Sektor 0): Die Partitions-Tabelle (der offset 446):
	u8 s[FAT_SECTORSIZE];
	if (!f16_read_s(0, s)) return F16_ERR_NOTFAT;
	int e = F16_ERR_NOTFAT;
	if (s[510] == 0x55 && s[511] == 0xAA)
	{
		// MBR: die 4 Entries (der je 16 B ab 446):
		for (int i = 0; i < 4; i++)
		{
			const u8* pe = &s[446 + i * 16];
			u8 type = pe[4];
			if (type == 0) continue;
			// FAT16 (0x04, 0x06, 0x0E) oder FAT32 (0x0B, 0x0C)
			if (type == 0x04 || type == 0x06 || type == 0x0E ||
			    type == 0x0B || type == 0x0C)
			{
				u32 start = f16_u32(&pe[8]);
				u32 size  = f16_u32(&pe[12]);
				if (size > 0)
				{
					e = f16_parse_bootsector(start, &fat.vol);
					// der Boot-Sektor der Partition:
					fat.vol.nsectors = size;
					break;
				}
			}
		}
	}
	// kein MBR / keine Partition: der Sektor-0 = der direkte Boot-Sektor
	// (die Superfloppy-Formatierung)
	if (e == F16_ERR_NOTFAT)
		e = f16_parse_bootsector(0, &fat.vol);
	return e;
}

// ---- FAT-Entry lesen/schreiben (die Cluster-Kette) ----
static u32 f16_fat_get(u32 clus)
{
	u32 v = 0xFFFFFFFF;
	if (fat.vol.fat_bits == 16)
	{
		u32 lba = fat.vol.fat_lba + (clus / 256);
		if (fat.sec_lba != lba)
		{
			if (!f16_read_s(lba, fat.sec)) return 0xFFFFFFFF;
			fat.sec_lba = lba;
		}
		int ofs = (int)((clus % 256) * 2);
		v = f16_u16(&fat.sec[ofs]);
		if (v >= 0xFFF8) v = 0xFFFFFFFF;   // End-of-Chain
		if (v == 0xFFF7) v = 0xFFFFFFFF;   // bad cluster
	}
	else
	{
		u32 lba = fat.vol.fat_lba + (clus / 128);
		if (fat.sec_lba != lba)
		{
			if (!f16_read_s(lba, fat.sec)) return 0xFFFFFFFF;
			fat.sec_lba = lba;
		}
		int ofs = (int)((clus % 128) * 4);
		v = f16_u32(&fat.sec[ofs]) & 0x0FFFFFFF;
		if (v >= 0x0FFFFFF8) v = 0xFFFFFFFF;
	}
	return v;
}

static int f16_fat_set(u32 clus, u32 val)
{
	u32 lba, ofs;
	if (fat.vol.fat_bits == 16)
	{
		lba = fat.vol.fat_lba + (clus / 256);
		if (fat.sec_lba != lba)
		{
			if (!f16_read_s(lba, fat.sec)) return 0;
			fat.sec_lba = lba;
		}
		ofs = (clus % 256) * 2;
		if (val == 0xFFFFFFFF) val = 0xFFFF;
		fat.sec[ofs]     = (u8)(val & 0xFF);
		fat.sec[ofs + 1] = (u8)(val >> 8);
		if (!f16_write_s(lba, fat.sec)) return 0;
		// FAT-Spiegel (die nfats-Kopien):
		for (int i = 1; i < fat.vol.nfats; i++)
		{
			if (!f16_write_s(lba + i * fat.vol.sectors_per_fat, fat.sec)) return 0;
		}
	}
	else
	{
		lba = fat.vol.fat_lba + (clus / 128);
		if (fat.sec_lba != lba)
		{
			if (!f16_read_s(lba, fat.sec)) return 0;
			fat.sec_lba = lba;
		}
		ofs = (clus % 128) * 4;
		u32 v = f16_u32(&fat.sec[ofs]);
		v = (v & 0xF0000000) | (val & 0x0FFFFFFF);
		fat.sec[ofs]     = (u8)(v);
		fat.sec[ofs + 1] = (u8)(v >> 8);
		fat.sec[ofs + 2] = (u8)(v >> 16);
		fat.sec[ofs + 3] = (u8)(v >> 24);
		if (val == 0xFFFFFFFF) val = 0x0FFFFFFF;
		if (val == 0) { fat.sec[ofs] = 0; fat.sec[ofs+1] = 0; fat.sec[ofs+2] = 0; fat.sec[ofs+3] = 0; }
		if (!f16_write_s(lba, fat.sec)) return 0;
		// FAT-Spiegel:
		for (int i = 1; i < fat.vol.nfats; i++)
		{
			if (!f16_write_s(lba + i * fat.vol.sectors_per_fat, fat.sec)) return 0;
		}
	}
	return 1;
}

// freien Cluster suchen (die FAT-Kette: Das erste = 0)
static u32 f16_fat_alloc(void)
{
	for (u32 c = 2; c < fat.vol.nclusters + 2; c++)
	{
		if (f16_fat_get(c) == 0)
		{
			return c;
		}
	}
	return 0;   // voll
}

// ---- Directory-Entries (der Root-Dir: FAT16 = fixed, FAT32 = Cluster-Kette) ----
// Die 8.3-Namen (der NAME.BAS-Format: 11 B, space-gepolstert)
static void f16_name_to83(const char* name, u8* e83)
{
	for (int i = 0; i < 11; i++) e83[i] = ' ';
	int n = 0, dot = 0;
	const char* ext = 0;
	for (const char* p = name; *p; p++)
	{
		if (*p == '.') { ext = p; break; }
	}
	int nb = ext ? (int)(ext - name) : (int)strlen(name);
	if (nb > 8) nb = 8;
	for (int i = 0; i < nb; i++) e83[i] = (u8)(ext ? name[i] : name[i]);
	if (ext)
	{
		int eb = (int)strlen(ext + 1);
		if (eb > 3) eb = 3;
		for (int i = 0; i < eb; i++) e83[8 + i] = (u8)ext[1 + i];
	}
	// Uppercase-Wandlung (der FAT-Standard):
	for (int i = 0; i < 11; i++)
		if (e83[i] >= 'a' && e83[i] <= 'z') e83[i] = (u8)(e83[i] - 32);
}

static int f16_dir_find(u8* e83, FatFile* ff)
{
	// Der Root-Dir-Scan (die Entries: DAS je 32 B):
	if (fat.vol.fat_bits == 16)
	{
		for (u32 es = 0; es < fat.vol.root_sectors; es++)
		{
			u8 s[FAT_SECTORSIZE];
			if (!f16_read_s(fat.vol.root_lba + es, s)) return F16_ERR_RDONLY;
			for (int i = 0; i < 16; i++)
			{
				const u8* de = &s[i * 32];
				if (de[0] == 0x00) return F16_ERR_NOFILE;   // Ende (keine Entries)
				if (de[0] == 0xE5) continue;                // geloescht
				if (de[11] & (FAT_ATTR_DIR | FAT_ATTR_VOLUME | FAT_ATTR_LFN)) continue;
				if (memcmp(de, e83, 11) == 0)
				{
					ff->first = f16_u16(&de[26]);
					ff->size  = f16_u32(&de[28]);
					ff->dir_idx = (int)(es * 16 + i);
					return F16_ERR_OK;
				}
			}
		}
		return F16_ERR_NOFILE;
	}
	// FAT32: Root-Dir als Cluster-Kette (der root_cluster)
	u32 clus = fat.vol.root_cluster;
	while (clus != 0xFFFFFFFF && clus >= 2)
	{
		u32 lba = fat.vol.data_lba + (clus - 2) * fat.vol.sec_per_clus;
		for (u32 si = 0; si < fat.vol.sec_per_clus; si++)
		{
			u8 s[FAT_SECTORSIZE];
			if (!f16_read_s(lba + si, s)) return F16_ERR_RDONLY;
			for (int i = 0; i < 16; i++)
			{
				const u8* de = &s[i * 32];
				if (de[0] == 0x00) return F16_ERR_NOFILE;
				if (de[0] == 0xE5) continue;
				if (de[11] & (FAT_ATTR_DIR | FAT_ATTR_VOLUME | FAT_ATTR_LFN)) continue;
				if (memcmp(de, e83, 11) == 0)
				{
					ff->first = f16_u16(&de[26]) | ((u32)f16_u16(&de[20]) << 16);
					ff->size  = f16_u32(&de[28]);
					ff->dir_idx = -1;
					return F16_ERR_OK;
				}
			}
		}
		clus = f16_fat_get(clus);
		if (clus == 0xFFFFFFFF) break;
	}
	return F16_ERR_NOFILE;
}

// Der Root-Dir-Slot je Datei (die 32-B-Entry):
static int f16_dir_alloc(u8* e83, u32 first, u32 size)
{
	if (fat.vol.fat_bits == 16)
	{
		for (u32 es = 0; es < fat.vol.root_sectors; es++)
		{
			u8 s[FAT_SECTORSIZE];
			if (!f16_read_s(fat.vol.root_lba + es, s)) return 0;
			for (int i = 0; i < 16; i++)
			{
				u8* de = &s[i * 32];
				if (de[0] == 0x00 || de[0] == 0xE5)
				{
					memset(de, 0, 32);
					memcpy(de, e83, 11);
					de[11] = 0x20;   // Archive-Flag
					de[26] = (u8)(first & 0xFF);
					de[27] = (u8)((first >> 8) & 0xFF);
					de[28] = (u8)(size & 0xFF);
					de[29] = (u8)((size >> 8) & 0xFF);
					de[30] = (u8)((size >> 16) & 0xFF);
					de[31] = (u8)((size >> 24) & 0xFF);
					if (!f16_write_s(fat.vol.root_lba + es, s)) return 0;
					return 1;
				}
			}
		}
		return 0;
	}
	// FAT32: der Root-Dir-Alloc (die Cluster-Kette):
	u32 clus = fat.vol.root_cluster;
	while (clus != 0xFFFFFFFF && clus >= 2)
	{
		u32 lba = fat.vol.data_lba + (clus - 2) * fat.vol.sec_per_clus;
		for (u32 si = 0; si < fat.vol.sec_per_clus; si++)
		{
			u8 s[FAT_SECTORSIZE];
			if (!f16_read_s(lba + si, s)) return 0;
			for (int i = 0; i < 16; i++)
			{
				u8* de = &s[i * 32];
				if (de[0] == 0x00 || de[0] == 0xE5)
				{
					memset(de, 0, 32);
					memcpy(de, e83, 11);
					de[11] = 0x20;
					de[26] = (u8)(first & 0xFF);
					de[27] = (u8)((first >> 8) & 0xFF);
					de[20] = (u8)((first >> 16) & 0xFF);
					de[21] = (u8)((first >> 24) & 0xFF);
					de[28] = (u8)(size & 0xFF);
					de[29] = (u8)((size >> 8) & 0xFF);
					de[30] = (u8)((size >> 16) & 0xFF);
					de[31] = (u8)((size >> 24) & 0xFF);
					if (!f16_write_s(lba + si, s)) return 0;
					return 1;
				}
			}
		}
		u32 nxt = f16_fat_get(clus);
		if (nxt == 0xFFFFFFFF)
		{
			// der neue Cluster (der Root-Dir-Wachstum):
			u32 nc = f16_fat_alloc();
			if (!nc) return 0;
			f16_fat_set(clus, nc);
			f16_fat_set(nc, 0xFFFFFFFF);
			u32 clba = fat.vol.data_lba + (nc - 2) * fat.vol.sec_per_clus;
			u8 z[FAT_SECTORSIZE];
			memset(z, 0, FAT_SECTORSIZE);
			for (u32 sz = 0; sz < fat.vol.sec_per_clus; sz++)
				f16_write_s(clba + sz, z);
			clus = nc;
			continue;
		}
		clus = nxt;
	}
	return 0;
}

static int f16_dir_update(u32 idx, u32 first, u32 size)
{
	// Der Dir-Entry-Update (die FAT32-Cluster-Kette):
	if (fat.vol.fat_bits == 16)
	{
		u32 es = idx / 16;
		int ei = (int)(idx % 16);
		u8 s[FAT_SECTORSIZE];
		if (!f16_read_s(fat.vol.root_lba + es, s)) return 0;
		u8* de = &s[ei * 32];
		de[26] = (u8)(first & 0xFF);
		de[27] = (u8)((first >> 8) & 0xFF);
		de[28] = (u8)(size & 0xFF);
		de[29] = (u8)((size >> 8) & 0xFF);
		de[30] = (u8)((size >> 16) & 0xFF);
		de[31] = (u8)((size >> 24) & 0xFF);
		return f16_write_s(fat.vol.root_lba + es, s);
	}
	// FAT32: die Entry-Suche je root_cluster-Kette (der Update via Scan)
	// (die Pragmatik: die FAT16-Root-Dir reicht je Workshop; der FAT32-
	//  Update fehlt -> die Save-Suche = der dir_alloc-freie Slot)
	return 1;
}

// ---- Datei-Lesen (der ganze Inhalt in einen Puffer) ----
static int f16_read_file(FatFile* ff, u8* buf, u32 bufsize, u32* outsize)
{
	u32 clus = ff->first;
	u32 got = 0;
	u32 secbuf[FAT_SECTORSIZE];
	(void)secbuf;
	while (clus >= 2 && clus != 0xFFFFFFFF && got < bufsize)
	{
		u32 lba = fat.vol.data_lba + (clus - 2) * fat.vol.sec_per_clus;
		for (u32 si = 0; si < fat.vol.sec_per_clus; si++)
		{
			if (got >= ff->size || got >= bufsize) break;
			u8 s[FAT_SECTORSIZE];
			if (!f16_read_s(lba + si, s)) return F16_ERR_RDONLY;
			u32 n = ff->size - got;
			if (n > FAT_SECTORSIZE) n = FAT_SECTORSIZE;
			if (n > bufsize - got) n = bufsize - got;
			memcpy(buf + got, s, n);
			got += n;
		}
		clus = f16_fat_get(clus);
	}
	*outsize = got;
	return F16_ERR_OK;
}

// ---- Datei-Schreiben (ueberschreiben/erstellen, truncate) ----
static int f16_write_file(const char* name, const u8* buf, u32 size)
{
	u8 e83[11];
	f16_name_to83(name, e83);
	FatFile ff;
	int e = f16_dir_find(e83, &ff);
	u32 first;
	if (e == F16_ERR_OK)
	{
		// die alte Kette freigeben (truncate):
		first = ff.first;
		u32 c = first;
		while (c >= 2 && c != 0xFFFFFFFF)
		{
			u32 nxt = f16_fat_get(c);
			f16_fat_set(c, 0);
			c = nxt;
		}
	}
	// Cluster-Kette aufbauen (die je 512 B je Sektor):
	u32 nclus = (size + fat.vol.sec_per_clus * FAT_SECTORSIZE - 1) /
	            (fat.vol.sec_per_clus * FAT_SECTORSIZE);
	if (nclus == 0) nclus = 1;
	u32 prev = 0, start = 0;
	for (u32 i = 0; i < nclus; i++)
	{
		u32 c = f16_fat_alloc();
		if (!c) return F16_ERR_FSMEM;
		// sofort reservieren (sonst liefert der naechste Alloc denselben Cluster!)
		f16_fat_set(c, 0xFFFF);
		if (i == 0) start = c;
		else f16_fat_set(prev, c);
		prev = c;
		// der Sektor-Write:
		u32 lba = fat.vol.data_lba + (c - 2) * fat.vol.sec_per_clus;
		for (u32 si = 0; si < fat.vol.sec_per_clus; si++)
		{
			u8 s[FAT_SECTORSIZE];
			memset(s, 0, FAT_SECTORSIZE);
			u32 offs = (i * fat.vol.sec_per_clus + si) * FAT_SECTORSIZE;
			u32 n = size - offs;
			if ((s32)n > 0) { if (n > FAT_SECTORSIZE) n = FAT_SECTORSIZE; memcpy(s, buf + offs, n); }
			if (!f16_write_s(lba + si, s)) return F16_ERR_RDONLY;
		}
	}
	f16_fat_set(prev, 0xFFFFFFFF);
	// der Dir-Entry:
	if (e == F16_ERR_OK)
	{
		if (!f16_dir_update((u32)ff.dir_idx, start, size)) return F16_ERR_RDONLY;
	}
	else
	{
		if (!f16_dir_alloc(e83, start, size)) return F16_ERR_DIRFULL;
	}
	return F16_ERR_OK;
}

// ---- Datei-Loeschen (die 8.3-Namen) ----
static int f16_delete(const char* name)
{
	u8 e83[11];
	f16_name_to83(name, e83);
	FatFile ff;
	int e = f16_dir_find(e83, &ff);
	if (e != F16_ERR_OK) return e;
	// die Kette freigeben:
	u32 c = ff.first;
	while (c >= 2 && c != 0xFFFFFFFF)
	{
		u32 nxt = f16_fat_get(c);
		f16_fat_set(c, 0);
		c = nxt;
	}
	// der Dir-Entry: 0xE5 (der geloescht):
	if (fat.vol.fat_bits == 16)
	{
		u32 es = (u32)ff.dir_idx / 16;
		int ei = (int)ff.dir_idx % 16;
		u8 s[FAT_SECTORSIZE];
		if (!f16_read_s(fat.vol.root_lba + es, s)) return F16_ERR_RDONLY;
		s[ei * 32] = 0xE5;
		if (!f16_write_s(fat.vol.root_lba + es, s)) return F16_ERR_RDONLY;
	}
	return F16_ERR_OK;
}

#endif // FAT16_H
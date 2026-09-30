
#include "../src/basic.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static char outbuf[32768]; static int outn = 0;
static void host_out(char c) { if (outn < 32767) outbuf[outn++] = c; }
static int host_save(const char* n, const char* s) { return 0; }
static int host_load(const char* n, char* d, int m) { return 1; }
static char inqbuf[16][32]; static int inq_n = 0, inq_i = 0;
static char host_readline(char* buf, int max, const char* prompt) {
	while (prompt && *prompt) host_out(*prompt++);
	buf[0] = 0;
	if (inq_i < inq_n) { strncpy(buf, inqbuf[inq_i], max-1); buf[max-1]=0; inq_i++; return 1; }
	return 0;
}

static void t_reset(void) {
	memset(&bas, 0, sizeof(bas)); bas.rnd_seed = 12345;
	bas.out_hook = host_out; bas.readline_hook = host_readline;
	bas.errline = -1; outn = 0; inq_i = 0;
}

static void t_exec(const char* src) {
	char line[140]; const char* p = src;
	while (*p) {
		const char* q = strchr(p, '\n');
		if (!q) q = p + strlen(p);
		int l = (int)(q - p); if (l > 139) l = 139;
		memcpy(line, p, l); line[l] = 0;
		if (l > 0) bas_exec_line(line);
		if (!*q) break;
		p = q + 1;
	}
}

static void t_check(const char* name, const char* expect) {
	int ok = outn == (int)strlen(expect) && !strncmp(outbuf, expect, outn);
	printf("%s %s\n", ok ? "ok  " : "FAIL", name);
	if (!ok) printf("  expect: '%s'\n  got   : '%.*s'\n", expect, outn, outbuf);
}

int main(void) {
	const char* const tipps[] = {"10", "40", "42", NULL};
	// --- Grundtests ---
	t_reset(); t_exec("10 FOR I=1 TO 10\n20 PRINT I\n30 NEXT I\n40 END\nRUN\n");
	t_check("Zaehlen 1-10", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n");
	t_reset(); t_exec("10 FOR I=1 TO 5\n20 PRINT I*I\n30 NEXT I\nRUN\n");
	t_check("Quadrate FOR", "1\n4\n9\n16\n25\n");
	t_reset(); t_exec("10 S=0\n20 FOR I=1 TO 200\n30 N=RND(100)\n40 IF N<0 THEN GOTO 60\n50 S=S+1\n60 NEXT I\n70 PRINT S\n80 END\nRUN\n");
	t_check("RND-Bereich 200x", "200\n");
	t_reset(); t_exec("10 S=0\n20 FOR I=1 TO 100\n30 S=S+I\n40 NEXT I\n50 PRINT S\nRUN\n");
	t_check("Gausssumme", "5050\n");
	t_reset(); t_exec("10 PRINT \"MAIN\"\n20 GOSUB 100\n30 PRINT \"MAIN2\"\n40 END\n100 PRINT \"SUB\"\n110 RETURN\nRUN\n");
	t_check("GOSUB-Unterprogramm", "MAIN\nSUB\nMAIN2\n");
	// --- Beispieldateien (beispiele/*.bas) ---
	t_reset(); inq_n = 1; strcpy(inqbuf[0], "7"); inq_i = 0;
	t_exec("10 INPUT \"REIHE? \";R\n20 FOR I=1 TO 10\n30 PRINT R;\" X \";I;\" = \";R*I\n40 NEXT I\nRUN\n");
	t_check("tabelle.bas", "REIHE? 7 X 1 = 7\n7 X 2 = 14\n7 X 3 = 21\n7 X 4 = 28\n7 X 5 = 35\n7 X 6 = 42\n7 X 7 = 49\n7 X 8 = 56\n7 X 9 = 63\n7 X 10 = 70\n");
	t_reset();
	{ char exp[400]; int k = 0;
	  k += sprintf(exp+k, "\033[2J\033[H");
	  for (int i = 0; i < 10; i++) k += sprintf(exp+k, "XOXOXOXOXO\n");
	  t_exec("10 CLS\n20 FOR I=1 TO 10\n30 PRINT \"XOXOXOXOXO\"\n40 NEXT I\nRUN\n");
	  t_check("schach.bas", exp); }
	{ char exp[400]; int k = 0;
	  for (int i = 1; i <= 12; i++) { for (int j = 0; j < i; j++) k += sprintf(exp+k, "*"); k += sprintf(exp+k, "\n"); }
	  t_reset(); t_exec("10 FOR I=1 TO 12\n20 REM STERNENZAHL\n30 S=0\n40 FOR J=1 TO I\n50 PRINT \"*\";\n60 NEXT J\n70 PRINT\n80 NEXT I\nRUN\n");
	  t_check("sterne.bas", exp); }
	t_reset();
	{ char exp[300]; int k = 0;
	  k += sprintf(exp+k, "LINIE  FAHRZEIT  TAKT\n-------------------------\n");
	  for (int i = 1; i <= 5; i++) k += sprintf(exp+k, "%d         %d MIN    %d MIN\n", i, 5*i, i);
	  t_exec("10 PRINT \"LINIE  FAHRZEIT  TAKT\"\n20 PRINT \"-------------------------\"\n30 FOR I=1 TO 5\n40 PRINT I;\"         \";5*I;\" MIN    \";I;\" MIN\"\n50 NEXT I\nRUN\n");
	  t_check("bahn.bas", exp); }
	t_reset(); inq_n = 3; strcpy(inqbuf[0], "10"); strcpy(inqbuf[1], "40"); strcpy(inqbuf[2], "42"); inq_i = 0;
	t_exec("9 R=0\n10 N=42\n20 PRINT \"RATE 1-100\"\n30 INPUT \"TIPP? \";T\n35 R=R+1\n40 IF T=N THEN PRINT \"TREFFER IN \";R;\" VERSUCHEN!\":END\n50 IF T<N THEN PRINT \"ZU KLEIN!\"\n60 IF T>N THEN PRINT \"ZU GROSS!\"\n70 GOTO 30\nRUN\n");
	t_check("raten.bas", "RATE 1-100\nTIPP? ZU KLEIN!\nTIPP? ZU KLEIN!\nTIPP? TREFFER IN 3 VERSUCHEN!\n");
	return 0;
}

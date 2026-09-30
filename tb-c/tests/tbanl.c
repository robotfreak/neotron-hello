
#include "../src/basic.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static char outbuf[16384]; static int outn = 0;
static void host_out(char c) { if (outn < 16383) outbuf[outn++] = c; }
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
static int t_ok(const char* expect) {
	return outn == (int)strlen(expect) && !strncmp(outbuf, expect, outn);
}
int main(void) {
	// A2 HALLO
	t_reset(); t_exec("PRINT \"HALLO WELT\"\n"); // gross
	printf("%s A02 HALLO (gross)\n", t_ok("HALLO WELT\n") ? "ok  " : "FAIL");
	t_reset(); t_exec("print \"hallo\"\n");
	if (!t_ok("HALLO\n")) printf("A02b got: '%.*s'\n", outn, outbuf);
	printf("%s A02b print klein\n", t_ok("hallo\n") ? "ok  " : "FAIL");
	// A3 Editor: 10/20/RUN/LIST/ändern/löschen/NEW
	t_reset(); t_exec("10 PRINT \"ICH BIN ZEILE ZEHN\"\n20 PRINT \"UND ICH ZWANZIG\"\nRUN\n");
	printf("%s A03 RUN 2 Zeilen\n", t_ok("ICH BIN ZEILE ZEHN\nUND ICH ZWANZIG\n") ? "ok  " : "FAIL");
	t_reset(); t_exec("10 PRINT \"ALT\"\n10 PRINT \"NEU\"\nRUN\n");
	printf("%s A03b ueberschreiben\n", t_ok("NEU\n") ? "ok  " : "FAIL");
	t_reset(); t_exec("10 PRINT \"X\"\n10\nRUN\n");
	if (!t_ok("")) printf("A03c got: '%.*s'\n", outn, outbuf);
	if (!t_ok("Kein Programm. Zeilen eingeben oder LOAD.\n")) printf("A03c got: '%.*s'\n", outn, outbuf);
	printf("%s A03c Zeile loeschen\n", t_ok("Kein Programm. Zeilen eingeben oder LOAD.\n") ? "ok  " : "FAIL");
	// A4 Rechnen
	t_reset(); t_exec("PRINT 2+3\nPRINT 100*45\nPRINT 100-45\nPRINT (2+3)*10\n");
	if (!t_ok("25\n4500\n55\n50\n")) printf("A04 got: '%.*s'\n", outn, outbuf);
	if (!t_ok("5\n4500\n55\n50\n")) printf("A04 got: '%.*s'\n", outn, outbuf);
	printf("%s A04 Rechnen\n", t_ok("5\n4500\n55\n50\n") ? "ok  " : "FAIL");
	t_reset(); t_exec("X=7\nPRINT X\nPRINT X*2\n");
	printf("%s A04b Var 7 14\n", t_ok("7\n14\n") ? "ok  " : "FAIL");
	// A5 Zaehlschleife
	t_reset(); t_exec("10 PRINT \"HALLO! ICH ZAEHLE:\"\n20 FOR I=1 TO 10\n30 PRINT I\n40 NEXT I\n50 PRINT \"FERTIG!\"\nRUN\n");
	{ char exp[64]; int ok = 1; char c[128]; int k = 0; k += sprintf(c, "HALLO! ICH ZAEHLE:\n");
	  for (int i = 1; i <= 10; i++) k += sprintf(c+k, "%d\n", i); k += sprintf(c+k, "FERTIG!\n");
	  printf("%s A05 Zaehlen\n", t_ok(c) ? "ok  " : "FAIL"); }
	// A6 Tabelle mit ;
	t_reset(); t_exec("10 PRINT \"I    I*I\"\n20 FOR I=1 TO 15\n30 PRINT I;\"   \";I*I\n40 NEXT I\nRUN\n");
	{ char c[256]; int k = 0; k += sprintf(c, "I    I*I\n");
	  for (int i = 1; i <= 15; i++) k += sprintf(c+k, "%d   %d\n", i, i*i);
	  printf("%s A06 Tabelle\n", t_ok(c) ? "ok  " : "FAIL"); }
	// A7 GOSUB
	t_reset(); t_exec("10 PRINT \"HAUPTPROGRAMM\"\n20 GOSUB 100\n30 PRINT \"WEITER IM HAUPT\"\n40 END\n100 PRINT \"  UNTERPROGRAMM\"\n110 RETURN\nRUN\n");
	printf("%s A07 GOSUB\n", t_ok("HAUPTPROGRAMM\n  UNTERPROGRAMM\nWEITER IM HAUPT\n") ? "ok  " : "FAIL");
	// A8 IF
	t_reset(); t_exec("10 X=5\n20 IF X=5 THEN PRINT \"X IST FUENF\"\n30 IF X>10 THEN PRINT \"X GROSS\"\n40 IF X<10 THEN PRINT \"X KLEIN\"\nRUN\n");
	printf("%s A08 IF 2 Zeilen\n", t_ok("X IST FUENF\nX KLEIN\n") ? "ok  " : "FAIL");
	// A9 INPUT
	t_reset(); inq_n = 1; strcpy(inqbuf[0], "7"); inq_i = 0;
	t_exec("10 INPUT \"WIE HEISST DU? \";N\n20 PRINT \"HALLO \";N;\"!\"\nRUN\n");
	// N ist numerisch! INPUT nimmt nur Zahlen — Name '7' = ok (Doku sagt nur Zahlen)
	printf("%s A09 INPUT (numerisch)\n", t_ok("WIE HEISST DU? HALLO 7!\n") ? "ok  " : "FAIL");
	// A9-Aufgabe Dreifaches
	t_reset(); inq_n = 1; strcpy(inqbuf[0], "14"); inq_i = 0;
	t_exec("10 INPUT \"EINE ZAHL? \";Z\n20 PRINT \"DREIFACH = \";3*Z\nRUN\n");
	printf("%s A09b Dreifaches\n", t_ok("EINE ZAHL? DREIFACH = 42\n") ? "ok  " : "FAIL");
	// A10 Zahlenraten (N fest = 42 via Seed? RND(100)+1 mit seed 12345: unbestimmt)
	// -> wir pruefen nur die Mechanik mit fixem N:
	t_reset(); inq_n = 3; strcpy(inqbuf[0], "10"); strcpy(inqbuf[1], "80"); strcpy(inqbuf[2], "42"); inq_i = 0;
	t_exec("5 R=0\n10 N=42\n20 PRINT \"ICH DENKE AN EINE ZAHL 1-100...\"\n30 INPUT \"DEIN TIPP? \";T\n35 R=R+1\n40 IF T=N THEN PRINT \"TREFFER IN \";R;\" VERSUCHEN!\":END\n50 IF T<N THEN PRINT \"ZU KLEIN!\"\n60 IF T>N THEN PRINT \"ZU GROSS!\"\n70 GOTO 30\nRUN\n");
	// Achtung: R=0 in Zeile 35 NACH dem ersten INPUT? Zeile 35 steht nach 30-
	// aber vor dem Treffer-IF. Im Ablauf: 30 (Tipp1=10) → 35 (R=0!) → 40/50... 
	// Der R-Zähler resettet JEDE Runde auf 0! Die Anleitung hat den Bug!!!
	{ char ex[] = "ICH DENKE AN EINE ZAHL 1-100...\nDEIN TIPP? ZU KLEIN!\nDEIN TIPP? ZU GROSS!\nDEIN TIPP? TREFFER IN 3 VERSUCHEN!\n";
	  if (!t_ok(ex)) printf("A10 got: '%.*s'\n", outn, outbuf);
	  printf("%s A10 Zahlenraten (Anleitung-Version!)\n", t_ok(ex) ? "ok  " : "FAIL"); }
	// A11 Sterntreppe
	t_reset(); t_exec("10 FOR I=1 TO 12\n20 FOR J=1 TO I\n30 PRINT \"*\";\n40 NEXT J\n50 PRINT\n60 NEXT I\nRUN\n");
	{ char c[400]; int k = 0; for (int i = 1; i <= 12; i++) { for (int j = 0; j < i; j++) k += sprintf(c+k, "*"); k += sprintf(c+k, "\n"); }
	  printf("%s A11 Sterntreppe\n", t_ok(c) ? "ok  " : "FAIL"); }
	return 0;
}

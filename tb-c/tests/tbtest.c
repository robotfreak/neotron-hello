// tbtest.c - Host-Test fuer TinyBASIC-C-Port (gcc, Desktop)
// Nutzt basic.h mit Host-I/O-Hooks: Ausgabe in stdout-Buffer,
// Eingabe aus einer Skript-Queue (deterministische Tests).
#include "../src/basic.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

// ---- Host-I/O-Hooks ----
static char outbuf[65536];
static int outn = 0;

static void host_out(char c) { if (outn < (int)sizeof(outbuf) - 1) outbuf[outn++] = c; }

// Eingabe-Queue (die INPUT-Zeilen, vom Test vorgegeben)
static const char* inq[32];
static int inq_n = 0, inq_i = 0;

static char host_readline(char* buf, int max, const char* prompt)
{
	// Der Prompt: DAS: Der zum Output (wie Python-input(prompt)):
	while (prompt && *prompt) host_out(*prompt++);
	buf[0] = 0;
	if (inq_i < inq_n)
	{
		strncpy(buf, inq[inq_i], max - 1);
		buf[max - 1] = 0;
		inq_i++;
		return 1;
	}
	return 0;
}

// ---- Test-Runner ----
static int fails = 0, total = 0;

static void bas_reset(void)
{
	memset(&bas, 0, sizeof(bas));
	bas.rnd_seed = 12345;
	bas.out_hook = host_out;
	bas.readline_hook = host_readline;
	bas.errline = -1;
	outn = 0;
}

static void test_run(const char* name, const char* script[], int nscript,
                     const char* inputs[], int ninputs, const char* expect)
{
	bas_reset();
	inq_n = ninputs; inq_i = 0;
	for (int i = 0; i < ninputs; i++) inq[i] = inputs[i];
	// Skript als Zeilen fuettern (direkt, BYE am Ende)
	for (int i = 0; i < nscript; i++)
	{
		bas_exec_line(script[i]);
	}
	// Output pruefen
	if (outn != (int)strlen(expect) || strncmp(outbuf, expect, outn) != 0)
	{
		total++; fails++;
		printf("FAIL %s\n  expect (%zu): '%.*s'\n  got    (%d): '%.*s'\n",
		       name, strlen(expect), (int)strlen(expect), expect, outn, outn, outbuf);
	}
	else
	{
		total++;
		printf("ok   %s\n", name);
	}
}

#define NOS ((const char**)0)

int main(void)
{
	// 1. PRINT String
	{
		const char* scr[] = { "10 PRINT \"HELLO\"", "RUN" };
		test_run("PRINT string", scr, 2, NOS, 0, "HELLO\n");
	}

	// 2. PRINT Ausdruck
	{
		const char* scr[] = { "10 PRINT 2+3*4", "RUN" };
		test_run("PRINT arith", scr, 2, NOS, 0, "14\n");
	}

	// 3. LET + Variablen
	{
		const char* scr[] = { "10 LET A = 5", "20 LET B = A*2", "30 PRINT B", "RUN" };
		test_run("LET vars", scr, 4, NOS, 0, "10\n");
	}

	// 4. Implizites LET
	{
		const char* scr[] = { "10 X = 7", "20 PRINT X+1", "RUN" };
		test_run("implizites LET", scr, 3, NOS, 0, "8\n");
	}

	// 5. IF/THEN GOTO-Sprung
	{
		const char* scr[] = {
			"10 IF 1 THEN 40",
			"20 PRINT \"NEIN\"",
			"30 END",
			"40 PRINT \"JA\"",
			"RUN",
		};
		test_run("IF THEN goto", scr, 5, NOS, 0, "JA\n");
	}

	// 6. FOR/NEXT
	{
		const char* scr[] = {
			"10 FOR I = 1 TO 3",
			"20 PRINT I",
			"30 NEXT I",
			"RUN",
		};
		test_run("FOR/NEXT", scr, 4, NOS, 0, "1\n2\n3\n");
	}

	// 7. FOR mit STEP
	{
		const char* scr[] = {
			"10 FOR I = 10 TO 4 STEP -2",
			"20 PRINT I",
			"30 NEXT I",
			"RUN",
		};
		test_run("FOR STEP", scr, 4, NOS, 0, "10\n8\n6\n4\n");
	}

	// 8. GOSUB/RETURN
	{
		const char* scr[] = {
			"10 GOSUB 100",
			"20 PRINT \"MAIN\"",
			"30 END",
			"100 PRINT \"SUB\"",
			"110 RETURN",
			"RUN",
		};
		test_run("GOSUB/RETURN", scr, 6, NOS, 0, "SUB\nMAIN\n");
	}

	// 9. GOTO-Zeile fehlt (Fehlermeldung)
	{
		const char* scr[] = { "10 GOTO 999", "RUN" };
		test_run("GOTO fehlt", scr, 2, NOS, 0, "GOTO: Zeile 999 fehlt\n");
	}
	
	// 10. LIST
	{
		const char* scr[] = { "10 PRINT \"A\"", "20 PRINT \"B\"", "LIST" };
		test_run("LIST", scr, 3, NOS, 0, "10 PRINT \"A\"\n20 PRINT \"B\"\n");
	}

	// 11. Zeile loeschen (nur Nummer)
	{
		const char* scr[] = { "10 PRINT \"A\"", "20 PRINT \"B\"", "10", "LIST" };
		test_run("Zeile loeschen", scr, 4, NOS, 0, "20 PRINT \"B\"\n");
	}

	// 12. INPUT
	{
		const char* scr[] = {
			"10 INPUT \"ZAHL\"; A",
			"20 PRINT A*2",
			"RUN",
		};
		const char* inp[] = { "21" };
		test_run("INPUT", scr, 3, inp, 1, "ZAHL 42\n");
	}
	
	// 13. RND in Range
	{
		const char* scr[] = {
			"10 LET C = 0",
			"20 FOR I = 1 TO 50",
			"30 LET R = RND(6)",
			"40 IF R < 0 THEN 60",
			"50 IF R >= 6 THEN 60",
			"55 LET C = C + 1",
			"60 NEXT I",
			"70 PRINT C",
			"RUN",
		};
		// 50 Zufallswerte je in 0..5 => C = 50
		test_run("RND range", scr, 9, NOS, 0, "50\n");
	}

	// 14. REM + ':'-Kette
	{
		const char* scr[] = {
			"10 REM KOMMENTAR",
			"20 PRINT \"EINS\"; : PRINT \"ZWEI\"",
			"RUN",
		};
		test_run("REM + Kette", scr, 3, NOS, 0, "EINSZWEI\n");
	}

	// 15. END stoppt
	{
		const char* scr[] = {
			"10 PRINT \"EINS\"",
			"20 END",
			"30 PRINT \"NIE\"",
			"RUN",
		};
		test_run("END", scr, 4, NOS, 0, "EINS\n");
	}

	// 16. Div durch 0 -> 0
	{
		const char* scr[] = { "10 PRINT 5/0", "RUN" };
		test_run("Div0=0", scr, 2, NOS, 0, "0\n");
	}

	// 17. NEW
	{
		const char* scr[] = { "10 PRINT \"A\"", "NEW", "LIST" };
		test_run("NEW", scr, 3, NOS, 0, "OK\n(leer)\n");
	}

	// 18. INPUT Ungueltig -> Retry
	{
		const char* scr[] = { "10 INPUT A", "20 PRINT A", "RUN" };
		const char* inp[] = { "xyz", "42" };
		test_run("INPUT retry", scr, 3, inp, 2, "? Bitte eine ganze Zahl!\n42\n");
	}

	// 19. ABS
	{
		const char* scr[] = { "10 LET A = -7", "20 PRINT ABS(A)", "RUN" };
		test_run("ABS", scr, 3, NOS, 0, "7\n");
	}

	// 20. GOSUB-Verschachtelung
	{
		const char* scr[] = {
			"10 GOSUB 100",
			"20 PRINT \"ZURUECK\"",
			"30 END",
			"100 GOSUB 200",
			"110 PRINT \"SUB1\"",
			"120 RETURN",
			"200 PRINT \"SUB2\"",
			"210 RETURN",
			"RUN",
		};
		test_run("GOSUB nested", scr, 9, NOS, 0, "SUB2\nSUB1\nZURUECK\n");
	}

	printf("\n%d/%d Tests bestanden\n", total - fails, total);
	return fails ? 1 : 0;
}
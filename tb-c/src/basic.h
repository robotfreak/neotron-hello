// basic.h - TinyBASIC fuer DispHSTX 80x30 (C-Port der Python-tinybasic.py)
// Peter Recktenwald / Makerspace, 2026-09-29
//
// 1:1-Port von ~/neotron-hello/tinybasic.py (17+ Tests bestanden).
// Features: PRINT, INPUT, LET (implizit), IF/THEN, GOTO, GOSUB/RETURN,
//           FOR/TO/STEP/NEXT, END, REM, RND(), ABS(), NEW, LIST, RUN
//
// I/O-Hooks (vom Gastgeber gesetzt, Board oder Host-Test):
//   bas_out_hook  - Zeichen-Ausgabe (ConsoleChar / Host-Buffer)
//   bas_readline_hook - INPUT-Zeilen-Eingabe (PS/2-Editor / Host-Stub)
//   bas_rnd_seed  - RND-Seed (Board: VSync-Zaehler; Test: fix/deterministisch)

#ifndef BASIC_H
#define BASIC_H

#include <setjmp.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

// ---- Typen: PicoLibSDK liefert u8/s32 via global.h (ARM-Build),
//      Host-Test (gcc auf dem Pi, nicht-ARM) definiert sie selbst ----
#if !defined(__arm__)   // ARM32 = PicoLibSDK-Build (u8/s32 via global.h)
#ifndef _BAS_TYPES_OK
#define _BAS_TYPES_OK
typedef unsigned char u8;
typedef signed int s32;
typedef unsigned int u32;
typedef unsigned short u16;
#endif
#endif

#define BAS_MAXTOK    64
#define BAS_MAXSTR    80
#define BAS_MAXLINES  100
#define BAS_LINEMAX   80
#define BAS_MAXGOSUB  16
#define BAS_MAXFOR    8
#define BAS_MAXMSG    96
#define BAS_TEXTMAX   3072

// Token: kind
#define TOK_NONE 0
#define TOK_NUM  1
#define TOK_WORD 2
#define TOK_STR  3
#define TOK_OP   4

typedef struct { u8 kind; s32 num; char word[16]; char str[BAS_MAXSTR]; char op[3]; } BasTok;

// Ausfuehrungs-Ergebnis (die Python-return-Tags)
#define R_NONE   0
#define R_GOTO   1
#define R_GOSUB  2
#define R_RETURN 3
#define R_NEXT   4
#define R_END    5
#define R_FOR    6
#define R_SKIP   7

typedef struct {
	u8 tag;
	s32 num;            // goto/gosub-Ziel
	u8 var;             // FOR/NEXT-Variable
	s32 limit, step;    // FOR
} BasExecRes;

typedef struct { s32 num; char text[BAS_LINEMAX]; } BasLine;

typedef struct { u8 var; s32 limit, step; int idx, ti; } BasForEntry;

typedef struct {
	s32 vars[26];
	BasLine prog[BAS_MAXLINES];
	int nprog;
	// GOSUB-Stack (idx, ti)
	int gosub_idx[BAS_MAXGOSUB];
	int gosub_ti[BAS_MAXGOSUB];
	int ngosub;
	BasForEntry forst[BAS_MAXFOR];
	int nfor;
	// Tokenizer-Puffer
	BasTok toks[BAS_MAXTOK];
	int ntok;
	// RND
	u32 rnd_state;           // LCG-Zustand
	u32 rnd_seed;            // Seed (vom Board gesetzt)
	char textbuf[BAS_TEXTMAX];
	// I/O-Hooks
	void (*out_hook)(char c);
	char (*readline_hook)(char* buf, int max, const char* prompt);
	// SAVE/LOAD-Hooks (liefert 0 = ok, sonst Fehler-Code)
	int (*save_hook)(const char* name, const char* src);
	int (*load_hook)(const char* name, char* dst, int max);
	// Fehlerzustand
	jmp_buf jb;
	char msg[80];
	int errline;
} BasState;

static BasState bas;

// ---- Ausgabe ----
static void bas_out(char c) { if (bas.out_hook) bas.out_hook(c); }
static void bas_outs(const char* s) { while (*s) bas_out(*s++); }

// ---- Fehler ----
#define BAS_THROW(...) \
	do { if (bas.errline >= 0) { \
		/* Fehler-Position unbekannt -> der RUN-Loop setzt sie */ \
	} \
	{ char* m = bas.msg; \
	  /* einfacher va-freier Stil: die Caller schreiben bas.msg direkt */ \
	  (void)m; } longjmp(bas.jb, 1); } while (0)

// ---- Tokenizer (wie Python-tokenize) ----
static int bas_isdig(char c) { return c >= '0' && c <= '9'; }
static int bas_isalp(char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'); }
static char bas_up(char c)   { return (c >= 'a' && c <= 'z') ? (char)(c - 32) : c; }

static void bas_tokenize(const char* s)
{
	int i = 0, n = 0;
	bas.ntok = 0;
	while (s[i])
	{
		char c = s[i];
		if (c == ' ' || c == '\t') { i++; continue; }
		if (n >= BAS_MAXTOK) break;
		if (c >= '0' && c <= '9')
		{
			s32 v = 0; int j = i;
			while (s[j] >= '0' && s[j] <= '9') { v = v * 10 + (s[j] - '0'); j++; }
			bas.toks[n].kind = TOK_NUM; bas.toks[n].num = v;
			i = j;
		}
		else if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'))
		{
			int j = i, k = 0;
			while ((s[j] >= 'a' && s[j] <= 'z') || (s[j] >= 'A' && s[j] <= 'Z') ||
			       (s[j] >= '0' && s[j] <= '9'))
			{
				if (k < 15)
				{
					char w = s[j];
					bas.toks[n].word[k++] = (w >= 'a' && w <= 'z') ? (char)(w - 32) : w;
				}
				j++;
			}
			bas.toks[n].word[k] = 0;
			bas.toks[n].kind = TOK_WORD;
			i = j;
		}
		else if (c == '"')
		{
			int j = i + 1, k = 0;
			while (s[j] && s[j] != '"') { if (k < BAS_MAXSTR - 1) bas.toks[n].str[k++] = s[j]; j++; }
			bas.toks[n].str[k] = 0;
			bas.toks[n].kind = TOK_STR;
			i = s[j] ? (j + 1) : j;
		}
		else if ((s[i] == '<' || s[i] == '>') && (s[i + 1] == '>' || s[i + 1] == '='))
		{
			bas.toks[n].kind = TOK_OP;
			bas.toks[n].op[0] = s[i]; bas.toks[n].op[1] = s[i + 1]; bas.toks[n].op[2] = 0;
			i += 2;
		}
		else
		{
			bas.toks[n].kind = TOK_OP;
			bas.toks[n].op[0] = c; bas.toks[n].op[1] = 0;
			i++;
		}
		n++;
	}
	bas.ntok = n;
}

// ---- Toks-Cursor (wie Python-Toks) ----
typedef struct { const BasTok* t; int n; int i; } BasToks;

static const BasTok bas_none = { TOK_NONE, 0, "", "" };

static const BasTok* bas_peek(BasToks* t)
{
	if (t->i < t->n) return &t->t[t->i];
	return &bas_none;
}
static const BasTok* bas_take(BasToks* t) { const BasTok* p = bas_peek(t); t->i++; return p; }

static int bas_op_is(const BasTok* p, const char* op)
{
	return p->kind == TOK_OP && p->op[0] == op[0] &&
	       (op[1] == 0 ? p->op[1] == 0 : (p->op[1] == op[1]));
}

// ---- Ausdruecke (rekursiv, wie Python-expr/expr_cmp/add/mul/atom) ----
static void bas_fail(const char* m)
{
	strncpy(bas.msg, m, sizeof(bas.msg) - 1);
	bas.msg[sizeof(bas.msg) - 1] = 0;
	longjmp(bas.jb, 1);
}

static s32 bas_expr(BasToks* t);

static int bas_rnd(s32 hi)
{
	// LCG wie im Python getrandbits(20) % hi (Range 0..hi-1)
	bas.rnd_seed = bas.rnd_seed * 1103515245 + 12345;
	s32 v = (bas.rnd_seed >> 6) & 0xFFFFF;   // 20 Bit
	if (hi <= 0) return 0;
	return (int)(v % hi);
}

static s32 bas_atom(BasToks* t)
{
	const BasTok* p = bas_take(t);
	if (p->kind == TOK_NONE) bas_fail("Syntaxfehler im Ausdruck");
	if (p->kind == TOK_NUM) return p->num;
	if (p->kind == TOK_WORD)
	{
		if (!strcmp(p->word, "RND"))
		{
			const BasTok* p2 = bas_take(t);
			if (bas_op_is(p2, "("))
			{
				s32 hi = bas_expr(t);
				bas_take(t); // ')'
				return (s32)bas_rnd(hi);
			}
			return 0;
		}
		if (!strcmp(p->word, "ABS"))
		{
			const BasTok* p2 = bas_take(t);
			if (bas_op_is(p2, "("))
			{
				s32 v = bas_expr(t);
				bas_take(t); // ')'
				return v >= 0 ? v : -v;
			}
			return 0;
		}
		if (p->word[1] == 0) return bas.vars[p->word[0] - 'A'];
		bas_fail("Unbekannte Funktion");
	}
	if (p->kind == TOK_OP && p->op[0] == '-' && p->op[1] == 0)
		return -bas_atom(t);
	if (p->kind == TOK_OP && p->op[0] == '(' && p->op[1] == 0)
	{
		s32 v = bas_expr(t);
		bas_take(t); // ')'
		return v;
	}
	bas_fail("Syntaxfehler im Ausdruck");
	return 0;
}

static s32 bas_mul(BasToks* t)
{
	s32 l = bas_atom(t);
	for (;;)
	{
		const BasTok* p = bas_peek(t);
		if (p->kind == TOK_OP && (p->op[0] == '*' || p->op[0] == '/' || p->op[0] == '%'))
		{
			char cc = p->op[0];
			t->i++;
			s32 r = bas_atom(t);
			if (cc == '*') l = l * r;      // placeholder
			else if (r == 0) l = 0;        // Div 0 -> 0
			else if (cc == '/') l = l / r;
			else l = l % r;
		}
		else return l;
	}
}

static s32 bas_add(BasToks* t)
{
	s32 l = bas_mul(t);
	for (;;)
	{
		const BasTok* p = bas_peek(t);
		if (p->kind == TOK_OP && (p->op[0] == '+' || p->op[0] == '-') && p->op[1] == 0)
		{
			char cc = p->op[0];
			t->i++;
			s32 r = bas_mul(t);
			l = (cc == '+') ? l + r : l - r;
		}
		else return l;
	}
}

static s32 bas_cmp(BasToks* t)
{
	s32 l = bas_add(t);
	const BasTok* p = bas_peek(t);
	if (p->kind == TOK_OP && (p->op[0] == '=' || p->op[0] == '<' || p->op[0] == '>'))
	{
		char x = p->op[0];
		t->i++;
		s32 r = bas_add(t);
		if (p->op[1] == 0)
		{
			if (x == '=') return l == r ? 1 : 0;
			if (x == '<') return l < r ? 1 : 0;
			if (x == '>') return l > r ? 1 : 0;
		}
		else
		{
			if (p->op[0] == '<' && p->op[1] == '>') return l != r ? 1 : 0;
			if (p->op[0] == '<' && p->op[1] == '=') return l <= r ? 1 : 0;
			if (p->op[0] == '>' && p->op[1] == '=') return l >= r ? 1 : 0;
		}
	}
	return l;
}

static s32 bas_expr(BasToks* t) { return bas_cmp(t); }

// ---- Statements ----
static void bas_expect_num(BasToks* t, s32* out)
{
	const BasTok* p = bas_peek(t);
	if (p->kind != TOK_NUM) bas_fail("Zeilennummer erwartet");
	t->i++;
	*out = p->num;
}

static void bas_do_let(BasToks* t)
{
	const BasTok* p = bas_peek(t);
	if (p->kind != TOK_WORD || p->word[1] != 0) bas_fail("Variable A-Z erwartet");
	u8 var = p->word[0];
	t->i++;
	const BasTok* eq = bas_peek(t);
	if (eq->kind != TOK_OP || eq->op[0] != '=' || eq->op[1] != 0) bas_fail("= erwartet");
	t->i++;
	bas.vars[var - 'A'] = bas_expr(t);
}

static void bas_do_input(BasToks* t)
{
	char prompt[40] = "? ";
	int var = -1;
	if (t->i < t->n && t->t[t->i].kind == TOK_STR)
	{
		strcpy(prompt, t->t[t->i].str);
		strcat(prompt, " ");
		t->i++;
		if (t->i < t->n && t->t[t->i].kind == TOK_OP && t->t[t->i].op[0] == ';') t->i++;
	}
	const BasTok* p = bas_peek(t);
	if (p->kind != TOK_WORD || p->word[1] != 0) bas_fail("INPUT braucht Variable A-Z");
	var = p->word[0] - 'A';
	t->i++;

	char buf[24];
	for (;;)
	{
		buf[0] = 0;
		bas.readline_hook(buf, 60, prompt);
		// Zahl parsen (Whitespace-trim)
		const char* s = buf;
		while (*s == ' ') s++;
		char* end;
		long v = strtol(s, &end, 10);
		while (*end == ' ') end++;
		if (*end == 0 && end != s)
		{
			bas.vars[var] = (s32)v;
			return;
		}
		bas_outs("Bitte eine ganze Zahl!\n");
	}
}

// PRINT (wie do_print: ';' -> kein NL, ',' -> Tab, String/Ausdruck)
static void bas_do_print(BasToks* t)
{
	int nl = 1;
	for (;;)
	{
		const BasTok* p = bas_peek(t);
		if (p->kind == TOK_NONE || (p->kind == TOK_OP && p->op[0] == ':')) break;
		if (p->kind == TOK_OP && p->op[0] == ';') { t->i++; nl = 0; continue; }
		if (p->kind == TOK_OP && p->op[0] == ',')
		{
			t->i++;
			bas_out('\t'); nl = 1;
			continue;
		}
		// ein Element: bis zum ';'/'/' ,'/':'/Ende sammeln
		BasToks sub; sub.t = t->t; sub.i = t->i; sub.n = t->n;
		while (t->i < t->n)
		{
			const BasTok* q = bas_peek(t);
			if (q->kind == TOK_OP && (q->op[0] == ',' || q->op[0] == ';')) break;
			if (q->kind == TOK_OP && q->op[0] == ':' && q->op[1] == 0) break;
			t->i++;
		}
		sub.n = t->i;
		if (sub.i >= sub.n) continue;
		if (t->t[sub.i].kind == TOK_STR)
			bas_outs(t->t[sub.i].str);
		else
		{
			s32 v = bas_expr(&sub);
			char b[16];
			// BasItoa (negativ-faehig)
			int neg = v < 0; unsigned int uv = neg ? (unsigned int)(-v) : (unsigned int)v;
			int k = 0;
			if (uv == 0) b[k++] = '0';
			while (uv > 0) { b[k++] = (char)('0' + (uv % 10)); uv /= 10; }
			int w = 0;
			if (neg) bas_out('-');
			while (k > 0) bas_out(b[--k]);
		}
		nl = 1;
	}
	if (nl) bas_out('\n');
}

// die Statement-Ausfuehrung (der Python-exec_stmt)
static BasExecRes bas_exec_stmt(BasToks* t);

// IF/THEN (der Rest bis Zeilen-Ende kann ':'-Kette sein)
static BasExecRes bas_exec_chain(BasToks* t);

static void bas_split_rem(const char* s, char* out)
{
	// REM-Zeile: ganze Zeile entfernen (der Kommentar)
	out[0] = 0;
}

static BasExecRes bas_do_if(BasToks* t)
{
	s32 cond = bas_expr(t);
	const BasTok* th = bas_peek(t);
	if (th->kind == TOK_WORD && !strcmp(th->word, "THEN")) t->i++;
	BasExecRes r; r.tag = R_NONE;
	if (cond != 0)
	{
		const BasTok* p = bas_peek(t);
		if (t->i == t->n - 1 && p->kind == TOK_NUM)
		{
			// THEN <Zeilennummer> = implizites GOTO
			r.tag = R_GOTO; r.num = p->num;
			t->i++;
			return r;
		}
		return bas_exec_chain(t);   // der Rest als ':'-Kette
	}
	r.tag = R_SKIP;
	return r;
}

static BasExecRes bas_exec_stmt(BasToks* t)
{
	BasExecRes r; r.tag = R_NONE; r.num = 0; r.var = 0; r.limit = 0; r.step = 0;
	const BasTok* p = bas_peek(t);
	if (p->kind == TOK_NONE) return r;

	if (p->kind == TOK_OP && p->op[0] == '\'' && p->op[1] == 0)
	{
		t->i = t->n; // Kommentar
		return r;
	}
	if (p->kind == TOK_OP && p->op[0] == ':' && p->op[1] == 0)
		{ t->i++; return r; }  // leeres Statement-Element

	if (p->kind != TOK_WORD)
	{
		// implizites LET: X = ... (die Variable als Word? Nein: nur Word)
		bas_fail("Syntaxfehler");
	}
	const char* v = p->word;

	if (!strcmp(v, "PRINT") || !strcmp(v, "?"))
	{
		t->i++;
		bas_do_print(t);
		return r;
	}
	if (!strcmp(v, "INPUT"))
	{
		t->i++;
		bas_do_input(t);
		return r;
	}
	if (!strcmp(v, "LET"))
	{
		t->i++;
		bas_do_let(t);
		return r;
	}
	if (!strcmp(v, "GOTO"))
	{
		t->i++;
		s32 num;
		bas_expect_num(t, &num);
		r.tag = R_GOTO; r.num = num;
		return r;
	}
	if (!strcmp(v, "GOSUB"))
	{
		t->i++;
		s32 num;
		bas_expect_num(t, &num);
		r.tag = R_GOSUB; r.num = num;
		return r;
	}
	if (!strcmp(v, "RETURN"))
	{
		t->i++;
		r.tag = R_RETURN;
		return r;
	}
	if (!strcmp(v, "IF"))
	{
		t->i++;
		return bas_do_if(t);
	}
	if (!strcmp(v, "FOR"))
	{
		t->i++;
		// FOR var = start TO limit [STEP step]
		const BasTok* pv = bas_peek(t);
		if (pv->kind != TOK_WORD || pv->word[1] != 0) bas_fail("FOR braucht Variable A-Z");
		u8 var = pv->word[0];
		t->i++;
		const BasTok* eq = bas_peek(t);
		if (eq->kind != TOK_OP || eq->op[0] != '=' || eq->op[1] != 0) bas_fail("FOR braucht =");
		t->i++;
		s32 start = bas_expr(t);
		const BasTok* to = bas_peek(t);
		if (to->kind != TOK_WORD || strcmp(to->word, "TO") != 0) bas_fail("FOR braucht TO");
		t->i++;
		s32 limit = bas_expr(t);
		s32 step = 1;
		if (t->i < t->n)
		{
			const BasTok* st = bas_peek(t);
			if (st->kind == TOK_WORD && !strcmp(st->word, "STEP"))
			{
				t->i++;
				step = bas_expr(t);
			}
		}
		bas.vars[var - 'A'] = start;
		r.tag = R_FOR;
		r.var = var;
		r.limit = limit;
		r.step = step;
		return r;
	}
	if (!strcmp(v, "NEXT"))
	{
		t->i++;
		const BasTok* pv = bas_peek(t);
		if (pv->kind == TOK_WORD)
		{
			r.tag = R_NEXT;
			r.var = pv->word[0];
			t->i++;
		}
		else
		{
			r.tag = R_NEXT;
			r.var = 0;
		}
		return r;
	}
	if (!strcmp(v, "END") || !strcmp(v, "STOP"))
	{
		t->i = t->n;
		r.tag = R_END;
		return r;
	}
	if (!strcmp(v, "REM"))
	{
		t->i = t->n;
		return r;
	}
	if (!strcmp(v, "CLS"))
	{
		t->i++;
		bas_outs("\033[2J\033[H");
		return r;
	}
	if (!strcmp(v, "SAVE"))
	{
		t->i++;
		const BasTok* ps = bas_peek(t);
		if (ps->kind != TOK_STR) bas_fail("SAVE braucht \"NAME\"");
		const char* name = ps->str;
		t->i++;
		// der Quelltext je je je je je je je je je je je je je je je
		char* src = bas.textbuf;
		int pos = 0;
		for (int i = 0; i < bas.nprog; i++)
		{
			int nl = snprintf(&src[pos], BAS_TEXTMAX - pos, "%d %s\n",
				(int)bas.prog[i].num, bas.prog[i].text);
			if (nl < 0 || pos + nl >= BAS_TEXTMAX) { bas_fail("Programm zu gross"); }
			pos += nl;
		}
		if (bas.save_hook == 0) bas_fail("Kein Filesystem");
		int rc = bas.save_hook(name, src);
		if (rc != 0) bas_fail("SAVE fehlgeschlagen");
		bas_outs("OK\n");
		return r;
	}
	if (!strcmp(v, "LOAD"))
	{
		t->i++;
		const BasTok* ps = bas_peek(t);
		if (ps->kind != TOK_STR) bas_fail("LOAD braucht \"NAME\"");
		const char* name = ps->str;
		t->i++;
		if (bas.load_hook == 0) bas_fail("Kein Filesystem");
		char dst[BAS_TEXTMAX];
		int rc = bas.load_hook(name, dst, BAS_TEXTMAX);
		if (rc != 0) bas_fail("Datei nicht gefunden");
		// das Programm je je je je je je je je je je je je je je je:
		bas.nprog = 0;
		char* line = dst;
		while (*line)
		{
			char* nl = strchr(line, '\n');
			if (nl) *nl = 0;
			char* sp = strchr(line, ' ');
			if (sp)
			{
				int num = atoi(line);
				const char* rest = sp + 1;
				if (num > 0 && bas.nprog < BAS_MAXLINES)
				{
					bas.prog[bas.nprog].num = num;
					strncpy(bas.prog[bas.nprog].text, rest, BAS_LINEMAX - 1);
					bas.prog[bas.nprog].text[BAS_LINEMAX - 1] = 0;
					bas.nprog++;
				}
			}
			if (!nl) break;
			line = nl + 1;
		}
		bas_outs("OK\n");
		return r;
	}
	if (v[1] == 0)
	{
		bas_do_let(t); // implizites LET
		return r;
	}
	bas_fail("Unbekannter Befehl");
	return r;
}

// die ':'-Kette bis Zeilen-Ende ausfuehren (der Python-exec_chain)
static BasExecRes bas_exec_chain(BasToks* t)
{
	for (;;)
	{
		const BasTok* p = bas_peek(t);
		if (p->kind == TOK_NONE) { BasExecRes r; r.tag = R_NONE; return r; }
		BasExecRes r = bas_exec_stmt(t);
		if (r.tag != R_NONE) return r;
	}
}

// der implizite LET ohne word-Anfang? (der Python: k=='word', len==1)
// -> exec_stmt deckt das ab (v[1]==0 Fall)

// ---- RUN-Programm (der Python-run_program 1:1) ----
static void bas_out_i(s32 v, int neg)
{
	char tmp[16]; int k = 0;
	unsigned int uv = v < 0 ? (unsigned int)(-(v)) : (unsigned int)v;
	if (uv == 0) tmp[k++] = '0';
	while (uv > 0) { tmp[k++] = (char)('0' + (uv % 10)); uv /= 10; }
	if (v < 0) bas_out('-');
	while (k > 0) bas_out(tmp[--k]);
}

static int bas_find_line(s32 num)
{
	for (int i = 0; i < bas.nprog; i++)
		if (bas.prog[i].num == num) return i;
	return -1;
}

static void bas_run_program(void)
{
	bas.ngosub = 0;
	bas.nfor = 0;
	int i;
	for (i = 0; i < 26; i++) bas.vars[i] = 0;
	if (bas.nprog == 0)
	{
		bas_outs("Kein Programm. Zeilen eingeben oder LOAD.\n");
		return;
	}
	int idx = 0, ti = 0;
	while (idx >= 0 && idx < bas.nprog)
	{
		bas.errline = bas.prog[idx].num;
		bas_tokenize(bas.prog[idx].text);
		BasToks t; t.t = bas.toks; t.n = bas.ntok; t.i = ti;
		int jumped = 0;
		while (t.i < t.n)
		{
			BasExecRes r = bas_exec_chain(&t);
			if (r.tag == R_NONE) break;
			if (r.tag == R_SKIP) break;
			if (r.tag == R_END) return;
			if (r.tag == R_GOTO || r.tag == R_GOSUB)
			{
				int li = bas_find_line(r.num);
				if (li < 0)
				{
					bas_outs(r.tag == R_GOTO ? "GOTO: Zeile " : "GOSUB: Zeile ");
					// Zeilennummer-Ausgabe
					{
						char tb[16]; int k = 0; s32 v = r.num;
						if (v == 0) tb[k++] = '0';
						while (v > 0) { tb[k++] = (char)('0' + (v % 10)); v /= 10; }
						while (k > 0) bas_out(tb[--k]);
					}
					bas_outs(" fehlt\n");
					return;
				}
				if (r.tag == R_GOSUB)
				{
					if (bas.ngosub >= BAS_MAXGOSUB) { bas_outs("GOSUB-Stack voll\n"); return; }
					bas.gosub_idx[bas.ngosub] = idx;
					bas.gosub_ti[bas.ngosub] = t.i;
					bas.ngosub++;
				}
				idx = li;
				ti = 0;
				jumped = 1;
				break;
			}
			if (r.tag == R_RETURN)
			{
				if (bas.ngosub > 0)
				{
					bas.ngosub--;
					idx = bas.gosub_idx[bas.ngosub];
					ti = bas.gosub_ti[bas.ngosub];
					jumped = 1;
				}
				else { bas_outs("RETURN ohne GOSUB\n"); return; }
				break;
			}
			if (r.tag == R_FOR)
			{
				if (bas.nfor >= BAS_MAXFOR) { bas_outs("FOR-Stack voll\n"); return; }
				bas.forst[bas.nfor].var = r.var;
				bas.forst[bas.nfor].limit = r.limit;
				bas.forst[bas.nfor].step = r.step;
				bas.forst[bas.nfor].idx = idx;
				bas.forst[bas.nfor].ti = t.i;
				bas.nfor++;
				continue;   // der Cursor steht nach dem FOR
			}
			if (r.tag == R_NEXT)
			{
				// handle_next
				u8 want = r.var;
				int found = -1;
				for (int fi = bas.nfor - 1; fi >= 0; fi--)
					if (want == 0 || bas.forst[fi].var == want) { found = fi; break; }
				if (found < 0) { bas_outs("NEXT ohne FOR\n"); return; }
				BasForEntry* e = &bas.forst[found];
				bas.vars[e->var - 'A'] += e->step;
				s32 ak = bas.vars[e->var - 'A'];
				int again = (e->step > 0 && ak <= e->limit) || (e->step < 0 && ak >= e->limit);
				if (again)
				{
					idx = e->idx;
					ti = e->ti;
					bas.nfor = found + 1;
					jumped = 1;
					break;
				}
				bas.nfor = found;
				continue;
			}
		}
		if (!jumped) { idx++; ti = 0; }
	}
}

// ---- REPL (der Python-repl, pro Zeile) ----
static void bas_set_err(const char* m) { strcpy(bas.msg, m); }

static int bas_repl_line(const char* line)
{
	// BYE/NEW/LIST/RUN/SAVE/LOAD/Zeilennummer/Direktbefehl
	char up[128]; int k = 0;
	while (line[k] && k < 127) { char c = line[k]; up[k] = (c >= 'a' && c <= 'z') ? (char)(c - 32) : c; k++; }
	up[k] = 0;

	if (!strcmp(up, "BYE") || !strcmp(up, "EXIT") || !strcmp(up, "BYE\n") || !strcmp(up, "EXIT\n"))
	{
		bas_outs("Tschuess!\n");
		return 1;
	}
	if (!strcmp(up, "NEW"))
	{
		bas.nprog = 0;
		bas_outs("OK\n");
		return 0;
	}
	if (!strcmp(up, "LIST"))
	{
		if (bas.nprog == 0) bas_outs("(leer)\n");
		for (int i = 0; i < bas.nprog; i++)
		{
			// Format: <num> <text>
			{
				char tb[16]; int kk = 0; s32 v = bas.prog[i].num;
				if (v == 0) tb[kk++] = '0';
				while (v > 0) { tb[kk++] = (char)('0' + (v % 10)); v /= 10; }
				while (kk > 0) bas_out(tb[--kk]);
			}
			bas_out(' ');
			bas_outs(bas.prog[i].text);
			bas_out('\n');
		}
		return 0;
	}
	if (!strcmp(up, "RUN"))
	{
		bas_run_program();
		return 0;
	}
	// Zeilennummer?
	{
		const char* p = line;
		while (*p == ' ') p++;
		const char* s = p;
		if (*s >= '0' && *s <= '9')
		{
			s32 num = 0;
			while (*s >= '0' && *s <= '9') { num = num * 10 + (*s - '0'); s++; }
			const char* rest = s;
			while (*rest == ' ') rest++;
			// Insert/Replace/Delete
			int li = bas_find_line(num);
			if (*rest == 0)
			{
				if (li >= 0)
				{
					for (int i = li; i < bas.nprog - 1; i++) bas.prog[i] = bas.prog[i + 1];
					bas.nprog--;
				}
				return 0;
			}
			if (li >= 0) { strcpy(bas.prog[li].text, rest); return 0; }
			if (bas.nprog >= BAS_MAXLINES) { bas_outs("Programm voll\n"); return 0; }
			// insert-sorted
			int pos = 0;
			while (pos < bas.nprog && bas.prog[pos].num < num) pos++;
			for (int i = bas.nprog; i > pos; i--) bas.prog[i] = bas.prog[i - 1];
			bas.prog[pos].num = num;
			strcpy(bas.prog[pos].text, rest);
			bas.nprog++;
			return 0;
		}
	}
	// Direktbefehl (Immediate)
	bas_tokenize(line);
	BasToks t; t.t = bas.toks; t.n = bas.ntok; t.i = 0;
	BasExecRes r = bas_exec_stmt(&t);
	if (r.tag == R_GOTO || r.tag == R_GOSUB || r.tag == R_FOR)
	{
		bas_outs("Dieser Befehl funktioniert nur im Programm (RUN)\n");
		return 0;
	}
	if (t.i < t.n)
	{
		// ':'-Kette ausfuehren (der Python-exec_immediate-Loop)
		for (;;)
		{
			const BasTok* p = bas_peek(&t);
			if (p->kind == TOK_NONE) break;
			BasExecRes r2 = bas_exec_stmt(&t);
			if (r2.tag == R_GOTO || r2.tag == R_GOSUB || r2.tag == R_FOR)
			{
				bas_outs("Dieser Befehl funktioniert nur im Programm (RUN)\n");
				break;
			}
			if (r2.tag == R_NONE)
				continue;
			bas_outs("Dieser Befehl funktioniert nur im Programm (RUN)\n");
			break;
		}
	}
	return 0;
}

// ---- Fehler-Wrapper (der Python-repl-try/except) ----
static int bas_exec_line(const char* line)
{
	if (setjmp(bas.jb))
	{
		bas_outs("Fehler: ");
		bas_outs(bas.msg);
		bas_out('\n');
		bas.errline = -1;
		return 0;
	}
	return bas_repl_line(line);
}

#endif // BASIC_H
# tinybasic.py - Tiny BASIC fuer Raspberry Pi Pico 2 (CircuitPython)
# Neotron-Pico-Projekt, Makerspace - Schritt 1: Interpreter ueber USB-Konsole
# Installation: Diese Datei als "code.py" ins Hauptverzeichnis von CIRCUITPY kopieren.
# Danach Serial-Konsole oeffnen (z.B. Thonny) - dort läuft der BASIC-Editor.
#
# Unterstuetzt: PRINT, INPUT, LET (auch implizit), IF/THEN, GOTO, GOSUB/RETURN,
#               FOR/TO/STEP/NEXT, END, REM, CLS, RND(), ABS()
# Befehle:      NEW, LIST, RUN, SAVE "name", LOAD "name", BYE
# Getestet auf dem Pi500 (Desktop-Python); laeuft 1:1 unter CircuitPython.

import sys
import random


class BasicError(Exception):
    pass


VARS = {}
PROG = {}            # Zeilennummer -> Quelltext
GOSUB_STACK = []
FOR_STACK = []


def out(s):
    sys.stdout.write(s)
    try:
        sys.stdout.flush()
    except AttributeError:
        pass  # CircuitPython: kein flush noetig, schreibt direkt durch


# ---------------- Tokenizer ----------------
def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == ' ' or c == '\t':
            i += 1
        elif c.isdigit():
            j = i
            while j < n and s[j].isdigit():
                j += 1
            toks.append(('num', int(s[i:j])))
            i = j
        elif c.isalpha():
            j = i
            while j < n and (s[j].isalpha() or s[j].isdigit()):
                j += 1
            toks.append(('word', s[i:j].upper()))
            i = j
        elif c == '"':
            j = i + 1
            buf = ''
            while j < n and s[j] != '"':
                buf += s[j]
                j += 1
            toks.append(('str', buf))
            i = j + 1
        elif s[i:i + 2] == '<>' or s[i:i + 2] == '<=' or s[i:i + 2] == '>=':
            toks.append(('op', s[i:i + 2]))
            i += 2
        else:
            toks.append(('op', c))
            i += 1
    return toks


def split_statements(toks):
    # REM-Kommentar: ganze Zeile ignorieren
    if toks and toks[0] == ('word', 'REM'):
        return []
    stmts = [[]]
    for tk in toks:
        if tk == ('op', ':'):
            stmts.append([])
        else:
            stmts[-1].append(tk)
    return stmts


# ---------------- Ausdruecke (rekursiv) ----------------
class Toks:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        if self.i < len(self.t):
            return self.t[self.i]
        return (None, None)

    def take(self):
        t = self.peek()
        self.i += 1
        return t


def expr(t):
    return cmp_expr(t)


def cmp_expr(t):
    left = add_expr(t)
    k, v = t.peek()
    if k == 'op' and v in ('=', '<>', '<', '>', '<=', '>='):
        t.take()
        right = add_expr(t)
        if v == '=':
            return 1 if left == right else 0
        if v == '<>':
            return 1 if left != right else 0
        if v == '<':
            return 1 if left < right else 0
        if v == '>':
            return 1 if left > right else 0
        if v == '<=':
            return 1 if left <= right else 0
        return 1 if left >= right else 0
    return left


def add_expr(t):
    left = mul_expr(t)
    while True:
        k, v = t.peek()
        if k == 'op' and v in ('+', '-'):
            t.take()
            right = mul_expr(t)
            left = left + right if v == '+' else left - right
        else:
            return left


def mul_expr(t):
    left = atom(t)
    while True:
        k, v = t.peek()
        if k == 'op' and v in ('*', '/', '%'):
            t.take()
            right = atom(t)
            if v == '*':
                left = left * right
            elif right == 0:
                left = 0  # Division durch 0 -> 0 statt Absturz
            elif v == '/':
                left = left // right
            else:
                left = left % right
        else:
            return left


def atom(t):
    k, v = t.take()
    if k == 'num':
        return v
    if k == 'word':
        if v == 'RND':
            k2, v2 = t.take()
            if k2 == 'op' and v2 == '(':
                hi = expr(t)
                t.take()  # ')'
                return random.getrandbits(20) % hi if hi > 0 else 0
            return 0
        if v == 'ABS':
            k2, v2 = t.take()
            if k2 == 'op' and v2 == '(':
                val = expr(t)
                t.take()  # ')'
                return val if val >= 0 else -val
            return 0
        if len(v) == 1:
            return VARS.get(v, 0)
        raise BasicError('Unbekannte Funktion: ' + v)
    if k == 'op' and v == '-':
        return -atom(t)
    if k == 'op' and v == '(':
        val = expr(t)
        t.take()  # ')'
        return val
    raise BasicError('Syntaxfehler im Ausdruck')


# ---------------- Statements ----------------
def expect_number(toks):
    if len(toks) == 1 and toks[0][0] == 'num':
        return toks[0][1]
    raise BasicError('Zeilennummer erwartet')


def do_let(toks):
    if not toks or toks[0][0] != 'word' or len(toks[0][1]) != 1:
        raise BasicError('Variable A-Z erwartet')
    var = toks[0][1]
    if len(toks) < 3 or toks[1] != ('op', '='):
        raise BasicError('= erwartet')
    VARS[var] = expr(Toks(toks[2:]))


def do_input(toks):
    prompt = '? '
    idx0 = 0
    if toks and toks[0][0] == 'str':
        prompt = toks[0][1] + ' '
        idx0 = 1
        if len(toks) > idx0 and toks[idx0] == ('op', ';'):
            idx0 += 1
    if len(toks) <= idx0 or toks[idx0][0] != 'word' or len(toks[idx0][1]) != 1:
        raise BasicError('INPUT braucht Variable A-Z')
    var = toks[idx0][1]
    while True:
        line = input(prompt)
        try:
            VARS[var] = int(line.strip())
            return
        except ValueError:
            out('Bitte eine ganze Zahl!\n')


def do_print(toks):
    nl = True
    while True:
        k, v = (toks[0], toks[1]) if False else (None, None)
        break
    t = Toks(toks)
    while True:
        k, v = t.peek()
        if k is None:
            break
        if k == 'op' and v == ';':
            t.take()
            nl = False
            continue
        if k == 'op' and v == ',':
            t.take()
            out('\t')
            nl = True
            continue
        sub = []
        while True:
            k2, v2 = t.peek()
            if k2 is None or (k2 == 'op' and v2 in (',', ';')):
                break
            sub.append(t.take())
        if not sub:
            continue
        if sub[0][0] == 'str':
            out(sub[0][1])
        else:
            out(str(expr(Toks(sub))))
        nl = True
    if nl:
        out('\n')


def do_if(toks):
    t = Toks(toks)
    cond = expr(t)
    rest = t.t[t.i:]
    if rest and rest[0] == ('word', 'THEN'):
        rest = rest[1:]
    if cond != 0:
        # THEN <Zeilennummer> = implizites GOTO
        if len(rest) == 1 and rest[0][0] == 'num':
            return ('goto', rest[0][1])
        return exec_chain(split_statements(rest))
    return ('skip',)


def do_for(toks):
    if len(toks) < 4 or toks[0][0] != 'word' or len(toks[0][1]) != 1:
        raise BasicError('FOR braucht Variable A-Z')
    var = toks[0][1]
    if toks[1] != ('op', '='):
        raise BasicError('FOR braucht =')
    t = Toks(toks[2:])
    start = expr(t)
    rem = t.t[t.i:]
    if not rem or rem[0] != ('word', 'TO'):
        raise BasicError('FOR braucht TO')
    t2 = Toks(rem[1:])
    limit = expr(t2)
    rem2 = t2.t[t2.i:]
    step = 1
    if rem2 and rem2[0] == ('word', 'STEP'):
        step = expr(Toks(rem2[1:]))
    VARS[var] = start
    return ('for', var, limit, step)


def next_var(toks):
    if toks and toks[0][0] == 'word':
        return toks[0][1][:1]
    return None


def handle_next(var, cur_idx, cur_si):
    if not FOR_STACK:
        raise BasicError('NEXT ohne FOR')
    found = -1
    for i in range(len(FOR_STACK) - 1, -1, -1):
        if var is None or FOR_STACK[i][0] == var:
            found = i
            break
    if found < 0:
        raise BasicError('NEXT ohne passendes FOR')
    entry = FOR_STACK[found]
    v = entry[0]
    VARS[v] = VARS.get(v, 0) + entry[2]
    akt = VARS[v]
    if (entry[2] > 0 and akt <= entry[1]) or (entry[2] < 0 and akt >= entry[1]):
        del FOR_STACK[found + 1:]
        return (entry[3], entry[4])
    del FOR_STACK[found:]
    return None


def exec_chain(stmts):
    for st in stmts:
        r = exec_stmt(st)
        if r is not None:
            return r
    return None


def exec_stmt(toks):
    if not toks:
        return None
    k, v = toks[0]
    if k == 'word':
        if v == 'PRINT' or v == '?':
            do_print(toks[1:])
            return None
        if v == 'INPUT':
            do_input(toks[1:])
            return None
        if v == 'LET':
            do_let(toks[1:])
            return None
        if v == 'GOTO':
            return ('goto', expect_number(toks[1:]))
        if v == 'GOSUB':
            return ('gosub', expect_number(toks[1:]))
        if v == 'RETURN':
            return ('return',)
        if v == 'IF':
            return do_if(toks[1:])
        if v == 'FOR':
            return do_for(toks[1:])
        if v == 'NEXT':
            return ('next', next_var(toks[1:]))
        if v == 'END' or v == 'STOP':
            return ('end',)
        if v == 'CLS':
            out('\x1b[2J\x1b[H')
            return None
        if v == 'REM':
            return None
        if len(v) == 1:
            do_let(toks)  # implizites LET: X = 5
            return None
        raise BasicError('Unbekannter Befehl: ' + v)
    if k == 'op' and v == "'":
        return None  # Kommentar
    raise BasicError('Syntaxfehler')


def exec_immediate(toks):
    for st in split_statements(toks):
        r = exec_stmt(st)
        if r is None or r[0] == 'skip':
            continue
        raise BasicError('Dieser Befehl funktioniert nur im Programm (RUN)')


def run_program():
    VARS.clear()
    del GOSUB_STACK[:]
    del FOR_STACK[:]
    lines = sorted(PROG.keys())
    if not lines:
        out('Kein Programm. Zeilen eingeben oder LOAD.\n')
        return
    lidx = {}
    for i in range(len(lines)):
        lidx[lines[i]] = i
    idx = 0
    si = 0
    while 0 <= idx < len(lines):
        try:
            stmts = split_statements(tokenize(PROG[lines[idx]]))
        except Exception as e:
            out('Fehler Zeile %d: %s\n' % (lines[idx], e))
            return
        jumped = False
        while si < len(stmts):
            try:
                r = exec_stmt(stmts[si])
            except BasicError as e:
                out('Fehler Zeile %d: %s\n' % (lines[idx], e.args[0] if e.args else e))
                return
            except KeyboardInterrupt:
                out('\nBREAK in Zeile %d\n' % lines[idx])
                return
            except Exception as e:
                out('Fehler Zeile %d: %s\n' % (lines[idx], e))
                return
            if r is None:
                si += 1
                continue
            tag = r[0]
            if tag == 'skip':
                break
            if tag == 'end':
                return
            if tag == 'goto' or tag == 'gosub':
                if r[1] in lidx:
                    if tag == 'gosub':
                        GOSUB_STACK.append((idx, si + 1))
                    idx = lidx[r[1]]
                    si = 0
                    jumped = True
                else:
                    out('%s: Zeile %d fehlt\n' % (tag.upper(), r[1]))
                    return
                break
            if tag == 'return':
                if GOSUB_STACK:
                    idx, si = GOSUB_STACK.pop()
                    jumped = True
                else:
                    out('RETURN ohne GOSUB\n')
                    return
                break
            if tag == 'for':
                FOR_STACK.append([r[1], r[2], r[3], idx, si + 1])
                si += 1
                continue
            if tag == 'next':
                try:
                    res = handle_next(r[1], idx, si)
                except BasicError as e:
                    out('Fehler Zeile %d: %s\n' % (lines[idx], e.args[0] if e.args else e))
                    return
                if res is None:
                    si += 1
                    continue
                idx, si = res
                jumped = True
                break
            si += 1
        if not jumped:
            idx += 1
            si = 0


# ---------------- Dateien (CIRCUITPY-Flash / SD spaeter) ----------------
def do_save(name):
    path = name if name.startswith('/') else '/' + name
    with open(path, 'w') as f:
        for ln in sorted(PROG.keys()):
            f.write('%d %s\n' % (ln, PROG[ln]))


def do_load(name):
    path = name if name.startswith('/') else '/' + name
    PROG.clear()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            sp = line.find(' ')
            if sp < 0:
                continue
            try:
                PROG[int(line[:sp])] = line[sp + 1:]
            except ValueError:
                pass


# ---------------- Haupt-REPL ----------------
def repl():
    out('\x1b[2J\x1b[H')
    out('*** TINY BASIC v1.0 ***\n')
    out('Pico 2 / CircuitPython - Makerspace\n\n')
    out('Befehle: NEW LIST RUN SAVE LOAD BYE\n')
    out('Beispiel: 10 PRINT "HALLO"  dann RUN\n\n')
    while True:
        try:
            line = input('] ')
        except EOFError:
            return
        except KeyboardInterrupt:
            out('\n')
            continue
        line = line.strip()
        if not line:
            continue
        up = line.upper()
        try:
            if up == 'BYE' or up == 'EXIT':
                out('Tschuess!\n')
                return
            if up == 'NEW':
                PROG.clear()
                out('OK\n')
                continue
            if up == 'LIST':
                if not PROG:
                    out('(leer)\n')
                for ln in sorted(PROG.keys()):
                    out('%d %s\n' % (ln, PROG[ln]))
                continue
            if up == 'RUN':
                run_program()
                continue
            if up.startswith('SAVE') or up.startswith('LOAD'):
                parts = up.split(' ', 1)
                if len(parts) < 2:
                    out('Usage: %s "NAME.BAS"\n' % parts[0])
                    continue
                name = parts[1].strip().strip('"')
                try:
                    if parts[0] == 'SAVE':
                        do_save(name)
                    else:
                        do_load(name)
                    out('OK\n')
                except OSError as e:
                    out('Fehler: %s\n' % e)
                continue
            # Zeilennummer?
            p = line.split(None, 1)
            if p[0].isdigit():
                num = int(p[0])
                rest = p[1].strip() if len(p) > 1 else ''
                if rest:
                    PROG[num] = rest
                elif num in PROG:
                    del PROG[num]
                continue
            # Direktbefehl (ohne Zeilennummer)
            exec_immediate(tokenize(line))
        except BasicError as e:
            out('Fehler: %s\n' % (e.args[0] if e.args else e))
        except Exception as e:
            out('Fehler: %s\n' % e)


# repl() wird vom Hauptprogramm (vga_basic_console) aufgerufen -
# nicht mehr automatisch beim Import (sonst blockiert input() im Import,
# bevor der input-Shim gesetzt ist).
if __name__ == "__main__":
    repl()
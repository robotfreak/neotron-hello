# Testharness fuer tinybasic.py - fuehrt Testprogramme aus und prueft Ausgabe
# Run: python3 test_tinybasic.py
import subprocess
import sys

TESTS = [
    # (Name, Eingabe, erwartete Ausgabe-Teile)
    (
        "PRINT Hello",
        'PRINT "HALLO WELT"\n',
        ["HALLO WELT"],
    ),
    (
        "FOR/NEXT Zaehlschleife",
        '10 FOR I = 1 TO 3\n20 PRINT I\n30 NEXT I\nRUN\n',
        ["1", "2", "3"],
    ),
    (
        "LET + Rechnen",
        'LET A = 6\nLET B = 7\nPRINT A*B\n',
        ["42"],
    ),
    (
        "Implizites LET",
        'X = 20\nPRINT X+22\n',
        ["42"],
    ),
    (
        "IF/THEN/GOTO",
        '10 A = 5\n20 IF A > 3 THEN 40\n30 PRINT "FALSCH"\n40 PRINT "RICHTIG"\nRUN\n',
        ["RICHTIG"],
    ),
    (
        "GOSUB/RETURN",
        '10 GOSUB 100\n20 PRINT "ZURUECK"\n30 END\n100 PRINT "SUB"\n110 RETURN\nRUN\n',
        ["SUB", "ZURUECK"],
    ),
    (
        "Vergleichsoperatoren",
        'IF 1 < 2 THEN PRINT "JA"\nIF 2 <> 2 THEN PRINT "NEIN"\nPRINT 3>=3\nRUN\n'.replace('RUN\n', '') + 'RUN\n',
        ["JA", "1"],
    ),
    (
        "RND Bereich",
        'A = RND(10)\nIF A >= 0 THEN IF A < 10 THEN PRINT "OK"\nRUN\n',
        ["OK"],
    ),
    (
        "Programm editieren",
        '10 PRINT "ALT"\n10 PRINT "NEU"\nLIST\nRUN\n',
        ["10 PRINT \"NEU\"", "NEU"],
    ),
    (
        "Zeile loeschen",
        '10 PRINT "A"\n20 PRINT "B"\n10\nLIST\nRUN\n',
        ["20 PRINT \"B\"", "B"],
    ),
    (
        "CLS (unsichtbar aber kein Fehler)",
        'CLS\nPRINT "NACH CLS"\n',
        ["NACH CLS"],
    ),
    (
        "FOR mit STEP -1",
        'FOR I = 3 TO 1 STEP -1\nPRINT I\nNEXT I\nRUN\n',
        ["3", "2", "1"],
    ),
    (
        "ABS Funktion",
        'PRINT ABS(0-42)\n',
        ["42"],
    ),
    (
        "Unbekannter Befehl -> Fehlermeldung",
        'FLOETE 42\n',
        ["Fehler"],
    ),
    (
        "PRINT ohne Anfuehrungszeichen (Zahl)",
        'PRINT 7*6\n',
        ["42"],
    ),
    (
        "Mehrere Statements mit :",
        'A = 1 : PRINT A : A = 2 : PRINT A\n',
        ["1", "2"],
    ),
    (
        "BREAK/END im Programm",
        '10 PRINT "VORHER"\n20 END\n30 PRINT "NIE"\nRUN\n',
        ["VORHER"],
    ),
]

passed = 0
failed = 0
for name, stdin_data, expected_parts in TESTS:
    try:
        result = subprocess.run(
            [sys.executable, "tinybasic.py"],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=15,
        )
        outp = result.stdout
        ok = all(part in outp for part in expected_parts)
        if ok:
            passed += 1
            print("PASS: %s" % name)
        else:
            failed += 1
            print("FAIL: %s" % name)
            print("  Erwartet: %r" % expected_parts)
            print("  Ausgabe:  %r" % outp[:300])
            if result.stderr:
                print("  STDERR: %r" % result.stderr[:300])
    except subprocess.TimeoutExpired:
        failed += 1
        print("TIMEOUT: %s" % name)

print("\n%d PASS / %d FAIL / %d gesamt" % (passed, failed, len(TESTS)))
sys.exit(1 if failed else 0)
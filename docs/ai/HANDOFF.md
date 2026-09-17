Open tasks:

1. [ ] Issue #1 „CLI gaps + undocumented API findings (session
   2026-09-17)“ abarbeiten: generische `rpc`/`rest`-Passthrough-Commands,
   `lesson info`, `session status`, `kv --student`; Doku-Nachzug
   (Login-Verifikation 302≠Erfolg, token/new-Toten-Signatur,
   Parallel-Login-Beobachtung, app/data). →
   https://github.com/georgernstgraf/webuntis-agent/issues/1

Recently closed (2026-09-16):

1. [x] 16.9.-Zettel "3CAIF NICHT auf Liste" VOLLSTÄNDIG: Kollege hatte
   Reaktivierungen in 218881 (3 Schüler, je 15/17) + 218839/215940
   (3 Schüler, je 17/18) schon eingetragen (nicht aufgefüllt); 2 davon
   nach Re-Import in 3CAIF verifiziert. 3 Writes (result=null, Re-Read
   ok): 218881 +8 (attending 35), 218839 +7 (attending 29), 215943 +3
   (attending 28). Alle 21 Reaktivierungs-IDs heuer im System.
   [Namen/IDs: LOCAL.md]
2. [x] 3CAIF-POS1 (215943) nachgezogen: +8 Schüler, je 18 Termine
   (result=null, Re-Read: attending 36). User unterrichtet 3CAIF
   auch in POS1 — beide 3CAIF-Lektionen damit vollständig.
   [Namen: LOCAL.md]
3. [x] 3BAIF-Zettel (17 Namen) abgeglichen, dann je 1 Write in POS1
   (215940) + WMC_1 (218839): 4 Schüler mit 18/18 Terminen (Re-Read ok;
   POS1 attending 20, WMC_1 attending 19; einer davon eigentlich 5AAIF —
   Detail: LOCAL.md; 2 falsch Eingetragene bleiben draußen, der korrekt
   Zugeordnete unverändert). Nur SJ 2025/26: 11 Schüler. KV 3BAIF:
   [Name: LOCAL.md].
4. [x] 3CAIF-Zettel abgeglichen: 7 von 9 Namen nur noch SJ 2025/26;
   eine Schreibkorrektur eines Zettel-Namens verifiziert.
   Aktuelle 3CAIF = 23 andere Schüler. [Namen/IDs: LOCAL.md]
5. [x] 2 Schüler in WMC_1 (lsId 218881, 3CAIF) aufgenommen: ein Write
   (`students edit --add-student-id <id1> --add-student-id <id2>
   --no-dry-run`, result=null), Re-Read: beide 17/17 Termine,
   22 Klassen-Schüler unverändert (attending 24). [Namen/IDs: LOCAL.md]
6. [x] Such-Fallback gebaut: `search --fallback/--all-years`,
   `students find` (Auto-Fallback, NICHT AKTUELL-Flag), Wrapper `./wu`.

Recently closed (2026-09-14):

1. [x] Schüler-Verwechslung korrigiert: POS1 (lsId 215940) hatte
   fälschlich den falschen von zwei Brüdern (5BAIF) — User bestätigte
   die richtige Zuordnung: POS1 (POS-Theorie), NICHT WMC. Korrektur per
   `students edit --lsid 215940 --class-id 4107 --add-student-id <id>
   --remove-student-id <id> --no-dry-run`. Verifiziert per
   Matrix-Re-Read: falscher Bruder 0 Termine, richtiger alle 18
   (2026-09-11 .. 2027-01-29), 17 Klassen-Schüler (klasse 4107)
   unverändert. [Namen/IDs: LOCAL.md]
2. [x] WMC_1-Aufnahme (lsId 218839) gestrichen: der Schüler gehört
   laut User ausdrücklich nicht in WMC. WMC_1 wurde nie beschrieben.
3. [x] Write-Pfad `submitStudentLessonPeriodData` validiert: erster
   echter Write lief erfolgreich (result=null), nachfolgender Re-Read
   bestätigt.
4. [x] Zwei Schüler (beide Klasse 4107) fälschlich mit allen 18
   Terminen in POS1 UND WMC_1 — aus beiden Lektionen entfernt (zwei
   Writes, je zwei `--remove-student-id`). Verifiziert: beide 0
   Termine, POS1 attending 16 (15 Klasse + 1 extern), WMC_1 attending
   15 (nur Klasse). [Namen/IDs: LOCAL.md]

Last updated: 2026-09-17

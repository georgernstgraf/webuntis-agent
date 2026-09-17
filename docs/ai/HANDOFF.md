Open tasks:

1. [ ] Issue #1 „CLI gaps + undocumented API findings (session
   2026-09-17)": VOLLSTÄNDIG implementiert und live-verifiziert
   (rpc/rest, lesson info, session status, kv --student, Doku-Nachzug,
   wu-Wrapper-Fix); commit ausstehen bzw. bereits committed — Issue
   schließen im `finish`-Modus, wenn der User bestätigt. →
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

Last updated: 2026-09-17

Open tasks:

1. [ ] Student-Verwechslung klären: In POS1 (lsId 215940) wurde händisch
   "Al Badawi Mahmoud" (id=19261, 5BAIF) aufgenommen — angefragt war aber
   "Badawi Mhd Nour" (id=19405, 5BAIF). User muss im Browser prüfen, wer
   der richtige Schüler ist. Korrektur wäre per `students add --lsid
   215940 --class-id 4107 --student-id 19405 --no-dry-run` möglich
   (Write braucht explizite Freigabe); ggf. Rücknahme der falschen
   Aufnahme (attendedPeriods auf [] setzen) klären.
2. [ ] WMC_1 (lsId 218839): Badawi Nour ist dort noch gar nicht enthalten
   (0 attending von der falschen Person auch nicht). Nach Klärung von 1.
   ggf. Aufnahme in WMC_1.
3. [ ] Write-Pfad `submitStudentLessonPeriodData` ist ungetestet (nur
   abgeleitet aus Widget-Code + Read-Call validiert). Erster echter
   Write gleichzeitig als Validierung werten.

Last updated: 2026-08-22

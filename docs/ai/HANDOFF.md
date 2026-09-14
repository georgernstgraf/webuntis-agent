Open tasks:

(None)

Recently closed (2026-09-14):

1. [x] Badawi-Verwechslung korrigiert: POS1 (lsId 215940) hatte fälschlich
   "Al Badawi Mahmoud" (19261, klasse 4137) — User bestätigte: richtig ist
   "Badawi Mhd Nour" (19405), und zwar in POS1 (POS-Theorie), NICHT in WMC.
   Korrektur per `students edit --lsid 215940 --class-id 4107
   --add-student-id 19405 --remove-student-id 19261 --no-dry-run`.
   Verifiziert per Matrix-Re-Read: Mahmoud 0 Termine, Nour alle 18
   (2026-09-11 .. 2027-01-29), 17 Klassen-Schüler (klasse 4107) unverändert.
2. [x] WMC_1-Aufnahme (lsId 218839) gestrichen: Nour gehört laut User
   ausdrücklich nicht in WMC. WMC_1 wurde nie beschrieben.
3. [x] Write-Pfad `submitStudentLessonPeriodData` validiert: erster echter
   Write lief erfolgreich (result=null), nachfolgender Re-Read bestätigt.
4. [x] Rana Aaron (21616) und Steindl Jonathan (21592) — beide Klasse 4107,
   fälschlich mit allen 18 Terminen in POS1 UND WMC_1 — aus beiden
   Lektionen entfernt (zwei Writes, je ein `students edit --remove-student-id
   21616 --remove-student-id 21592`). Verifiziert: beide 0 Termine,
   POS1 attending 16 (15 Klasse + Nour), WMC_1 attending 15 (nur Klasse).

Last updated: 2026-09-14

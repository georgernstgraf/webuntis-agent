Open tasks:

(None)

Recently closed (2026-09-16):

1. [x] 16.9.-Zettel "3CAIF NICHT auf Liste" VOLLSTÄNDIG: Kollege hatte
   Ji/Putz/Unger (218881: je 15/17) + Brandstötter/Dominkovic/Imamovic
   (218839/215940: je 17/18) schon eingetragen (nicht aufgefüllt);
   Putz (11912) + Unger (12097) nach Re-Import in 3CAIF verifiziert.
   3 Writes (result=null, Re-Read ok): 218881 +8 (attending 35),
   218839 +7 (attending 29), 215943 +Gavrilovic/Hähsler/Gorgovik
   (attending 28). Alle 21 Reaktivierungs-IDs heuer im System.
2. [x] 3CAIF-POS1 (215943) nachgezogen: +8 (Haimov, Barbut, Moza,
   Möslinger, Szegner, Matyja, Jurci, Ibis), je 18 Termine
   (result=null, Re-Read: attending 36). User unterrichtet 3CAIF
   auch in POS1 — beide 3CAIF-Lektionen damit vollständig.
2. [x] 3BAIF-Zettel (17 Namen) abgeglichen, dann je 1 Write in POS1
   (215940) + WMC_1 (218839): Stritzki (19393, 5AAIF!), Hardes (412),
   Dolezal (16768), Capistrano (5591) je 18/18 Termine (Re-Read ok;
   POS1 attending 20, WMC_1 attending 19; Rana/Steindl bleiben draußen,
   Nour unverändert). Nur SJ 2025/26: Leschnik (21403), Kalkhauser
   (11902), Brandstötter (13382), Odribozic (6297), Kalcina (6476),
   Dominkovic (12087), Strzelecki (12937), Zivkovic (12517), Imamovic
   Tarik (18813), Unger (12097), Parali (11697). KV 3BAIF: Nassler.
2. [x] 3CAIF-Zettel abgeglichen: 7 von 9 Namen nur noch SJ 2025/26
   (Ji 11897, Haimov 9115, Barbut 13207, Jurci 13539, Moza 13574,
   Szegner 11927, Putz 11912); "Händler" korrigiert zu Hähsler
   Matthias (22484). Aktuelle 3CAIF = 23 andere Schüler.
2. [x] Gorgovik Aleksandra (22457) + Hähsler Matthias (22484) in
   WMC_1 (lsId 218881, 3CAIF) aufgenommen: ein Write
   (`students edit --add-student-id 22457 --add-student-id 22484
   --no-dry-run`, result=null), Re-Read: beide 17/17 Termine,
   22 Klassen-Schüler unverändert (attending 24).
3. [x] Such-Fallback gebaut: `search --fallback/--all-years`,
   `students find` (Auto-Fallback, NICHT AKTUELL-Flag), Wrapper `./wu`.

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

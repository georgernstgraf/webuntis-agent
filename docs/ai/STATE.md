# Project State

Current status as of 2026-09-14.

## Current Focus
Student attendance (Schüler-Aufnahme) feature is complete and validated
against the live API.

## Completed (this cycle)
- [x] Badawi-Verwechslung geklärt und korrigiert: falscher Bruder
      (Al Badawi Mahmoud, 19261) aus POS1 (lsId 215940) entfernt,
      richtiger Schüler (Badawi Mhd Nour, 19405) aufgenommen
- [x] New CLI subcommand `students edit` (single-write add/remove,
      dry-run default, payload export via --out)
- [x] Write-Pfad `submitStudentLessonPeriodData` erstmals live genutzt
      und per Matrix-Re-Read validiert (result=null = success)
- [x] Klarstellung: Nour gehört in POS1 (POS-Theorie), NICHT in WMC_1;
      WMC_1 (lsId 218839) blieb unangetastet
- [x] Rana Aaron (21616) und Steindl Jonathan (21592) aus POS1 und WMC_1
      entfernt (laut User gehören beide in keines der beiden Fächer;
      je 1 Write, verifiziert per Matrix-Re-Read)

## Earlier (2026-08-22 cycle)
- [x] School year 2025/26 fully closed: 418 periods Lehrstoff + Absenzen
- [x] lehrstoff status/fill/verify/fill-fixed CLI commands
- [x] Phase 1/2 API reverse-engineering (SPA routes, class-register
      iframe, lessonstudentlist.do, student matrix read-call)
- [x] students add CLI (dry-run default)

## Pending
- None open.

## Blockers
- None.

## Notes
- Lesson ids 215940 (POS1) / 218839 (WMC_1) sind im Schuljahr 2026/27
  stabil gültig; Klassenregister-Klasse der Lektion ist 4107 (21 Schüler,
  15 attending), externe Aufnahmen haben klasse 4137 (5BAIF).

## Next Session Suggestion
- Nothing queued; new feature requests as they come up.

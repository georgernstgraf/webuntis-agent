# Project State

Current status as of 2026-09-21 (Domain-CLI, harter Schnitt).

## Current Focus
Domain-CLI umgesetzt: `klasse`, `lesson` (KLASSE/FACH), `student`,
`offen`, `search` (mit --detail-Dispatch), `intern` (versteckt).
Alte Befehle ersatzlos gestrichen (keine Aliase), UI deutsch,
JSON-Schlüssel englisch. Tests 45/45 grün. Skill `fill-open-periods`
auf `offen vorschlag/eintragen/pruefen` migriert.

## Completed (this cycle)
- [x] CLI-Gerüst: deutsche Hilfe (description + Beispiele je Gruppe),
  `--schuljahr-id`, `--von/--bis`, `--datum (heute|…)`,
  `--testlauf/--ausfuehren`, KLASSE/FACH-Extraktion (`_extract_adresse`,
  s. PITFALLS.md), UnknownLessonError-Text aktualisiert
- [x] `klasse` (Übersicht: KV + Fächer + Roster), `roster`, `faecher`, `kv`
- [x] `lesson`: Roster (Default, Zukunfts-Fallback), `matrix`,
  `termine` (+ `--mit-lehrstoff`), `info`, `lehrstoff zeigen/eintragen/aus-git`,
  `absenzen zeigen` (fehlt/gehalten, nur gehaltene Termine),
  `absenzen pruefen` (einzeln/lesson-weit),
  `aufnehmen`/`anpassen` (Testlauf-Standard)
- [x] `student`: Suche (Fallback/Alle-Jahre) + Detail (KV, belegt/nicht
  belegt, Absenzen via Klassen-Matrix-Scan)
- [x] `offen`: liste/status/verifizieren/vorschlag/eintragen/festtexte/pruefen
- [x] `search --detail`: Dispatch Student→Detail, Lehrer→Steckbrief +
  KV-Klassen (Wochenplan fremder Lehrer nicht lesbar, s. PITFALLS.md),
  Klasse→Übersicht
- [x] Doku: README (Migrationstabelle), WEBUNTIS_API.md, ARCHITECTURE.md,
  CONVENTIONS.md, DECISIONS.md (#15-Split → HISTORY.md), PITFALLS.md
- [x] live verifiziert (Lesen + Testläufe): klasse/lesson-Roster, termine,
  matrix, info, absenzen zeigen, student-Detail, search-Dispatch,
  offen liste/status/vorschlag/festtexte, aufnehmen-Testlauf

## Pending
- None.

## Blockers
- None.

## Notes
- Matrix-`name` gekürzt, Matrix-Daten int YYYYMMDD (Details: PITFALLS.md).
- `student`-Detail scannt je Klassen-Lesson eine Matrix (Rate-Limit
  beachten); klassenfremde Teilnahme nicht enthalten.
- Resolver-Fenster heute−7/+13 Tage: außerhalb keine `lsId`-Auflösung →
  `--lsid` direkt.

## Next Session Suggestion
- Nächster Code-Review ab dem Commit dieser Serie (Fixpunkt siehe HANDOFF.md).

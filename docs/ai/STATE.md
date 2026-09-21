# Project State

Current status as of 2026-09-21 (Stundenplan-Serie, nach Domain-CLI).

## Current Focus
Lesson-Enumeration aus dem Stundenplan umgestellt: `klasse faecher`,
`student` und der Resolver arbeiten primär auf timetable/entries +
calendar-entry/detail; Absenz-Writes (eintragen/entfernen) und
`raum`-Stubs angebaut. Tests 65/65 grün. Live verifiziert (lesend +
Testläufe).

## Completed (this cycle)
- [x] RE: Stundenplan-Endpunkte (entries/grid/filter/calendar,
  calendar-entry/detail, rooms/form) + Absenz-Write-Workflow
  (insert/delete/absenceRows/Dialog-CSRF) aus 2 CDP-Recordings
- [x] Join verifiziert: `lesson.lessonId` == Matrix-lsId (WMC-Block
  3BAIF); classregpage-ViewModel enthält lessonId + students
  (absent/absenceId) + absenceRows
- [x] Client: get_timetable_entries/get_calendar_entry_detail/
  get_rooms_form + Parser (parse_timetable_entries,
  group_timetable_lessons: Klasse/Fach/Primary-Lehrer) +
  parse_dojo_viewmodel + set_absence/delete_absence/
  get_classreg_viewmodel
- [x] `student`: Plan-Join (belegt = eingeschrieben, klassenfremde
  Lessons, 0 Matrix-Calls), `--absenzen` opt-in (nur eigene Lessons
  via MY_TIMETABLE, da Matrix rechte-beschränkt)
- [x] `klasse/faecher`: alle Lessons aus Klassen-Plan, `eigen` per
  Slot-Match, Primary-Anzeige bei parallelen Gruppen, offen-Count
- [x] Resolver: Plan→Match→Detail→lsId, eigene-Lesson-Bevorzugung bei
  Mehrdeutigkeit, open-periods-Fallback
- [x] `absenzen eintragen/entfernen` (Testlauf-Standard, Block-Default,
  --kein-block nur mit --termin-id), `absenzen zeigen --termin-id`
  (echte Absenz-Einträge)
- [x] `raum suchen/groesse` Stubs (Exit 3)
- [x] Doku: WEBUNTIS_API.md (Schablonen, anonymisiert), PITFALLS,
  CONVENTIONS (Anonymisierungs-Regel, Doku-Schablonen-Regel),
  DECISIONS, ARCHITECTURE
- [x] Live: klasse 3BAIF faecher (18 Lessons, 3 parallele POS1-Gruppen,
  eigen korrekt), student = POS1+WMC_1 (0 Matrix), --absenzen 2/2+2/2,
  Resolver 3baif/pos1 -> eigene lsId, Absenz-Testläufe, raum rc=3
- [x] `student --id <ID>` Direktzugriff per Schüler-ID (Alternative zum
  Namen, `_suchen_per_id` über students/overview, nur aktuelles Roster —
  kein Jahr-Fallback; genau eins aus NAME/--id, sonst Exit 2) (#19)

## Pending
- Live-Absenz-Write-Verifikation (Setzen+Löschen am Testtermin,
  netto null) — wartet auf Nutzer-Go.

## Blockers
- None.

## Notes
- Parallele Gruppen desselben Fachs (POS1_3BAIF_1/2/3): Team-Teilung,
  Schüler besuchen ggf. alle; E1x/E1y-Gruppenwahl nur eine — Join bildet
  beides korrekt ab (Primary-Lehrer + Slot-Fakten).
- MY_TIMETABLE/TEACHER-Plan anonymisiert eigene Lehrerposition →
  eigen-Markierung per Slot-Match, NICHT per Lehrer.
- Matrix rechte-beschränkt: fremde lsIds melden Internal server error
  (wie unbekannte) — UnknownLessonError-Hinweis angepasst.
- Resolver-Fenster heute−7/+13 bleibt nur als Fallback (Plan primär).

## Next Session Suggestion
- Code-Review ab Commit dieser Serie (Fixpunkt s. HANDOFF.md).
- Folgeissue: `raum suchen` echte Freie-Raum-Suche (Belegung aus
  ROOM-entries je Slot, capacity-Filter; availability-Semantik offen).

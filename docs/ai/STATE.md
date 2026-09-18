# Project State

Current status as of 2026-09-18 (later session, Feature #16).

## Current Focus
Ticket #16 (`students roster`: Excel-pasteable TSV-Einheiten-Teilnehmerliste)
umgesetzt und geschlossen — inkl. Closest-Match-Auto-Pick mit
stderr-Labelblock, exakter Untis-Kopfzeile und Future-first-Fallback.
Nur Reads, keine Writes. Tests 41/41 grün (16 neu, Fake-Daten).

## Completed (this cycle)
- [x] #16 `students roster CLASS SUBJECT --date <YYYY-MM-DD|now>` (Default `now`): TSV `Nachname Vorname<TAB>Klasse`, Header default, sortiert
- [x] #16 Namens-Join via `students/overview` (Matrix-Namen gekürzt), Klasse via `allKlassen`, `studentCount`-Kreuzcheck
- [x] #16 Mehrdeutigkeit: Closest-Match-Auto-Pick + Warnblock (eine `class/subject (date)`-Zeile pro Kandidat); `--date`-Default `now`
- [x] #16 Future-first-Fallback (nächste zukünftige sonst letzte gehaltene Einheit), effektives Datum in Kopfzeile + `requestedDate`
- [x] #16 live verifiziert: 4AHWIT PMM --date now (14 Zeilen), 3AAIF WMC Fallback 2026-09-22 (15 Zeilen)

## Pending
- None.

## Blockers
- None.

## Notes
- Matrix-`name` gekürzt, Matrix-Daten int YYYYMMDD (Details: PITFALLS.md).
- `lessonSubject` der Matrix ist Vollname-Liste, `lessonKlassen` teils leer — Label daher aus Open-Periods (Resolver bzw. Reverse-Lookup), nicht aus der Matrix.
- Resolver-Fenster heute−7/+13 Tage: außerhalb keine `lsId`-Auflösung → `--lsid` direkt.

## Next Session Suggestion
- Nächster Code-Review ab dem Commit dieser Serie (Fixpunkt siehe HANDOFF.md).

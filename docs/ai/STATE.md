# Project State

Current status as of 2026-09-24 (nach Session-Fixes #25).

## Current Focus
Robustheit gegen reale WebUntis-Antworten + schlanker `student`-Default:
Null-Feld-Crashs bei open-periods behoben, Fach-Match nur noch in eine
Richtung, `student`-KeyError 'class' gefixt, `student` zeigt Details nur
mit `--details` (Default schnell). Tests 131/131 grün (Unit,
Fake-Clients, kein Netz).

## Completed (this cycle, #25)
- [x] Null-Feld-Crashs: `PeriodFields.from_raw`, `_open_period_entries`,
  `_period_summary`, `_klasse_kandidaten`, `_format_search_hit` sichern
  `subject`/`classes`/`teachers`/`rooms`/`dtRange`/`periods: null` per
  `or {}`/`or []` ab; `lessonDetailsUrl = None` ohne classId
- [x] Fach-Match `_subject_matches`: exakt ODER Query ist Kürzung
  (`pmm` → `PMMx`); Rückrichtung entfernt (`pmmx` ≠ `PMM`)
- [x] `_faecher_aus_plaenen._lesson_item` liefert `class` (Text-Crash
  „Klassenfremde Lessons" + JSON)
- [x] `student`: Default nur Trefferliste; `--details` für Klasse/KV/
  Fächer; `--absenzen` impliziert `--details`; gilt für Text + `--json`
  (spart ~4 API-Calls/Treffer)
- [x] Doku: man/wu.1, README, WEBUNTIS_API, DECISIONS, PITFALLS
- [x] Tests: test_period_fields, test_subject_matches, student-Default/
  --details/absenzen

## Pending
- Live-Verifikation der Fehlerklassen (Netz/Auth/Server) an echten
  Endpunkten (siehe #23).
- Code-Review ab Fixpunkt.

## Blockers
- None.

## Notes
- Pre-Push-Hook `scripts/pre-push` läuft `pytest tests/` und blockt rote
  Pushes; pro Clone per Symlink nach `.git/hooks/pre-push` (README).
- `dict.get(k, default)` greift NUR bei fehlendem Key — WebUntis liefert
  Felder auch als JSON `null` (s. PITFALLS.md).
- `WuError` erbt von `RuntimeError`: Soft-Fail-Handler
  (`except RuntimeError: print(...)`) bleiben nutzbar.
- `raum suchen/groesse` sind Stubs mit Exit 7 (vorher 3).
- `wu`-Wrapper: fehlende Module → Exit 8 (= ConfigError).
- `offen eintragen`/`offen pruefen` mit `--datei` laufen im Testlauf
  ohne Login (Dry-Run vor `_make_client`).

## Next Session Suggestion
- Live-Verifikation der Fehlerklassen; Code-Review ab Fixpunkt.
- Folgeissue #22: `raum suchen` echte Freie-Raum-Suche.

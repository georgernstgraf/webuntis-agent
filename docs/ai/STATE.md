# Project State

Current status as of 2026-09-21 (nach Man-Page + offen-Default).

## Current Focus
Bedienbarkeit und Standard-Workflow: autoritative Man-Page `man/wu.1`
(Drift-Test) und `offen`-Schuljahr-Default (Schuljahr-Start..heute aus
`open-periods/meta`). Tests 83/83 grün, Live verifiziert.

## Completed (this cycle)
- [x] Man-Page `man/wu.1` (groff, deutsch): alle Kommandos/Subs,
  Optionen, Workflows, Exit-Codes (0/1/2/3), FILES/ENVIRONMENT,
  Hinweise/Fallen, INTERNALS (verstecktes `intern`), fiktive Beispiele (#20)
- [x] `tests/test_manpage.py`: Drift-Test (Inventar aus `cli*.py`,
  groff-Render-Check) (#20)
- [x] `AGENTS.md`-Abschnitt "CLI manual" (Agents lernen Pfad) +
  `README.md`-Verweis (#20)
- [x] `/open-periods`-Re-Record (20260921-231543) ausgewertet: UI-Route
  ruft `POST classreg/open-periods`; neu `GET classreg/open-periods/meta`
  (`allowedFilters`, `defaultFilter`, `schoolYear`-Range) (#21)
- [x] `Client.get_open_periods_meta()` + `_resolve_von_bis()`:
  `--von/--bis` bei allen `offen`-Befehlen optional, Default
  Schuljahr-Start..heute (Ende gedeckelt), halb → Exit 2 (#21)
- [x] `tests/test_offen_default.py` (5 Tests) (#21)
- [x] Doku: WEBUNTIS_API.md (Meta-Template + UI-Quelle),
  DECISIONS/CONVENTIONS/PITFALLS/HANDOFF (Brave-Rauschen ≠
  Recorder-Fehler; Heute-Cap) (#21)

## Pending
- Code-Review ab Fixpunkt (s. HANDOFF.md).

## Blockers
- None.

## Notes
- Man-Page deckt auch das versteckt `intern` ab (DECISIONS: Escape-Hatch).
- `groff -man -Tutf8` warnungsfrei; `man --local-file man/wu.1` rendert.
- offen-Zeitraum ohne Flags: ein Meta-Call zusätzlich; Meta-Ausfall ohne
  expliziten Zeitraum wirft (kein Raten).
- Brave-Debug-Meldungen (`OpenH264`, `puffin … Operation not permitted`)
  sind Browser-Rauschen, kein Recorder-Fehler (PITFALLS).

## Next Session Suggestion
- Code-Review ab Commit dieser Serie (Fixpunkt s. HANDOFF.md).
- Folgeissue: `raum suchen` echte Freie-Raum-Suche (Belegung aus
  ROOM-entries je Slot, capacity-Filter; availability-Semantik offen).

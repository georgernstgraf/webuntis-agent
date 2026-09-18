# Project State

Current status as of 2026-09-18 (later session, Review-Serie).

## Current Focus
Tickets #13 (Spec-Drift), #14 (cli-Duplikate) und #15 (Struktur)
umgesetzt und geschlossen — auf Basis des Vollbaum-Reviews
(Standards 0 hard/~12 Smells, Spec 4 partiell + 1 Akzeptanz-Bruch #5)
mit Fixpunkt 5dc4e13. Keine Live-Writes durchgeführt.

## Completed (this cycle)
- [x] #13 `--school-year-id` vor+nacher Subcommand (SUPPRESS), `fill-fixed --json` im Write-Pfad, egg-info rebuildet (playwright weg, gitignored)
- [x] #14 Helper extrahiert (`_sleep_between`, `_resolve_topic_id`, `_base_period_fields`, `_finish_students_command`, `_no_open_periods`, Login via `_make_client`); `url_fields`-Entscheidung dokumentiert (nur `batch-set`)
- [x] #14 Nebenbefund: `batch-check`-Delay-NameError aus der Refactor-Reihenfolge, gefixt + Regressionstest tests/test_absences.py
- [x] #15 cli-Split in cli_{common,lehrstoff,students,absences,misc} (dünnes cli.py mit Re-Exports), Domain-Typen (`PeriodFields`/`LessonGroup`/`SubmitItem`) per Differenzialtest byte-identisch, Kleinkram (Namen, `Client`-Typen, Chains)
- [x] #15 bewusst behalten: `element_type`-Param, `get_commit_diff_by_name`, `sy`-Konvention; ARCHITECTURE/CONVENTIONS nachgezogen
- [x] Tests 25/25 grün (24 bestehend + 1 neu)

## Pending
- None.

## Blockers
- None.

## Notes
- `git pull --ff-only` scheitert bei dirty tree (rebase-config) — per `git fetch` geprüft: kein Upstream-Vorsprung, kein Konflikt.
- Malformed batch-items geben `ok: false` statt Crash (`SubmitItem.from_dict`-Guard).
- `fill`-Write-Pfad (nicht `-fixed`) gibt wie `batch-set` immer JSON — konsistent, kein Handlungsbedarf.

## Next Session Suggestion
- Nächster Code-Review ab dem Commit dieser Serie (Fixpunkt siehe HANDOFF.md).

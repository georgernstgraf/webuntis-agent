Open tasks:

- Live-Verifikation der neuen Fehlerklassen (Netz 5 / Auth 4 / Server 6)
  an echten Endpunkten — bisher nur Unit-Tests mit Fake-Clients
  (siehe #23).
- Code-Review ab dem Fixpunkt dieses Commits (`git log`).

Offen für später:
- #22 `raum suchen` echte Freie-Raum-Suche (ROOM-Belegung je Slot,
  capacity-Filter; `availability`-Semantik ungeklärt).

Erledigt (Session 2026-09-24, #25, Commit s. `git log`):
- Null-Feld-Crashs bei open-periods (`subject`/`classes`/`teachers`/
  `rooms`/`dtRange`/`periods: null`) in `cli_common.py` abgesichert.
- `_subject_matches` nur noch in eine Richtung (`pmm` → `PMMx`, nicht
  umgekehrt).
- `student`: KeyError 'class' bei klassenfremden Lessons gefixt;
  Default nur Trefferliste, Details mit `--details`, `--absenzen`
  impliziert `--details` (Text + `--json`).
- Tests 131/131; `groff` warnungsfrei.

Vorherige Serien (committed): Session-Härtung (#23/#24), Man-Page +
`offen`-Default (#20/#21), Domain-CLI (#17), Stundenplan-Serie (#18).

Last updated: 2026-09-24

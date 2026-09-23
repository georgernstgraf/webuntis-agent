Open tasks:

- Live-Verifikation der neuen Fehlerklassen (Netz 5 / Auth 4 / Server 6)
  an echten Endpunkten — bisher nur Unit-Tests mit Fake-Clients
  (siehe #23).
- Code-Review ab dem Fixpunkt dieses Commits (`git log`).

Erledigt (Session 2026-09-23, #23, Commit s. `git log`):
- Exit-Code-Taxonomie (`errors.py`, 0–9, `classify_exit`, Client-
  Übersetzung, `cli.main()` als einziger Exit-Punkt).
- Nutzungsfehler zeigen die volle Unterbefehl-Hilfe (`_HelpfulParser`,
  `usage_error`, `_attach_parsers`); `wu` ohne Argumente → Top-Hilfe,
  Exit 1.
- `search` entfernt → `lehrer`; `student`/`klasse` mit eingebetteter
  Suche (Kandidatenvorschlag).
- ALLE Writes testlauf-Standard (`--testlauf`/`--ausfuehren`); Ausnahme
  dokumentiert: `intern rpc`/`intern rest`.
- `AGENTS.md`: Git-Reglementierung entfernt (Agenten entscheiden selbst).
- `man wu` nutzerlokal (`~/.local/share/man/man1/wu.1`), README-Anleitung.
- Tests 112/112; `groff -man -Tutf8 man/wu.1` warnungsfrei.

Nachtrag (#24):
- Pre-Push-Hook `scripts/pre-push` (pytest vor jedem Push, blockt rote
  Pushes). Installiert per Symlink `.git/hooks/pre-push` (nicht
  versioniert); README-Abschnitt „Tests vor jedem Push (Git-Hook)".

Vorherige Serien (committed): Man-Page + `offen`-Default (#20/#21),
Domain-CLI (#17), Stundenplan-Serie (#18).

Offen für später:
- #22 `raum suchen` echte Freie-Raum-Suche (ROOM-Belegung je Slot,
  capacity-Filter; `availability`-Semantik ungeklärt).

Last updated: 2026-09-23

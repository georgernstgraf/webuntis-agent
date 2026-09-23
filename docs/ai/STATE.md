# Project State

Current status as of 2026-09-23 (nach CLI-Härtung #23).

## Current Focus
Robuste, sichere CLI: eindeutige Exit-Codes je Fehlerklasse,
hilfreiche Nutzungsfehler (volle Unterbefehl-Hilfe), aufgeräumtes
Befehlsvokabular (`search`→`lehrer`) und durchgängiger Schreibschutz
(alle Writes `--testlauf`-Standard). Tests 112/112 grün (Unit,
Fake-Clients, kein Netz).

## Completed (this cycle, #23)
- [x] `errors.py`: `WuError` + 8 Subklassen mit `exit_code` 2–9;
  `classify_exit()` (Cause-Chain); `UnknownLessonError` = NotFound
- [x] Client: `_check_status()` (401/403→Auth, 404→NotFound, 5xx→Server),
  `httpx.TransportError`→Network, JSON-RPC→Server, Login/Setup typisiert
- [x] `cli.main()` einziger Exit-Punkt (0–9, `KeyboardInterrupt`→130,
  Unerwartetes→9 mit Traceback)
- [x] `_HelpfulParser` + `usage_error()` + `_attach_parsers`; keine
  Argumente → Top-Hilfe Exit 1
- [x] `search` entfernt (`cli_suche.py` gelöscht), neu `lehrer`;
  `klasse` mit Kandidatenvorschlag bei Namens-Fehltreffer
- [x] Write-Guard: `lesson lehrstoff eintragen`, `lesson absenzen
  pruefen`, `offen eintragen`, `offen pruefen` mit
  `--testlauf/--ausfuehren`; `intern rpc`/`intern rest` ausgenommen
- [x] `AGENTS.md`: Git-Reglementierung entfernt
- [x] `man wu` nutzerlokal (`~/.local/share/man/man1/wu.1`) + README
- [x] Tests: test_errors, test_usage_help, test_lehrer,
  test_klasse_fuzzy, test_write_guard; bestehende angepasst
- [x] Doku: man/wu.1, README, WEBUNTIS_API, docs/ai/*, Skill
  fill-open-periods

## Pending
- Live-Verifikation der Fehlerklassen (Netz/Auth/Server) an echten
  Endpunkten (siehe #23).
- Code-Review ab Fixpunkt.

## Blockers
- None.

## Notes
- `WuError` erbt von `RuntimeError`: Soft-Fail-Handler
  (`except RuntimeError: print(...)`) bleiben nutzbar.
- `raum suchen/groesse` sind Stubs mit Exit 7 (vorher 3).
- `wu`-Wrapper: fehlende Module → Exit 8 (= ConfigError).
- `offen eintragen`/`offen pruefen` mit `--datei` laufen im Testlauf
  ohne Login (Dry-Run vor `_make_client`).

## Next Session Suggestion
- Live-Verifikation der Fehlerklassen; Code-Review ab Fixpunkt.
- Folgeissue #22: `raum suchen` echte Freie-Raum-Suche.

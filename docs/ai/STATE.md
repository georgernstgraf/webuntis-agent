# Project State

Current status as of 2026-09-17 (later session, Bugfix-Serie).

## Current Focus
Alle 11 Tickets (#2–#12) aus dem Problemezettel abgeschlossen und
geschlossen — inkl. #11 (Live-Write + vollständiger Revert) und #12
(alle 5 Unterpunkte; cookies entfernt, Escape-Hatch in DECISIONS.md).

## Completed (this cycle)
- [x] #9 Doku 302 korrigiert (PITFALLS + CONVENTIONS), 642c6a6
- [x] #7 batch-set --delay Default 0.5→1.0, 149906b
- [x] #6 fill-fixed Dry-Run-Default + --no-dry-run, 83c472b
- [x] #2 recorder.main(argv) + record-Optionen am Subparser, 2a13c8d
- [x] #4 resolve_schoolyear_id wirft statt falscher Arithmetik (21 vs 24), 787e446
- [x] #8 Login fail-closed bei fehlendem anonymousMode-Marker, 0080fe1
- [x] #10 JSON-RPC-Fehler werden ausgelöst (_raise_jsonrpc_error in rpc()/_jsonrpc_web inkl. setSchoolyear), 90c9a22
- [x] #3 fill nutzt echte dtRange-Zeiten (startIso/endIso in _period_summary) + Gruppierung nach lsId, live verifiziert, 4b6b47a
- [x] #5 --school-year-id durch students-Befehle in setSchoolyear gethreadet, 63b5c06
- [x] #11 _build_students_payload (edit-Semantik) für add+edit, 9e88068; live verifiziert: Write auf lsId 215940 (Ziel 0→18/18, attending 24→25), Revert exakt (alle attendedPeriods byte-identisch zum Vorher-Stand)
- [x] #12 Unterpunkte 1/3/4/5 (chmod-Race os.open 0o600, playwright-Dep raus, fetch_bodies gelöscht, _submit_topic_entries-Helper), 53b56ce; Unterpunkt 2: cookies-Befehl entfernt, Escape-Hatch-Pfad in DECISIONS.md dokumentiert

## Pending
- None.

## Blockers
- None.

## Notes
- Live-Verifikation offenbart: `setSchoolyear` akzeptiert ungültige
  Schuljahr-IDs still (kein Fehler) — Server-Verhalten, dokumentiert in #5.
- dtRange liefert echte ISO start/end je Periode — die frühere
  +1:50-Heuristik war nie nötig.
- `rpc`-Passthrough wirft bei Error-Payloads jetzt RuntimeError
  (Exit ≠ 0) statt Error-JSON auszudrucken.
- Browser-Cookie-Harvest (Captcha/Lockout-Escape-Hatch): siehe
  DECISIONS.md 2026-09-17.

## Next Session Suggestion
- Neue Feature-Wünsche nach Bedarf.

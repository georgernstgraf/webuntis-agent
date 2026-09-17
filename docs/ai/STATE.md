# Project State

Current status as of 2026-09-17 (later session, Bugfix-Serie).

## Current Focus
11 Tickets aus dem Problemezettel als GitHub Issues #2–#12 angelegt;
Orchestrierung im Default läuft: 9 von 11 abgearbeitet, #11/#12 fast
fertig (je 1 offener Punkt).

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
- [x] #11 Code-Fix: _build_students_payload (edit-Semantik) für add+edit; dry-run-Verifikation lsId 215940 (Payloads identisch, 34 statt 32), 9e88068 — Issue offen bis Live-Write
- [x] #12 Unterpunkte 1/3/4/5: chmod-Race (os.open 0o600), playwright-Dep raus, fetch_bodies gelöscht, _submit_topic_entries-Helper (batch-set/fill/fill-fixed), 53b56ce — Issue offen (Unterpunkt 2 cookies)

## Pending
- #11: ein live-verifizierter `--no-dry-run`-Write (students add) durch
  den User abnehmen lassen.
- #12.2: `cookies`-TODO — Entscheidung entfernen vs. implementieren.

## Blockers
- None.

## Notes
- Live-Verifikation offenbart: `setSchoolyear` akzeptiert ungültige
  Schuljahr-IDs still (kein Fehler) — Server-Verhalten, dokumentiert in #5.
- dtRange liefert echte ISO start/end je Periode — die frühere
  +1:50-Heuristik war nie nötig.
- `rpc`-Passthrough wirft bei Error-Payloads jetzt RuntimeError
  (Exit ≠ 0) statt Error-JSON auszudrucken.

## Next Session Suggestion
- #11-Write-Abnahme, #12.2-Entscheidung, dann beide Issues schließen.

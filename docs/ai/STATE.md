# Project State

Current status as of 2026-09-14.

## Current Focus
Student attendance (Schüler-Aufnahme) feature is complete and validated
against the live API.

## Completed (this cycle)
- [x] Badawi-Verwechslung geklärt und korrigiert: falscher Bruder
      (Al Badawi Mahmoud, 19261) aus POS1 (lsId 215940) entfernt,
      richtiger Schüler (Badawi Mhd Nour, 19405) aufgenommen
- [x] New CLI subcommand `students edit` (single-write add/remove,
      dry-run default, payload export via --out)
- [x] Write-Pfad `submitStudentLessonPeriodData` erstmals live genutzt
      und per Matrix-Re-Read validiert (result=null = success)
- [x] Klarstellung: Nour gehört in POS1 (POS-Theorie), NICHT in WMC_1;
      WMC_1 (lsId 218839) blieb unangetastet
- [x] Rana Aaron (21616) und Steindl Jonathan (21592) aus POS1 und WMC_1
      entfernt (laut User gehören beide in keines der beiden Fächer;
      je 1 Write, verifiziert per Matrix-Re-Read)
- [x] Name-Auflösung für Lehrer geklärt: getTeachers/REST-/teachers 403,
      Message-Empfänger anonymisiert — einziger Weg ist
      GET /v1/timetable/search?q=..&schoolyear=.. (Kürzel → Vollname);
      getKlassen().teacher1 liefert die KV-Teacher-ID
- [x] Neue CLI-Commands: `search <text>` (Timetable-Suche), `kv <klasse>`
      (Klassenvorstand, id oder Name), `students list --lsid`
      (Attendance-Matrix dumpen)
- [x] Session-Cache: `webuntis-agent login` persistiert die Session
      (`.webuntis_session.json`, gitignored, chmod 600); alle Commands
      nutzen den Cache, `_request_with_retry` logt bei Session-Verlust
      (401 ODER 302→index.do) transparent 1× neu. `logout` räumt auf.
- [x] Login-Verifikation repariert: 302 der j_spring_security_check ist
      KEIN Erfolgssignal (falsche Passwörter liefern ebenfalls 302 +
      neue anonyme JSESSIONID!). Verifikation über die SPA-Bootstrap-
      Seite: `anonymousMode:true` + `loginError` → klarer RuntimeError,
      keine bogus Sessions im Cache mehr.

## Pending
- None open. (Login-Sperre nach den Wrong-Password-Probes hat sich
  gelöst; `webuntis-agent login` erfolgreich inkl. anonymousMode-
  Verifikation, Cache-Flow live bestätigt.)

## Earlier (2026-08-22 cycle)
- [x] School year 2025/26 fully closed: 418 periods Lehrstoff + Absenzen
- [x] lehrstoff status/fill/verify/fill-fixed CLI commands
- [x] Phase 1/2 API reverse-engineering (SPA routes, class-register
      iframe, lessonstudentlist.do, student matrix read-call)
- [x] students add CLI (dry-run default)

## Pending
- (see top Pending item: temporary login block, retry later)

## Blockers
- None. (Temporäre Login-Sperre nach Diagnose-Probes hat sich gelöst.)

## Notes
- Lesson ids 215940 (POS1) / 218839 (WMC_1) sind im Schuljahr 2026/27
  stabil gültig; Klassenregister-Klasse der Lektion ist 4107 (21 Schüler,
  15 attending), externe Aufnahmen haben klasse 4137 (5BAIF).
- Beispiel: KV von 5AAIF (klasse 4134) ist Schiefer, Birgit (SB,
  teacher id 147) — `kv 5AAIF`.

## Next Session Suggestion
- Nothing queued; new feature requests as they come up.

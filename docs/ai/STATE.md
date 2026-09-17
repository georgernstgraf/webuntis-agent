# Project State

Current status as of 2026-09-17.

## Current Focus
Issue #1 (CLI gaps + undocumented API findings, session 2026-09-17)
is fully implemented and live-verified; commit issued, issue stays
open until `finish` mode.

## Completed (this cycle)
- [x] Generic passthrough: `rpc <method> [params-json]` and
      `rest <path> [--method] [--data-json]` (Variante B — write-capable,
      method+body echoed to stderr; HTTP method does NOT imply read/write
      in this API)
- [x] `lesson info <lsid>` — lessonTeachers, lessonKlassen,
      mainStudentgroupId, period span, per-klasse roster vs. attending
      (text view only attending > 0, `--json` for everything)
- [x] `session status` — cache age/savedAt, masked JSESSIONID, live check
      via `app/data` (exit 2 = dead session)
- [x] `kv --student <name>` — student -> class(es) via students/overview
      -> KV per class (tokenizing match; ambiguous hits listed)
- [x] `app/data` real route discovered: `/WebUntis/api/rest/view/v1/app/data`
      (payload: user incl. person/permissions, roles, currentSchoolYear
      with timeGrid units)
- [x] Doku-Nachzug WEBUNTIS_API.md: login-302 is NO success signal
      (anonymousMode/loginError verification), token/new 302->index.do
      as dead-session signature, single-session suspicion (parallel
      logins invalidate earlier sessions), app/data section, CLI list
- [x] `wu` wrapper fixed: symlink resolution (`readlink -f`),
      `.venv/bin/python` autodetect, German dependency guide
      (import-probe of httpx/websockets/playwright, exit 1 on fallback
      path); `cli.main()` catches ModuleNotFoundError (exit 3)
- [x] Live smoke (all green): session status (incl. transparent re-login
      of a 2-day-old dead session), rpc getCurrentSchoolyear,
      rest schoolyears (GET) + open-periods (POST, read-only),
      lesson info on lsId 215940, kv/kv --student on real cases
- [x] 8/8 pytest (tests/test_gitlog.py), privacy check on diff clean

## Pending
- None open. Issue #1 awaits `finish` mode (close with final report).

## Blockers
- None.

## Notes
- `rest` passthrough paths are relative to `/WebUntis/api`, e.g.
  `rest rest/view/v1/schoolyears` — the leading `rest/` segment belongs
  to the real route layout (`/api/rest/view/v1/...`).
- `session status` refreshed an old cached session via transparent
  re-login; cache file gets rewritten by `login()` automatically.

## Next Session Suggestion
- Run `finish` for Issue #1 when the user confirms; new feature
  requests as they come up.

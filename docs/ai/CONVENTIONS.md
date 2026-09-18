# Conventions

Coding patterns, naming rules, and style agreements for this project.
Follow these without question. Do not deviate unless explicitly told.

## Naming
- Class names from WebUntis are UPPERCASE (e.g. `5AHWII`); git folder names are lowercase (e.g. `5ahwii/`). Always lowercase for git pathspec.
- WebUntis subject short names: `SWP1x`, `SWP1y`, `WMC_1`, `INFIx`, `POS1`, `POS2` — prefix-matched against `SUBJECT_REPO_MAP`
- Recording files: `{timestamp}_{domain_with_underscores}_{type}.jsonl`

## File Layout
- `src/webuntis_agent/` — Python package (recorder, client, gitlog, cli + cli_{common,lehrstoff,students,absences,misc})
- `scripts/` — shell scripts (brave-debug.sh) and helper scripts (show-cookies.py)
- `recordings/` — gitignored, contains session cookies and captured traffic
- `docs/WEBUNTIS_API.md` — authoritative API reference
- `docs/ai/` — knowledge persistence files
- `.opencode/skills/` — opencode skills (fill-open-periods)
- `.env` — gitignored, contains WEBUNTIS_USER/PASSWORD
- `wu` — CLI shortcut wrapper: resolves symlinks (`readlink -f`) so it works from any directory; prefers the repo's `.venv/bin/python`, falls back to `python3` with an import-probe of httpx/websockets and a German setup guide (exit 1) when modules are missing; `cli.main()` additionally catches ModuleNotFoundError (exit 3) for direct `python -m` calls

## API Patterns
- All REST calls go through `Client._rest_headers()` which injects Cookie, Authorization (Bearer JWT), Tenant-Id, X-Webuntis-Api-School-Year-Id
- `_request_with_retry(..., headers=...)` MUST receive auth-dependent headers as a CALLABLE (not a dict) — after a transparent re-login the retry must pick up the NEW cookie/JWT; a static dict replays the dead session
- HTTP method does NOT imply read/write in this API: `open-periods` and all JSON-RPC are POST but read-only; writes are `PUT classreg/lesson-topics`, `submitStudentLessonPeriodData`, `absencechecked` POST. Generic passthrough (`rpc`/`rest` CLI) is therefore write-capable by design (Variante B), method+body echoed to stderr
- REST view routes live under `/WebUntis/api/rest/view/v1/...` (e.g. `app/data` = `/api/rest/view/v1/app/data`, NOT `/api/app/data`)
- Person search: exact `search_timetable()` matches NO multi-word phrases and student displayNames are anonymized — use the shared `search_timetable_tokens()` fallback (tokenize + shortname heuristic, flagged via `searchNote`); only `students find` falls back to older years automatically, everything else keeps the current-year default; non-current hits must always be flagged NICHT AKTUELL (`current: false`)
- JWT is auto-refreshed 60s before expiry
- Login via `POST /WebUntis/j_spring_security_check` (form-encoded, not JSON); the 302 redirect is NOT a success signal — verify via the `anonymousMode` marker (see `client.login()`, docs/WEBUNTIS_API.md § login)
- `batch-set` uses `--delay 1.0` (1 second between PUTs) to avoid IP rate-limiting
- `id: 0` in PUT body creates a new topic; existing `id` updates
- `--school-year-id` works before AND after the subcommand (subparser copies use `default=SUPPRESS`, subcommand wins on double use)
- `fill-fixed --json`: JSON with the flag, human-readable lines without — in BOTH dry-run and write paths

## Git-Log Analysis
- `get_commits_for_class(class, date, repo_filter=repos)` — always pass `repo_filter` to scope to candidate repos
- `resolve_class_folders_for_date(class, date)` — includes `_X/_Y/_Z` split variants AND February name-change variants
- `get_commit_diff(repo, hash, max_bytes=4000)` — full diff, truncated
- Class names may change in February: Abteilungsklassen (aif/cif/kif) advance year (3aaif→4aaif); Tagesklassen (hwii/hwit) stay same

## Testing
- `pytest tests/test_gitlog.py` — 8 tests covering split classes, February name change, ±10/±30 window, known examples
- Tests use real git repos (not mocked) — run from the repo with GRG-* repos present

## Privacy
- This repo is PUBLIC. No person data in any tracked file: no student or
  teacher names, no student IDs, no person-linked details — in any file
  (docs/ai/*, docs/*, code, tests, commit messages).
- Person data (names, student IDs) may be written ONLY to
  `docs/ai/LOCAL.md` (gitignored, local-only, NOT synced between
  machines) and ONLY on explicit user request.
- `HANDOFF.md`/`STATE.md` stay tracked but anonymized; person-specific
  entries point to LOCAL.md via `[Details: LOCAL.md]`.
- Allowed in tracked files: counts, lesson ids (lsId), class ids,
  period ids, subject names.
- Git history is never rewritten — exposure, once committed, stays.
  Be careful BEFORE writing.

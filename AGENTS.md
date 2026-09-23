# webuntis-agent

Reverse-engineering the WebUntis web API (as used by the WebUntis UI at
`https://spengergasse.webuntis.com/`) to automate the "Lehrstoff eintragen"
(lesson topic entry) action that the teacher otherwise performs manually
in the browser.

## CLI manual

The authoritative operator reference for the `./wu` CLI is `man/wu.1`
(groff man page, German) — read it with `man --local-file man/wu.1`
instead of assembling invocations from source code. It covers every
command, option, workflow, exit code, and pitfall — more than `--help`.
`tests/test_manpage.py` guards it against CLI drift; update both when
adding commands or flags.

## Context

This is a companion tool to the GRG-* teaching repositories under
`~/repos/georgernstgraf/`. The Lehrstoff is derived from the Git history of
those repositories (commits under top-level class folders, e.g.
`4bkif/2026-03-18_...`), and submitted to WebUntis via the reverse-engineered
endpoints.

See `~/AGENTS.md` for the full GRG-* repository list, class naming rules
(February class-name changes, split classes with `_X`/`_Y` suffix), and the
list of classes taught in 2025/26.

## WebUntis target

- Host: `https://spengergasse.webuntis.com/`
- School slug: `spengergasse` (used as `?school=spengergasse` on JSON-RPC,
  and as the Base64-encoded `schoolname` cookie value on REST endpoints).

## Reverse-engineering approach

The WebUntis Lehrstoff write endpoint is not part of the public JSON-RPC API
documented at
https://github.com/SafeMemoryZone/webuntis-api-docs/blob/master/WEBUNTIS_API.md
(which only covers read endpoints like `getTimetable`, `getSubjects`,
`getKlassen`, ...). It is written to by the web UI via internal REST or
JSON-RPC endpoints that we discover by recording the browser traffic while
the teacher performs the action manually.

The recorder attaches to a running Brave browser through the Chrome
DevTools Protocol (`--remote-debugging-port=9222`) and captures:

- `Network.requestWillBeSent` / `Network.responseReceived` /
  `Network.loadingFinished` for the WebUntis domain
- `Runtime.consoleAPICalled` / `Runtime.exceptionThrown` for all console
  output of the WebUntis page
- `Network.getAllCookies` at the end of a recording session, to harvest the
  `JSESSIONID` / `schoolname` cookies needed for replay

Output goes to `recordings/{timestamp}_network.jsonl` and
`recordings/{timestamp}_console.jsonl` (both gitignored).

## Running the recorder

1. Start Brave with the debug port:
   `scripts/brave-debug.sh`
2. In Brave, open `https://spengergasse.webuntis.com/` and log in.
3. Start the recorder: `python -m webuntis_agent.recorder`
4. Perform the "Lehrstoff eintragen" action in the WebUntis UI as usual.
5. Stop the recorder (Ctrl-C). Inspect `recordings/`.

## Session

The `recordings/` directory is gitignored because it contains session
cookies.

## Privacy

This repo is public. NEVER write person data (student/teacher names,
student IDs, person-linked details) into any tracked file — including
`docs/ai/HANDOFF.md` and `docs/ai/STATE.md`. On explicit user request
only, such details go to `docs/ai/LOCAL.md` (gitignored, local-only,
NOT synced between machines). Tracked files reference it via
`[Details: LOCAL.md]`. Counts, lesson ids, class ids and subject names
are allowed; person names and person ids are not.

## Knowledge Bootstrap

Before starting any task, read the following files in order:
1. `docs/ai/HANDOFF.md` — read first, act on it
2. `docs/ai/CONVENTIONS.md`
3. `docs/ai/DECISIONS.md`
4. `docs/ai/ARCHITECTURE.md`
5. `docs/ai/PITFALLS.md`
6. `docs/ai/STATE.md`
7. `docs/ai/DOMAIN.md` (if task involves business logic)
8. `docs/ai/HISTORY.md` (reference only — read last, as needed)

If `HANDOFF.md` contains open tasks, complete them before starting
any new work unless the user explicitly says otherwise.

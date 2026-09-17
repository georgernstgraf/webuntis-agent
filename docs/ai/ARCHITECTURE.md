# Architecture

Living structural map of the system as of 2026-09-17.
Overwritten when structural changes occur during a session.

## Overview

webuntis-agent is a Python CLI tool that reverse-engineers and automates
the WebUntis "Lehrstoff eintragen" (lesson topic entry) action. It
consists of a CDP recorder for endpoint discovery, an HTTP client for
API replay, a git-log analyzer for deriving topic text from GRG-*
teaching repos, and an opencode skill that orchestrates the full
fill-open-periods workflow with human confirmation.

## Components (`src/webuntis_agent/`)

| Module | Purpose |
|--------|---------|
| `recorder.py` | CDP-Recorder: attaches to Brave:9222, captures Network + Runtime events to recordings/*.jsonl |
| `client.py` | WebUntis HTTP client: login, JWT, REST/JSON-RPC endpoints, retry-with-backoff |
| `gitlog.py` | GRG-* git-log analysis: pull, class folder resolution (split/February), commit diffs |
| `cli.py` | CLI entry point: `lehrstoff *`, `lessons`, `search`, `students *`, `kv`, `absences *`, `record`, `login`/`logout`, `session status`, `lesson info`, generic `rpc`/`rest` passthrough |

## CLI Commands

| Command | Purpose |
|---------|---------|
| `login` / `logout` | persist/invalidate the cached session (`.webuntis_session.json`) |
| `session status [--json]` | cache age + live check via `app/data` (exit 2 = dead session) |
| `lehrstoff list --start --end [--json]` | List open periods (JSON includes lessonDetailsUrl) |
| `lessons <class> [--subject]` | List the user's lessons for one class, grouped by lsId |
| `search <text> [--fallback] [--all-years]` | Timetable search (exact default; tokenizing/multi-year opt-in) |
| `students find <name> [--class]` | Student search (tokenizing + auto-fallback, NICHT AKTUELL flagged) |
| `students list --lsid` | Attendance matrix dump |
| `students add` / `students edit` | Attendance writes (dry-run default) |
| `lehrstoff get --period <id>` | Show existing topic for a period |
| `lehrstoff set --period --text-file\|--text-stdin\|--text` | Write single topic |
| `lehrstoff batch-set --file <json> [--delay 1.0]` | Bulk write from JSON file |
| `lehrstoff from-git --class-name --subject --date [--dry-run]` | Derive text from git diffs |
| `lehrstoff status/fill/verify/fill-fixed` | Open-periods overview / batch builder / text check / fixed-text fill |
| `lesson info <lsid> [--json]` | Lesson diagnostics: teachers, klassen, mainStudentgroupId, roster vs. attending per klasse |
| `kv <class\|name>` / `kv --student <name>` | Klassenvorstand of a class or of a student's class(es) |
| `rpc <method> [params-json]` | Generic JSON-RPC passthrough (JSON output) |
| `rest <path> [--method] [--data-json]` | Generic REST passthrough to `/WebUntis/api/<path>` (write-capable, method+body echoed) |
| `absences check/batch-check/check-all` | Absenzenkontrolle |
| `record` | Run CDP recorder |

## `wu` Wrapper

Bash shortcut (tracked at repo root), symlink-fähig: `readlink -f`
auf `$BASH_SOURCE` → ROOT immer der Repo-Root, egal ob per Symlink
(z. B. `~/svn/georg/EDV/Toolset/wu`) aufgerufen. Interpreter:
bevorzugt `.venv/bin/python`, Fallback `python3` mit Import-Probe
(httpx/websockets, einzeln) + deutscher Setup-Anleitung
(Exit 1). `cli.main()` fängt zusätzlich ModuleNotFoundError (Exit 3)
für Direktaufrufe ohne `wu`.

## Skills (`.opencode/skills/`)

| Skill | Purpose |
|-------|---------|
| `fill-open-periods` | Orchestrates: list open periods → git-log + diffs → formulate texts → confirm → batch-set |

## Knowledge Files (`docs/ai/`)

| File | Purpose | Update mode |
|------|---------|------------|
| HANDOFF.md | Open tasks for next session | Overwrite |
| DECISIONS.md | Active decisions still in force | Append; prune → HISTORY.md |
| ARCHITECTURE.md | Living structural map | Overwrite |
| CONVENTIONS.md | Ongoing rules to follow | Append |
| PITFALLS.md | Hard-won failure knowledge | Append |
| DOMAIN.md | Business/domain rules | Append |
| STATE.md | Current project status | Overwrite |
| HISTORY.md | Superseded entries archive | Append-only |

## Data Flows

- **Reverse Engineering**: Brave (CDP:9222) → recorder.py → recordings/*.jsonl → analysis → docs/WEBUNTIS_API.md
- **Lehrstoff Entry**: .env (credentials) → client.login() → JWT → get_open_periods() → gitlog.get_commits_for_class() → agent formulates text → batch-set --file → WebUntis PUT
- **Git-Log Analysis**: GRG-* repos → pull_all_repos() → get_commits_for_class(class, date, repo_filter) → get_commit_diff() → agent reads diffs → German Lehrstoff text

## External Dependencies

- Brave Browser (with `--remote-debugging-port=9222`) — for RE only
- WebUntis API (`https://spengergasse.webuntis.com/`) — login + REST/JSON-RPC
- GRG-* git repos (`~/repos/georgernstgraf/GRG-*`) — lesson content source
- `pdftotext` — for GRG-POSTHEORIE PDF folien extraction

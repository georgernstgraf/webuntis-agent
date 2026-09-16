# Architecture

Living structural map of the system as of 2026-08-22.
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
| `cli.py` | CLI entry point: `lehrstoff list/get/set/batch-set/from-git`, `record` |

## CLI Commands

| Command | Purpose |
|---------|---------|
| `lehrstoff list --start --end [--json]` | List open periods (JSON includes lessonDetailsUrl) |
| `search <text> [--fallback] [--all-years]` | Timetable search (exact default; tokenizing/multi-year opt-in) |
| `students find <name> [--class]` | Student search (tokenizing + auto-fallback, NICHT AKTUELL flagged) |
| `lehrstoff get --period <id>` | Show existing topic for a period |
| `lehrstoff set --period --text-file\|--text-stdin\|--text` | Write single topic |
| `lehrstoff batch-set --file <json> [--delay 1.0]` | Bulk write from JSON file |
| `lehrstoff from-git --class-name --subject --date [--dry-run]` | Derive text from git diffs |
| `record` | Run CDP recorder |

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

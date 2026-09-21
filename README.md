# webuntis-agent

Automate the **Lehrstoff eintragen** (lesson topic entry) and **Absenzen
prüfen** (absence check) chores in [WebUntis] by reverse-engineering the
undocumented REST endpoints that the web UI calls — then replaying them from a
Python CLI.

Built for Georg Graf's teaching at [HTL Spengergasse] (Vienna). Lesson topics are
derived automatically from the Git history of the [GRG-*] teaching repositories,
so the agent fills in what was actually taught based on commits, diffs, and
README entries — no manual typing required.

> ⚠️ This is a **reverse-engineering** project. The write endpoints for lesson
> topics and absence checks are **not part of the public WebUntis JSON-RPC API**.
> They were discovered by recording browser traffic via the Chrome DevTools
> Protocol. See [`docs/WEBUNTIS_API.md`](docs/WEBUNTIS_API.md) for the full
> endpoint reference.

---

## Features

- **CDP-Recorder** — attaches to a running Brave browser via
  `--remote-debugging-port=9222` and captures all Network requests, response
  bodies, and console output for the WebUntis domain into structured JSONL
  files. No F12 or cURL copying needed.
- **WebUntis Client** — logs in, obtains JWT, and replays the discovered
  endpoints: lesson topics (GET/PUT), open periods, schoolyears, and absence
  checks (CSRF-protected POST). All dynamic values (teacherId, Tenant-Id,
  School-Year-Id) are derived at runtime from the JWT — no hardcoded constants.
- **Git-Log Analyzer** — scans the GRG-* teaching repos to find what was
  taught on a given date: handles split classes (`_X`/`_Y` groups), February
  class-name changes (`3aaif` → `4aaif`), ±10/±30-day commit windows, and
  full commit diffs.
- **Fill-Open-Periods Skill** — an [opencode] skill that orchestrates the
  full workflow: fetch open periods → derive topic text from git diffs →
  present a confirmation table → batch-submit via the CLI.
- **Retry-with-Backoff** — survives transient IP rate-limiting (TCP resets)
  from the WebUntis server after rapid API calls.

---

## Quick Start

### Prerequisites

- Python 3.11+
- A Brave (or Chromium) browser
- GRG-* teaching repos under `~/repos/georgernstgraf/GRG-*`
- A WebUntis account with teacher access

### Install

```bash
cd ~/repos/georgernstgraf/webuntis-agent
python3 -m venv .venv
.venv/bin/pip install -e .
```

### Configure

```bash
cp .env.example .env
# Edit .env and fill in your WebUntis credentials:
#   user=grafg
#   password=<your-password>
#   school=spengergasse
#   host=https://spengergasse.webuntis.com
```

---

## Verwendung

Kurzbefehl: `./wu …` — z.B. `./wu search "Erika Muster"`.
Er setzt `PYTHONPATH=src` und reicht an `webuntis_agent.cli` durch.

Domain-Objekte: **Klasse** (`wu klasse 3AHWII`), **Lesson** als
`KLASSE/FACH` (`wu lesson 3AHWII/SWP1x`), **Student**
(`wu student "Erika Muster"`). Alle Ausgaben sind deutsch;
`wu --help` (und jede Gruppen-Hilfe) erklärt mit Beispielen.

### Offene Perioden (Arbeitsvorrat: Lehrstoff oder Absenzen fehlen)

```bash
./wu offen status --von 2025-09-01 --bis 2026-07-05
./wu offen liste --von 2025-09-01 --bis 2026-07-05 --json
```

### Klasse und Lesson

```bash
./wu klasse 3AHWII                    # KV, Fächer, Roster
./wu lesson 3AHWII/SWP1x              # Roster des nächsten Termins
./wu lesson 3AHWII/SWP1x termine --mit-lehrstoff
./wu lesson 3AHWII/SWP1x absenzen zeigen
./wu student "Erika Muster"           # Klasse, KV, Fächer, Absenzen
```

### Einzelnen Lehrstoff schreiben

```bash
./wu lesson 3AHWII/SWP1x lehrstoff zeigen --termin-id 5458590
./wu lesson 3AHWII/SWP1x lehrstoff eintragen \
    --termin-id 5458590 --text-datei /tmp/topic.txt
```

(`--text-datei` statt `--text "…"` verwenden — die Shell verstümmelt
Umlaute wie `HÜ`, `ä`, `ö`.)

### Lehrstoffe aus Git-Historie vorschlagen + batchweise eintragen

```bash
./wu offen vorschlag --von 2025-09-01 --bis 2026-07-05 > vorschlag.json
# Texte prüfen/bestätigen, dann:
./wu offen eintragen --datei batch.json --pause 1.0
```

Vorschlags-JSON-Format je Block: `periodId`, `topicId`, `text`,
`classId`, `start`, `end`, `date` (+ `commits`/`diffs` als Quelle).

### Lehrstoff-Text aus Git-Historie ableiten (einzeln)

```bash
./wu lesson 5AHWII/SWP1y lehrstoff aus-git --datum 2026-03-18
```

Sucht in den GRG-*-Repos nach Commits zu Klasse+Datum (±10 Tage,
±30 Fallback), zeigt Commits + Diffs und schlägt einen Text vor.
Mit `--ausfuehren` (+ `--termin-id`/`--thema-id`) direkt eintragen.

### Absenzen prüfen

Einzelner Termin oder ganze Lesson:

```bash
./wu lesson 3AHWII/SWP1x absenzen pruefen --termin-id 5457498
./wu offen pruefen --von 2025-09-01 --bis 2026-07-05 --pause 1.5
```

### Migration (alte → neue Befehle, Stand 2026-09-21)

Harter Schnitt ohne Aliase. Entsprechungstabelle:

| alt | neu |
|---|---|
| `students roster KLASSE FACH` | `lesson KLASSE/FACH [roster]` |
| `students list --lsid X` | `lesson --lsid X matrix` |
| `students add/edit …` | `lesson KLASSE/FACH aufnehmen/anpassen …` |
| `students find NAME` | `student NAME` |
| `lessons KLASSE` | `klasse KLASSE faecher` |
| `lesson info LSID` | `lesson --lsid LSID info` / `lesson KLASSE/FACH info` |
| `lehrstoff list/status/verify` | `offen liste/status/verifizieren` |
| `lehrstoff fill` (Vorschlag) | `offen vorschlag` |
| `lehrstoff batch-set --file` | `offen eintragen --datei` |
| `lehrstoff fill-fixed` | `offen festtexte` |
| `lehrstoff get/set/from-git` | `lesson KLASSE/FACH lehrstoff zeigen/eintragen/aus-git` |
| `absences check-all/batch-check` | `offen pruefen` |
| `absences check --period` | `lesson KLASSE/FACH absenzen pruefen --termin-id` |
| `kv KLASSE` / `kv --student` | `klasse KLASSE kv` / `student NAME` |
| `login/logout/session/record/rpc/rest` | `intern …` (aus der Hilfe versteckt) |

Flag-Umbenennungen: `--school-year-id` → `--schuljahr-id`,
`--start/--end` → `--von/--bis`, `--dry-run/--no-dry-run` →
`--testlauf/--ausfuehren`, `--date` → `--datum` (`heute` statt `now`),
`--text-file` → `--text-datei`, `--file` → `--datei`,
`--delay` → `--pause`, `--class-id` → `--klassen-id`,
`--period` → `--termin-id`, `--topic-id` → `--thema-id`.
JSON-Schlüssel bleiben englisch.

### Reverse-engineer new endpoints (CDP-Recorder)

1. Start Brave with the debug port:

   ```bash
   scripts/brave-debug.sh
   ```

2. In Brave, open WebUntis and log in.

3. Start the recorder:

   ```bash
   .venv/bin/python -m webuntis_agent.recorder
   ```

4. Perform the action you want to capture (e.g. enter a lesson topic, check
   absences) in the WebUntis UI as usual.

5. Stop the recorder (Ctrl-C). Inspect `recordings/` for the captured
   requests, response bodies, and cookies.

---

## How It Works

### Reverse-Engineering Workflow

```
Brave (CDP :9222)
  └── recorder.py captures Network + Runtime events
       └── recordings/*.jsonl (requests, responses, cookies)
            └── analysis → docs/WEBUNTIS_API.md
                 └── client.py replays the endpoints
```

The recorder attaches to Brave via the Chrome DevTools Protocol and
subscribes to `Network.*` and `Runtime.*` events. It captures:

- `Network.requestWillBeSent` — URL, method, headers, POST body
- `Network.responseReceived` — status, headers, MIME type
- `Network.getResponseBody` — full response body (after `loadingFinished`)
- `Runtime.consoleAPICalled` — all `console.log/error/warn` output
- `Network.getAllCookies` — session cookies (harvested at session end)

Output goes to `recordings/{timestamp}_network.jsonl`,
`recordings/{timestamp}_console.jsonl`, and `recordings/{timestamp}_cookies.json`
(all gitignored — they contain session cookies).

### Fill-Open-Periods Workflow

```
.env (credentials)
  └── client.login() → JSESSIONID + schoolname cookies
       └── client.get_jwt() → Bearer JWT (person_id, tenant_id)
            └── client.get_open_periods() → list of owed lessons
                 └── gitlog.get_commits_for_class() → matching commits
                      └── gitlog.get_commit_diff() → full diffs
                           └── agent formulates German topic text
                                └── user confirms → batch-set → WebUntis PUT
```

### Subject → Repository Mapping

The agent maps WebUntis subject short names to candidate GRG-* repos by
prefix matching (so `SWP1x`, `SWP1y`, `SWP1` all match `SWP`):

| WebUntis subject | GRG repos |
|---|---|
| `POS1` / `POS` | GRG-POSTHEORIE, GRG-JAVA |
| `SWP1x` / `SWP1y` / `SWP` | GRG-SWP, GRG-CS |
| `WMC_1` / `WMC` | GRG-WMC |
| `INFIx` / `INF` | GRG-INFI |
| `CS` | GRG-CS |
| `SS` | _(fixed text: "Sprechstunde")_ |
| `BESP` | _(fixed text: "Bewegung und Sport")_ |

Unknown subjects trigger a warning so the mapping can be extended. See
`SUBJECT_REPO_MAP` in [`src/webuntis_agent/client.py`](src/webuntis_agent/client.py).

---

## Project Layout

```
webuntis-agent/
├── src/webuntis_agent/
│   ├── recorder.py       # CDP-Recorder: Network + Runtime → recordings/
│   ├── client.py         # WebUntis API client (login, JWT, REST, absences)
│   ├── gitlog.py         # GRG-* git-log analysis (split classes, diffs)
│   ├── cli.py            # CLI-Verdrahtung: klasse/lesson/student/offen/…
│   ├── cli_common.py     # geteilte Infra (Session, Period-Helpers, Suche)
│   ├── cli_klasse.py     # klasse: Übersicht, Roster, Fächer, KV
│   ├── cli_lesson.py     # lesson: Roster, Termine, Lehrstoff, Absenzen
│   ├── cli_student.py    # student: Suche + Detail (Fächer, Absenzen)
│   ├── cli_offen.py      # offen: Arbeitsvorrat (Vorschlag, Eintragen, Prüfen)
│   ├── cli_suche.py      # search: Suche mit Detail-Dispatch
│   └── cli_intern.py     # intern: Session, Recorder, rpc/rest (versteckt)
├── scripts/
│   ├── brave-debug.sh     # start Brave with --remote-debugging-port=9222
│   └── show-cookies.py    # inspect harvested cookies
├── tests/                 # pytest-Suite (Fake-Clients, keine Netz-Calls)
├── docs/
│   ├── WEBUNTIS_API.md    # authoritative endpoint reference
│   └── ai/                # knowledge persistence (DECISIONS, PITFALLS, …)
├── .opencode/skills/
│   └── fill-open-periods/SKILL.md  # opencode skill for the full workflow
├── .env.example          # template for credentials (copy to .env)
├── .gitignore            # ignores .env, .venv, recordings/, *.jsonl
├── AGENTS.md             # agent instructions + knowledge bootstrap
└── pyproject.toml        # Python package config
```

---

## Key Design Decisions

- **No hardcoded constants** — teacherId, Tenant-Id, and School-Year-Id are
  all derived at runtime from the JWT and REST API.
- **Python + httpx for replay** (not Playwright) — once endpoints are known,
  pure HTTP calls suffice; no browser needed for normal operation.
- **Skill-based architecture** — an opencode skill orchestrates the CLI
  calls; the agent (LLM) holds git-log context in memory and formulates
  topic texts from diffs with human confirmation before submission.
- **±10/±30-day git-log window** — catches commits made shortly after the
  lesson, with a wider fallback for longer delays.

See [`docs/ai/DECISIONS.md`](docs/ai/DECISIONS.md) for the full list.

---

## License

Private project. Not for redistribution.

[WebUntis]: https://www.untis.at/de/produkte/webuntis-die-online-erweiterung
[HTL Spengergasse]: https://www.spengergasse.at
[GRG-*]: https://github.com/georgernstgraf?tab=repositories&q=GRG
[opencode]: https://opencode.ai

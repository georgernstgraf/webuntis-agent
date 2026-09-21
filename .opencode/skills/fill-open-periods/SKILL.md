---
name: fill-open-periods
description: Fill missing WebUntis lesson topics (Lehrstoff) for open periods using GRG-* git history and the webuntis-agent CLI. Use when the user wants to catch up on missing Lehrstoff entries.
---

# fill-open-periods

Automate the "Lehrstoff nachtragen" chore: list WebUntis open periods,
derive a topic text from the corresponding GRG-* teaching repository's
git history, and submit each via the webuntis-agent CLI.

## Prerequisites

- The `webuntis-agent` repo is checked out at
  `~/repos/georgernstgraf/webuntis-agent` with a working `.venv`.
- `.env` is present with `WEBUNTIS_USER` / `WEBUNTIS_PASSWORD` (see
  `.env.example`).
- All GRG-* repos under `~/repos/georgernstgraf/` are pullable.

## Workflow

1. **Run `offen vorschlag`** to fetch all open periods and
   pre-load git commits + diffs in one call:

   ```bash
   cd ~/repos/georgernstgraf/webuntis-agent
   .venv/bin/python -m webuntis_agent.cli offen vorschlag \
       --von 2025-09-01 --bis 2026-07-05
   ```

   This outputs a JSON object with two arrays:

   - `blocks`: one entry per day-block (class + subject + date), each with:
     - `periodId`, `topicId`, `class`, `classId`, `subject`, `date`, `time`
     - `start`, `end` (block ISO timestamps for `lessonDetailsUrl`)
     - `blockPeriods`: list of all periodIds in the block
     - `source`: `"git"` | `"fixed"` | `"dummy"` | `"skipped"`
     - `proposedText`: raw text from commit messages (refine this!)
     - `commits`: array of `{repo, hash, date, message, files[], diff}` per commit

   - `skipped`: periods with unknown subjects (no repo mapping)

   Fixed-text subjects (SS="Sprechstunde", BESP="Bewegung und Sport") are
   already filled with their text — no formulation needed.

2. **Formulate the Lehrstoff text** for each block from:
   - The commit `diff` fields (what was added/changed — e.g. a Prisma
     schema, a regex exercise, a Deno project skeleton).
   - The `files` arrays (subject-area hint, e.g. `Matura-Prisma.md`).
   - The `subject` and `subjectLong` (e.g. `SWP1y` = Softwareentwicklung
     und Projektmanagement, Y-Gruppe) and the `date`.
   - Keep it concise and factual (German, e.g. "Prisma-Schema für
     Matura-Projekt; Deno-Setup; VSCode-Konfiguration" rather than
     raw commit messages like "std; fast commit").
   - The `proposedText` is a rough starting point — improve it.
   - For block periods (same `lsId`), use the same text — one PUT
     updates the whole block.

3. **Present a confirmation table** to the user:

   | periodId | class | subject | date | proposed text |
   |---|---|---|---|---|

   List skipped periods (unknown subjects) at the bottom.

4. **On user confirmation** (bulk "all ok" or per-row edits), write a
   JSON file with the confirmed entries:

   ```json
   [
     {"periodId": 5458590, "topicId": 2296724, "text": "...",
      "classId": 3661, "start": "2026-03-18T13:25:00",
      "end": "2026-03-18T15:15:00", "date": "2026-03-16"},
     ...
   ]
   ```

   Write it to `/tmp/opencode/batch_<timestamp>.json`.

5. **Submit** all entries:

   ```bash
   .venv/bin/python -m webuntis_agent.cli offen eintragen \
       --datei /tmp/opencode/batch_<timestamp>.json --pause 1.0
   ```

   - One PUT per entry; block partners are auto-updated by the server.
   - `--pause 1.0` avoids triggering IP rate-limiting.
   - `topicId` null → server creates new topic (id=0).
   - `classId`/`start`/`end`/`date` enable `lessonDetailsUrl` output.

6. **Check absences** for all remaining open periods:

   ```bash
   .venv/bin/python -m webuntis_agent.cli offen pruefen \
       --von 2025-09-01 --bis 2026-07-05 --pause 1.5
   ```

7. **Report** which periods were submitted, failed, or skipped. Include
   `lessonDetailsUrl` from the `batch-set` output for browser verification.
   Add new subjects to `SUBJECT_REPO_MAP` when the user confirms the repo.

## Helper commands

- `offen status --von ... --bis ...` — quick overview (by subject/class)
- `offen verifizieren --von ... --bis ...` — check which periods truly
  have no text vs only missing absence check
- `offen festtexte --von ... --bis ...` — fill SS/BESP only
  (no git-log needed)

## Notes

- The `vorschlag` call replaces the old manual workflow
  (`liste --json` + per-block git lookup). One call does it all.
- Block periods (same `lsId`) only need one PUT.
- The `.env` file is gitignored and contains the WebUntis password —
  never print it or commit it.
- `recordings/` contains session cookies — treat as sensitive.

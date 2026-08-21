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

1. **Fetch open periods as JSON** for the current schoolyear (default
   since Sep 1 of last year to Jul 5 of this year; adjust on request):

   ```bash
   cd ~/repos/georgernstgraf/webuntis-agent
   .venv/bin/python -m webuntis_agent.cli lehrstoff list \
       --start 2025-09-01 --end 2026-07-05 --json
   ```

2. **Inspect the JSON.** Each entry has:
   `periodId`, `topicId`, `class`, `subject` (short name like `SWP1y`,
   `POS1`, ...), `date`, `time`, `lsId`.

3. **Resolve candidate repos** for each period's `subject` using the
   `SUBJECT_REPO_MAP` in `src/webuntis_agent/client.py`. If the subject
   is unknown (not in the map):
   - Warn the user: "Subject `<X>` is not mapped — add it to
     `SUBJECT_REPO_MAP` in `src/webuntis_agent/client.py`."
   - Collect it in a "skipped" list for the final report.
   - Skip that period.

4. **For each remaining period**, run the git-log + diff fetch via the
   CLI dry-run to see commits and diffs for that class/date/subject:

   ```bash
   .venv/bin/python -m webuntis_agent.cli lehrstoff from-git \
       --class-name <class> --subject <short> --date <yyyy-MM-dd> \
       --dry-run
   ```

   This prints the matching commits (across the candidate repos only),
   followed by the full `git show` diff of each commit (truncated to
   4000 bytes per commit). Read the diffs — they contain the actual
   taught content (file contents, new functions, schema definitions,
   exercise texts, etc.), not just commit messages.

5. **Formulate the Lehrstoff text** for each period from:
   - The commit diffs (what was added/changed — e.g. a Prisma schema,
     a regex exercise, a Deno project skeleton).
   - The file paths (subject-area hint, e.g. `5ahwii_Y/Matura-Prisma.md`).
   - The WebUntis subject (e.g. `SWP1y` = Softwareentwicklung und
     Projektmanagement, Y-Gruppe) and the date.
   - Keep it concise and factual (German, e.g. "Prisma-Schema für
     Matura-Projekt; Deno-Setup; VSCode-Konfiguration" rather than
     raw commit messages like "std; fast commit").
   - For block periods (same `lsId`), use the same text — one PUT
     updates the whole block, so duplicate entries are fine.

6. **Present a confirmation table** to the user:

   | periodId | class | subject | date | proposed text |
   |---|---|---|---|---|

   Group block periods (same `lsId`) together. List skipped periods
   (unknown subjects) at the bottom.

7. **On user confirmation** (bulk "all ok" or per-row edits), write a
   JSON file with the confirmed entries:

   ```json
   [
     {"periodId": 5458590, "topicId": 2296724, "text": "Matura-Aufgabe Datenmodellierung: Prisma-Schema, SQLite-DDL/-DML, Seed-Script"},
     ...
   ]
   ```

   Write it to `/tmp/opencode/batch_<timestamp>.json` (or another
   gitignored location — never inside the repo, to avoid accidental
   commits of lesson content).

   Then submit all entries in one call:

   ```bash
   .venv/bin/python -m webuntis_agent.cli lehrstoff batch-set \
       --file /tmp/opencode/batch_<timestamp>.json
   ```

   - One PUT per entry; block partners are auto-updated by the server.
   - Use `--text-file` (or `batch-set` with a JSON file) instead of
     `--text "..."` to avoid shell-quoting issues with UTF-8 (Umlaute
     like HÜ, ä, ö, ü get mangled when passed via `--text` in bash).
   - If `topicId` is in the list output, include it; otherwise omit it
     and `batch-set` will resolve it via `getLessonTopic`.

8. **Report** which periods were submitted successfully, which failed,
   and which were skipped (unknown subjects). Add new subjects to
   `SUBJECT_REPO_MAP` when the user confirms what repo they belong to.
   For each successfully submitted period, include the
   `lessonDetailsUrl` from the `batch-set` output — the user can click
   it to verify the entry in the browser (it shows under "Lehrstoff").

   The `batch-set` JSON file should contain `classId`, `start`, `end`,
   `date` alongside `periodId`, `topicId`, `text` for each entry so
   that the URLs are emitted in the result. Use the values from the
   `lehrstoff list --json` output (`classId`, `_start_iso`/`_end_iso`
   block bounds, `date`).

## Notes

- The git-log scan is cheap (`git log` over ±10 days with a ±30-day
  fallback) and scoped to 2-4 candidate repos per subject, so O(N)
  over open periods is acceptable — no caching layer required.
- Block periods (same `lsId`) only need one PUT; the WebUntis server
  returns all updated topics in the block response.
- The `.env` file is gitignored and contains the WebUntis password —
  never print it or commit it.
- `recordings/` contains session cookies and (for the login recording)
  the plaintext password — treat as sensitive, delete after analysis.

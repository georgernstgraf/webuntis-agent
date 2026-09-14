# Project State

Current status as of 2026-08-22.

## Current Focus
All 418 open periods for school year 2025/26 are now closed — every period has both a lesson topic (Lehrstoff) and absence check (Absenzenkontrolle).

## Completed (this cycle)
- [x] CDP-Recorder built and tested (3 recording sessions)
- [x] WebUntis API reverse-engineered: login, JWT, open-periods, lesson-topics (GET/PUT), absences (CSRF + POST)
- [x] Client (client.py): login, JWT decode, schoolyear resolution, all endpoints with retry-backoff
- [x] CLI (cli.py): list (--json + lessonDetailsUrl), get, set, batch-set, from-git, absences check/batch-check/check-all
- [x] Git-Log analyzer (gitlog.py): pull, split-class folders, February name change, ±10/±30 window, commit diffs, case-insensitive
- [x] Subject→Repo mapping with prefix matching + GRG-CS for SWP
- [x] Fixed-text subjects (SS="Sprechstunde", BESP="Bewegung und Sport")
- [x] Skill `fill-open-periods` created and tested
- [x] 196 Lehrstoff day-blocks entered (10 monthly sub-agent batches)
- [x] 35 remaining periods entered (32 SS + 1 BESP + 2 late fixes)
- [x] All 418 absence checks completed (check-all batch)
- [x] UTF-8 fix: batch-set with JSON file
- [x] id=0 for new topic creation
- [x] Retry-with-backoff for TCP reset rate-limiting
- [x] Case-sensitivity fix in gitlog.py (lowercase + uppercase variants)
- [x] Knowledge persisted to docs/ai/

## Pending
- [ ] Commit all work to git (user has not requested yet)
- [ ] Login flow for fully autonomous operation (currently needs .env)

## Blockers
- None

## Next Session Suggestion
1. Commit all work: `git add -A && git commit -m "Initial implementation: CDP recorder, WebUntis client, git-log analyzer, fill-open-periods skill, absences check"`
2. Clean up recordings/ directory (contains session cookies + plaintext password)
3. Consider login flow for autonomous operation (OTP/secret or password-based)
4. Next school year: run `fill-open-periods` skill again for 2026/27

## New Feature In Progress: Student-Aufnahme (2026-08-22+)
- Goal: add student Mhd Badawi Nour (currently 5BAIF, classId 4137) to
  Georg's 3BAIF lessons (classId 4107) — POS1 lsId=215940 and/or WMC_1
  lsId=218839 in schoolyear 24.
- Phase 1 done: API surface extracted from SPA bundles (253 routes) →
  docs/WEBUNTIS_API.md "Discovered API Surface".
- Phase 2 mostly done: lesson participant mask found
  (lessonstudentlist.do), legacy iframe app mapped, student ids of 3BAIF
  extracted (17 students). Badawi Nour's studentId still unknown.
- Next: fetch StudentLessonPeriodMatrixPage.js from Dojo CDN to find the
  add-student write endpoint; then one recorder run by user (Phase 3);
  then implement (Phase 4).

# Project State

Current status as of 2026-08-22 (evening).

## Current Focus
New feature "Schüler-Aufnahme" (student lesson attendance) — API fully
reverse-engineered and implemented, write pending user confirmation.
Open question: which of the two Badawi brothers was meant.

## Completed (this cycle)
- [x] School year 2025/26 fully closed: 418 periods Lehrstoff + Absenzen
- [x] Case-sensitivity fix, GRG-CS→SWP mapping, SS/BESP fixed texts
- [x] lehrstoff status/fill/verify/fill-fixed CLI commands (replace heredoc python)
- [x] Code review fixes (topic=None crash, dead code, imports, context manager)
- [x] English README, repo made public, all commits pushed to GitHub
- [x] Phase 1: API surface extracted from SPA bundles (253 routes) → docs
- [x] Phase 2: legacy class-register iframe app mapped; participant mask
      found (lessonstudentlist.do); matrix read-call validated end-to-end
      (CSRF → setSchoolyear → jsonStudentgroupService)
- [x] students add CLI (dry-run default) implemented, payload export works
- [x] Verification: manually added student in POS1 is "Al Badawi Mahmoud"
      (19261) — NOT the requested "Badawi Mhd Nour" (19405)

## Pending
- [ ] User confirms which Badawi brother is the correct student
- [ ] First real write via submitStudentLessonPeriodData (validation)
- [ ] WMC_1 enrollment after clarification

## Blockers
- None (write blocked only by user confirmation)

## Next Session Suggestion
1. Resolve the Badawi brother question (see HANDOFF.md)
2. Execute/validate the first write, verify in browser
3. Enroll in WMC_1 if requested

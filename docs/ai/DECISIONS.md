# Decisions

Active architectural and technical decisions still in force.
Superseded decisions are relocated to HISTORY.md.

## 2025-08-21: CDP-Recorder as primary RE tool
- **Choice**: Use Chrome DevTools Protocol (CDP) via WebSocket to capture Network + Runtime events from a running Brave browser
- **Reason**: `--enable-logging --v=1` only captures Chromium-internal logs, not WebApp console.log. CDP `Runtime.consoleAPICalled` captures all JS console output. CDP `Network.*` captures all HTTP requests with bodies.
- **Considered**: Browser extension, page-script injection, manual F12 copying
- **Tradeoff**: Brave must run with `--remote-debugging-port=9222`

## 2025-08-21: Python + httpx as client stack (not Playwright for replay)
- **Choice**: Use httpx for API replay, Playwright/CDP only for recording
- **Reason**: Once endpoints are known, pure HTTP calls suffice. No browser needed for normal operation.
- **Considered**: Playwright for both recording and replay
- **Tradeoff**: Session cookies must be obtained via login (`.env`) or harvested from browser

## 2025-08-21: No hardcoded constants — all dynamic from JWT/session
- **Choice**: teacherId, Tenant-Id, School-Year-Id all derived at runtime
- **Reason**: User explicitly required no hardcoded constants. JWT contains `person_id` (teacherId) and `tenant_id`. Schoolyears come from REST API.
- **Considered**: Hardcoding 514/7046800/21
- **Tradeoff**: One extra API call for schoolyears, JWT decode needed

## 2025-08-21: Subject→Repo mapping by prefix, not exact match
- **Choice**: `SUBJECT_REPO_MAP` matched by prefix (e.g. "SWP" matches SWP1x, SWP1y, SWP1)
- **Reason**: WebUntis subject short names vary by group (SWP1x, SWP1y, WMC_1, INFIx, POS1, POS2)
- **Considered**: Exact match per variant
- **Tradeoff**: Must verify no false prefix matches (e.g. "INF" matches "INFI" but also "INFO" if it existed)

## 2025-08-21: batch-set with JSON file instead of --text CLI arg
- **Choice**: `lehrstoff batch-set --file <json>` for bulk entries; `--text-file`/`--text-stdin` for single
- **Reason**: Shell quoting mangles UTF-8 (Umlaute: "HÜ" became "HUe" in bash array)
- **Considered**: `--text` only
- **Tradeoff**: Extra temp file, but UTF-8 safe

## 2025-08-21: id=0 for new topic creation
- **Choice**: When topicId is None (no existing topic row), send `id: 0` in PUT body
- **Reason**: WebUntis server creates a new topic row when id=0. Discovered by testing.
- **Considered**: Omitting id field, using null
- **Tradeoff**: None known

## 2025-08-21: ±10 day git-log window with ±30 fallback
- **Choice**: Default ±10 days around lesson date, fallback ±30 if empty
- **Reason**: User sometimes commits days/weeks after the lesson. ±10 catches most, ±30 catches longer delays.
- **Considered**: ±10 only, ±30 only, whole schoolyear
- **Tradeoff**: ±30 may catch unrelated commits from adjacent lessons

## 2025-08-21: Skill-based architecture (not batch script or MCP server)
- **Choice**: opencode Skill `fill-open-periods` orchestrates CLI calls
- **Reason**: Agent (LLM) holds git-log context in memory, formulates good texts from diffs, human confirms. No separate LLM API needed.
- **Considered**: Autonomous batch script with local LLM, MCP server with tool calls
- **Tradeoff**: Interactive (not unattended), token cost for agent context

## 2025-08-21: Retry-with-backoff for transient TCP resets
- **Choice**: `_request_with_retry` wraps all httpx calls with 3 retries, exponential backoff
- **Reason**: WebUntis server rate-limits by IP after many API calls (TCP reset, not HTTP 429)
- **Considered**: No retry, curl_cffi for TLS fingerprinting
- **Tradeoff**: Adds latency on failures; curl_cffi installed as backup but not used (issue was IP-based, not TLS-fingerprint)

## 2026-09-16: Person data policy — anonymized tracked files, LOCAL.md on user request
- **Choice**: Keep `HANDOFF.md`/`STATE.md` tracked but anonymized; introduce gitignored `docs/ai/LOCAL.md` as the only file where agents may write student names/IDs, and only on explicit user request
- **Reason**: Repo is public; past exposures of student names/IDs accepted as uncritical, but no new person data may be committed. No git-history rewrite.
- **Considered**: Untracking HANDOFF/STATE entirely; full history rewrite (filter-repo)
- **Tradeoff**: Old person data remains in git history (accepted); agents must actively route person data to LOCAL.md

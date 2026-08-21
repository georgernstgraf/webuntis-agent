# Pitfalls

Things that do not work, subtle bugs, and non-obvious constraints.
Read this file carefully before making changes in affected areas.

## API / WebUntis

- **TCP reset after many API calls**: WebUntis rate-limits by IP on TCP level (not HTTP 429). After ~50 rapid calls, new connections get reset. Solution: `--delay 1.0` between PUTs, retry-with-backoff in client. Blockade clears after ~30-60 seconds.
- **Login response is 302, not 200**: `j_spring_security_check` returns 302 on success, 200 on failure (back to login page). `follow_redirects=False` required.
- **httpx cookie iteration**: `self.http.cookies` yields strings, not Cookie objects. Use `self.http.cookies.jar` to get Cookie objects with `.name`/`.value`.
- **topicId can be None**: Some periods have no existing topic row (`topic: null` in getLessonTopic response). Send `id: 0` in PUT to create new.
- **Block auto-update**: One PUT updates ALL periods with the same `lsId` (lesson block). Don't send separate PUTs for block partners.
- **JWT expiry ~15 min**: Must refresh before each batch. Client caches JWT and refreshes 60s before expiry.
- **School-Year-Id**: Not constant. Derive from `getSchoolyears()` REST endpoint (matches date range) or fallback `current_year - 2005`. Override with `--school-year-id`.

## Git-Log Analysis

- **Class name case sensitivity**: WebUntis returns UPPERCASE class names (`5AHWII`), but git folders are lowercase (`5ahwii/`). Always `.lower()` before git pathspec.
- **Folder name `3HWII` vs `3AHWII`**: GRG-SWP has a `3HWII/` folder (next year's planning) that is NOT the same as `3ahwii/` (current year's class). The `3ahwii` SWP content is actually in GRG-CS (C# OOP), not GRG-SWP.
- **POS-Theorie has no per-lesson commits**: GRG-POSTHEORIE uses PDF folien (Folien_WS/Folien_SS), not dated folders. Derive topics from folien sequence + README + parallel classes.
- **3BAIF POS1 has no repo**: 3baif is not in any GRG-* repo. Derive from parallel classes (4baif, 6acif in GRG-POSTHEORIE) or PDF folien.
- **February name change boundary**: For dates near February, search BOTH pre- and post-change folder names (e.g. both `3aaif/` and `4aaif/`).
- **Split class folders**: `5ahwii_X/` and `5ahwii_Y/` — must search all `_X/_Y/_Z` variants, not just `5ahwii/`.

## CLI / Shell

- **UTF-8 in --text arg**: Bash mangles Umlaute ("HÜ" → "HUe") when passing via `--text "..."`. Use `--text-file <path>` or `batch-set --file <json>` instead.
- **.env key names**: `.env` may use short keys (`user`, `password`) or full keys (`WEBUNTIS_USER`). `_load_env()` maps short→full via aliases dict.

## Recorder

- **Response body capture**: `Network.getResponseBody` must be called AFTER `Network.loadingFinished` (not after `responseReceived`). The body isn't available until loading completes.
- **No console output file**: If the page doesn't use `console.*`, no `_console.jsonl` is created. This is normal, not a bug.
- **Brave must be started with debug port**: `scripts/brave-debug.sh` starts Brave with `--remote-debugging-port=9222`. If Brave is already running without the port, the recorder can't attach.

## Absences

- **CSRF token required**: The absence-check POST needs a `_csrf` token that must be fetched per-period from `GET classregpage.do` (HTML hidden field). Cannot be reused across periods.
- **No JWT for absences**: The `classregpage.do` endpoint uses session cookie + CSRF, not Bearer JWT. Different from the lesson-topic REST endpoints.
- **Block partner auto-marked**: One POST marks both periods in the block (response contains `args:[[periodId, blockPartnerId]]`).
- **X-CSRF-TOKEN header + _csrf body**: Both must carry the same token value. Missing either one causes a 403.

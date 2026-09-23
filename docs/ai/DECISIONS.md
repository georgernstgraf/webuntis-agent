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

## 2025-08-21: JSON-Datei statt --text-Flag für Bulk-Einträge
- **Choice**: `offen eintragen --datei <json>` für Bulk; `--text-datei`/`--text-stdin` für einzeln
- **Reason**: Shell-Quoting zerstört UTF-8 (Umlaute: "HÜ" wurde "HUe")
- **Considered**: nur `--text`
- **Tradeoff**: extra Temp-Datei, dafür UTF-8-sicher

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

## 2026-09-17: `cookies` command removed — browser-harvest kept as manual escape hatch
- **Choice**: Remove the `cookies` TODO-stub command entirely; document the browser cookie-harvest path as a manual fallback instead
- **Reason**: Since `client.login()` (.env credentials) + session cache exist, the harvested-cookies path is obsolete for normal operation; a TODO stub in the help is a broken promise. BUT the harvest path remains valuable as an escape hatch when programmatic login is blocked (temporary lockout / captcha after failed attempts — observed before).
- **Escape hatch (if captcha/lockout strikes)**: log in once in the browser (started via `scripts/brave-debug.sh`), run the recorder (`wu record`), perform any page action, stop it — the recorder writes `recordings/<ts>_spengergasse_webuntis_com_cookies.json` (via CDP `Network.getAllCookies`) at session end. Build `~/.webuntis_session.json` manually from it:
  `{"jsessionid": "<JSESSIONID>", "schoolname": "<schoolname cookie>", "school": "spengergasse", "host": "https://spengergasse.webuntis.com", "savedAt": "<iso>"}`
  — then all CLI commands use the harvested session like a cached login.
- **Tradeoff**: single-session suspicion — using the harvested session in the CLI may invalidate the browser session (or vice versa); browser login itself bypasses captcha, the CLI cannot.
- **Considered**: implementing `cookies` (find newest recordings/*_cookies.json, seed the session cache, masked display + --json)

## 2026-09-16: Person data policy — anonymized tracked files, LOCAL.md on user request
- **Choice**: Keep `HANDOFF.md`/`STATE.md` tracked but anonymized; introduce gitignored `docs/ai/LOCAL.md` as the only file where agents may write student names/IDs, and only on explicit user request
- **Reason**: Repo is public; past exposures of student names/IDs accepted as uncritical, but no new person data may be committed. No git-history rewrite.
- **Considered**: Untracking HANDOFF/STATE entirely; full history rewrite (filter-repo)
- **Tradeoff**: Old person data remains in git history (accepted); agents must actively route person data to LOCAL.md

## 2026-09-21: Domain-CLI (harter Schnitt, alles deutsch)
- **Choice**: Befehle heißen `klasse`, `lesson`, `student`, `offen`,
  `search`, `intern` — alte Namen (`students`, `lessons`, `lehrstoff`,
  `absences`, `kv`, …) ersatzlos gestrichen, keine Aliase. Eine Lesson
  wird immer als `KLASSE/FACH` adressiert (z.B. `3AHWII/SWP1x`).
  Lehrstoff ist Unterbefehl von `lesson`, Absenzen stehen in `lesson`
  (fehlt/gehalten je Schüler) und im `student`-Detail. `offen` ist die
  Top-Level-Arbeitsvorratssicht offener Perioden. `search` bleibt
  Top-Level (einzige englische Ausnahme — wird per Shell-Alias
  aufgerufen) und dispatcht: Student→Student-Detail,
  Lehrer→dessen Lessons, Klasse→Klassen-Sicht. `intern`
  (login/logout/session/record/rpc/rest) ist aus der Hilfe versteckt
  (`help=SUPPRESS`), bleibt aber als Escape-Hatch funktionsfähig.
- **Reason**: Domain-Objekte (Klasse, Lesson, Student) statt
  Endpoint-Namen; WebUntis ist DACH-only → UI deutsch.
- **Considered**: Alias-Modell (abgelehnt — zwei Namenswelten),
  nur-Hilfe-ohne-Umbau (abgelehnt — löst Singular/Plural-Chaos nicht)
- **Tradeoff**: bricht alle bestehenden Aufrufe/Notizen/Skripte sofort —
  Migrationsliste alt→neu in README pflegen; Skill synchron migrieren
- **Scope**: UI (Hilfe, Meldungen, Befehls-/Optionsnamen) deutsch;
  JSON-Keys bleiben englisch (Skill-Parsing), interner Code englisch

## 2026-09-21: Lesson-Enumeration aus dem Stundenplan (nicht open-periods)
- **Choice**: `klasse … faecher`, `student` und der `lesson KLASSE/FACH`-
  Resolver enumerieren Lessons primär aus dem KLASSEN-STUNDENPLAN
  (`GET rest/view/v1/timetable/entries`, resourceType=CLASS, eine Woche
  um das Referenzdatum mit Nachbarwochen-Fallback). lsId nur im
  Einzelfall per `GET v2/calendar-entry/detail` (`lesson.lessonId` =
  Matrix-lsId, verifiziert). `open-periods` bleibt nur für Offen-Status,
  Arbeitsvorrat (`offen …`) und als Resolver-FALLBACK (heute−7/+13),
  wenn der Plan nicht ladbar ist. `student` ohne Matrix-Call
  (2 Plan-Calls, Join Klasse×Schüler), Absenzen opt-in via
  `--absenzen` (nur EIGENE Lessons via MY_TIMETABLE, da die Matrix
  rechte-beschränkt ist); `belegt` = eingeschrieben (Fach im
  Schüler-Plan), Anwesenheit irrelevant. Parallele Gruppen desselben
  Fachs (POS1_3BAIF_1/2/3) werden per Primary-Lehrer getrennt, eigene
  Lessons per Slot-Match markiert (MY_TIMETABLE anonymisiert die
  eigene Lehrerposition).
- **Reason**: open-periods kennt nur OPEN-Filter — erledigte Lessons
  fehlten (WMC_1 verschwand aus `student`, Unterzählung der Absenzen);
  10–12 Matrix-Calls pro Schüler wurden vom Nutzer explizit abgelehnt.
- **Considered**: open-periods-Enumeration belassen (abgelehnt — lückig),
  lsId-Spalten in Listen (abgelehnt — 10–12 Detail-Calls), Voll-Scan
  über Matrizen (abgelehnt)
- **Tradeoff**: Stundenplan-Quelle braucht 2–3 leichte Calls statt 1
  open-periods-Call; Ferien-Fenster-Fallback nötig

## 2026-09-21: Absenz-Write-Workflow (setzen/löschen) an der Lesson
- **Choice**: `lesson K/F absenzen eintragen|entfernen` (Testlauf-Standard,
  Block-Standard, `--kein-block` nur mit --termin-id) implementieren;
  `absenzen zeigen --termin-id` listet echte Absenz-Einträge
  (classregpage-ViewModel) als Discovery. `raum suchen|groesse` nur als
  verdrahtete Stubs (Exit 3) — Endpunkte (rooms/form mit capacity,
  ROOM-entries) sind dokumentiert, echte Freie-Raum-Suche ist
  Folgeissue.
- **Reason**: Nutzer-Anforderung nach dem CDP-Recording (Setzen/Löschen
  einer Abwesenheit wurde manuell aufgezeichnet und reverse-engineered);
  Raumsuche explizit Zukunftsmusik, aber Vokabular soll reserviert sein.
- **Considered**: Absenz-Write unter `student` (abgelehnt — Abwesenheit
  ist (Schüler × Termin einer Lesson), gehört zur Lesson-Adresse);
  Raumbefehle ganz weglassen (abgelehnt — Nutzer will CLI-Nutzen später)
- **Tradeoff**: zwei .do-CSRF-Flows (classregpage + absencedlg mit
  frischem Token pro GET) — dokumentiert und getestet

## 2026-09-21: Doku anonymisiert — Platzhalter-IDs, keine echten Werte
- **Choice**: API-Referenz (WEBUNTIS_API.md) mit Schablone je Endpunkt;
  Beispiele NUR mit Platzhaltern (`CLASS_ID`, `STUDENT_ID`, `LESSON_ID`,
  `PERIOD_ID`, `ABSENCE_ID`, `ROOM_ID`) bzw. offenkundig fiktiven Namen
  (Erika Musterfrau, 5XZY) — KEINE echten IDs mehr in neuen
  Dokumentations-Abschnitten (alt-committede lsId/classId-Beispiele
  bleiben unverändert stehen). Hinweis, dass Live-IDs per CLI in
  Sekunden erhältlich sind.
- **Reason**: Nutzer-Vorgabe („keine echten IDs und keine echten
  Personennamen, weil das verboten ist"); lsIds/classIds sind zwar laut
  CONVENTIONS erlaubt, die strengere Regel gewinnt.
- **Considered**: echte IDs weiterhin erlauben (abgelehnt)
- **Tradeoff**: Beispiele sind nicht 1:1 reproduzierbar — Weg zu
  Live-IDs ist je dokumentiert

## 2026-09-18: roster falls back to nearest unit and labels the effective date
- **Choice**: `lesson roster` with no unit on the requested date lists the nearest upcoming unit (else last held) instead of erroring; the stdout header then carries the effective date (`3AAIF/WMC_1 (2026-09-22)`), `--json` reports `date` + `requestedDate`
- **Reason**: User always wants a class list (attendance check happens anyway); a mislabeled list would be worse than a substituted one, hence the visible date + stderr note
- **Considered**: Hard error on missing unit (first version); nearest-by-distance with future tie-break (rejected — no date tricks)
- **Tradeoff**: Pasted lists may cover a different day than requested — mitigated by the visible effective date

## 2026-09-21: offen-Zeitraum-Default aus open-periods/meta (Schuljahr bis heute)
- **Choice**: `--von/--bis` bei allen `offen`-Befehlen optional; ohne
  Angabe gilt Schuljahr-Start..heute aus `GET open-periods/meta`
  (`schoolYear.start`, Ende auf heute gedeckelt — UI-Semantik der
  /open-periods-Schuljahr-Ansicht, per CDP-Mitschnitt verifiziert:
  OnLoad heute..heute, Schuljahr-Wahl Start..heute, Zukunft nie offen).
  Halb angegeben (nur eins) ist Usage-Fehler (Exit 2); der Default wird
  nach stderr gemeldet. Neuer Client-Call `get_open_periods_meta()`.
- **Reason**: Nutzer-Vorgabe („Standardmäßig immer das gesamte
  Schuljahr"); Meta statt Schuljahr-Range aus getSchoolyears, weil die
  UI exakt diese Quelle nutzt.
- **Considered**: --von/--bis weiter Pflicht (abgelehnt — Reibung im
  Standard-Workflow); Default Schuljahr-Start..Schuljahr-Ende
  (abgelehnt — Zukunft ist nie offen, UI kappt bei heute)
- **Tradeoff**: ein zusätzlicher Meta-Call pro offen-Aufruf ohne
  Zeitraum; Meta-Ausfall ohne expliziten Zeitraum wirft RuntimeError
  statt zu raten

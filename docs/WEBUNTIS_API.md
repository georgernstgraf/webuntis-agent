# WebUntis API reference

Endpoints discovered or confirmed via CDP-Recorder for
`https://spengergasse.webuntis.com/`. This document is the authoritative
reference for the `webuntis-agent` client; each endpoint is grouped by
purpose and maps to a CLI command where applicable.

## Base configuration

- Host: `https://spengergasse.webuntis.com/`
- School slug: `spengergasse`
- Session cookies (set by login, sent on all subsequent requests):
  - `JSESSIONID` — session id
  - `schoolname` — `_` + Base64(`spengergasse`) = `_c3Blbmdlcmdhc3Nl`
- `Tenant-Id` header — derived from JWT (`tenant_id`), NOT hardcoded

## Authentication

### login (Spring Security form login)

- Purpose: establish the WebUntis session (sets `JSESSIONID`,
  `schoolname` cookies)
- Method: `POST /WebUntis/j_spring_security_check`
- Content-Type: `application/x-www-form-urlencoded`
- Body: `school=spengergasse&j_username=<user>&j_password=<pass>&token=`
- Response: 302 redirect on success (session cookies in `Set-Cookie`)
- CLI: implicit (called by `webuntis-agent` before any other command)

### getJwtToken

- Purpose: obtain a short-lived JWT Bearer token for REST endpoints
- Method: `GET /WebUntis/api/token/new`
- Headers: `Cookie: JSESSIONID=...; schoolname=...`
- Response: plain-text JWT string (not JSON)
- JWT payload (decoded) contains:
  - `person_id` — the teacher id (used in `open-periods`)
  - `tenant_id` — the Tenant-Id header value
  - `username`, `host`, `sn` (school), `exp` (~15 min)
- CLI: implicit (called internally before REST calls)

## Schoolyears

### getSchoolyears (REST)

- Purpose: list all schoolyears with their id and date range
- Method: `GET /WebUntis/api/rest/view/v1/schoolyears`
- Headers: `Cookie`, `Authorization: Bearer <jwt>`, `Tenant-Id`
- Response: `[{id, name, dateRange:{start,end}}, ...]`
- Note: the agent picks the schoolyear whose date range contains the
  target lesson date; falls back to `current_year - 2005` if none.
  Override with `--school-year-id`.

## Lesson Topics (Lehrstoff)

### getOpenPeriods

- Purpose: list lessons where the teacher still owes a topic or absence
  entry
- Method: `POST /WebUntis/api/rest/view/v1/classreg/open-periods`
- Headers: `Cookie`, `Authorization: Bearer <jwt>`, `Content-Type: application/json`,
  `X-Webuntis-Api-School-Year-Id: <id>`, `Tenant-Id: <id>`
- Body: `{"teacherId":<person_id>,"filter":"TOPIC_OR_ABSENCE_OPEN","dateRange":{"start":"<yyyy-MM-dd>","end":"<yyyy-MM-dd>"}}`
- Response: `{"periods":[{period:{id,classes,subject,teachers,dtRange,...},topicId,topicNeeded,absCheckNeeded,...}]}`
- CLI: `webuntis-agent lehrstoff list --start <d> --end <d>`

### getLessonTopicMeta

- Purpose: metadata for the lesson-topic editor
- Method: `GET /WebUntis/api/rest/view/v1/classreg/lesson-topics/meta`
- Headers: as above
- Response: metadata object (rarely needed directly)

### getLessonTopic

- Purpose: load the existing topic (text, id, attachments) for a period
- Method: `GET /WebUntis/api/rest/view/v1/classreg/lesson-topics/period/{periodId}?nearbyCount=-5&exceptThis=false`
- Headers: as above
- Response:
  `{"periodTopics":[{"period":{...},"topic":{"id","periodId","text","methodId","attachments":[]},"canSave":true}]}`
- CLI: `webuntis-agent lehrstoff get --period <id>`

### setLessonTopic (Lehrstoff eintragen)

- Purpose: write the lesson topic text
- Method: `PUT /WebUntis/api/rest/view/v1/classreg/lesson-topics`
- Headers: `Cookie`, `Authorization: Bearer <jwt>`,
  `Content-Type: application/json`, `X-Webuntis-Api-School-Year-Id: <id>`,
  `Tenant-Id: <id>`
- Body: `{"forceBlock":false,"topic":{"id":<topicId>,"periodId":<periodId>,"text":"<...>","attachments":[]}}`
- Response (200): `{"topics":[{"id","periodId","text","methodId","attachments":[]}, ...]}` — returns all topics in the block
- Note: `topic.id` comes from `getLessonTopic` (always an update when
  coming via Open Periods — the empty topic row already exists)
- CLI: `webuntis-agent lehrstoff set --period <id> --topic-id <id> --text "<...>"`

## Workflows

### Workflow: Lehrstoff nachtragen (Open Periods)

1. `login(user, password)` → session cookies
2. `getJwtToken()` → JWT (decode for `person_id`, `tenant_id`)
3. `getSchoolyears()` → pick schoolyear id for the lesson date
4. `getOpenPeriods(teacherId=person_id, dateRange=…)` → list of owed periods
5. For each desired period: `getLessonTopic(periodId)` → obtain `topic.id`
6. `setLessonTopic(periodId, topicId, text)` → PUT
7. (later) `getOpenPeriods(...)` again to verify

## CLI

- `webuntis-agent lehrstoff status --start <d> --end <d> [--json]`
  — quick overview of open periods grouped by subject/class
- `webuntis-agent lehrstoff fill --start <d> --end <d> [--dry-run] [--file <json>]`
  — fetch open periods + git diffs in one call; dry-run outputs JSON with
  commits/diffs/proposedText per block; without dry-run submits a confirmed
  batch JSON (--file)
- `webuntis-agent lehrstoff verify --start <d> --end <d> [--json]`
  — check which open periods truly have no topic text vs only missing absence check
- `webuntis-agent lehrstoff fill-fixed --start <d> --end <d> [--dry-run]`
  — fill SS/BESP periods with their fixed text (no git-log needed)
- `webuntis-agent lehrstoff list --start <d> --end <d> [--json]`
  — list open periods (JSON includes lessonDetailsUrl)
- `webuntis-agent lehrstoff get --period <id>`
  — show existing topic for a period
- `webuntis-agent lehrstoff set --period <id> --text-file <path>`
  — write single topic (UTF-8 safe via file)
- `webuntis-agent lehrstoff batch-set --file <json> [--delay 1.0]`
  — bulk write from JSON file
- `webuntis-agent lehrstoff from-git --class-name <c> --subject <s> --date <d> [--dry-run]`
  — derive text from GRG-* git logs + diffs
- `webuntis-agent absences check --period <id>`
  — check absences for one period
- `webuntis-agent absences check-all --start <d> --end <d> [--delay 1.5]`
  — auto-fetch open periods and check all absences
- `--school-year-id <N>` overrides the auto-detected schoolyear

## Subject -> GRG repo mapping

The `from-git` command and the `fill-open-periods` skill resolve which
GRG-* repositories to scan based on the WebUntis subject short name
(`period.subject.el.nameShort`). The mapping lives in
`src/webuntis_agent/client.py` as `SUBJECT_REPO_MAP` and is meant to be
extended as new subjects appear.

| WebUntis subject | Candidate GRG repos |
|---|---|
| `POS` / `POS1` | GRG-POSTHEORIE, GRG-POSTHEORIE-T, GRG-JAVA, GRG-JAVA-T |
| `SWP` / `SWP1` / `SWP1y` | GRG-SWP, GRG-SWP-T |
| `WMC` / `WMC1` | GRG-WMC, GRG-WMC-T |
| `INF` / `INFI` | GRG-INFI, GRG-INFI-T |
| `CS` | GRG-CS, GRG-CS-T |

Unknown subjects (e.g. `AM`, `D`, `G`, `REL`, ...) have no GRG repo;
the agent warns and skips those periods so the mapping can be extended.

## fill-open-periods workflow

1. `webuntis-agent lehrstoff list --start <yyyy-MM-dd> --end <yyyy-MM-dd> --json`
   — open periods as JSON
2. For each period: resolve candidate repos from the subject mapping; if
   empty, warn and skip. Otherwise call
   `gitlog.get_commits_for_class(class, date, repo_filter=repos)` and
   `gitlog.get_commit_diff_by_name(repo, hash)` per commit.
3. The agent (LLM) reads the diffs + file paths + subject + date and
   formulates a concise lesson-topic text.
4. Present a confirmation table (periodId | class | subject | date |
   proposed text). Group block periods (same `lsId`) together — one PUT
   updates the whole block.
5. On user confirmation, `webuntis-agent lehrstoff set --period <id>
   --topic-id <id> --text "<...>"` per period.

## Lesson Details URL (browser)

Once a topic is written, the browser displays it under "Lehrstoff" at:

```
https://spengergasse.webuntis.com/timetable/class/lessonDetails/
  {periodId}/{classId}/{elementType}/{startISO}/{endISO}/{bool}
  ?date={refDate}&entityId={classId}
```

- `periodId` — the period id
- `classId` — the class entity id (from `period.classes[0].el.id`, e.g. 3661 for 5AHWII)
- `elementType` — 1 = CLASS
- `startISO` / `endISO` — block bounds (start of the first period, end of
  the last period in the same `lsId` block), e.g. `2026-03-18T13:25:00`
- `bool` — `true`
- `date` (query) — a reference date for the timetable view (any day close
  to the lesson, e.g. a few days before)
- `entityId` (query) — same as `classId`

The CLI emits this URL in:
- `lehrstoff list --json` — as the `lessonDetailsUrl` field per period
- `lehrstoff batch-set --file <json>` — as `lessonDetailsUrl` in the
  result list, when the input JSON contains `classId`, `start`, `end`,
  `date` alongside `periodId`, `topicId`, `text`.

## Absences (Absenzenkontrolle)

### getCsrfToken (for classregpage)

- Purpose: obtain a CSRF token needed for the absence-check POST
- Method: `GET /WebUntis/classregpage.do?ttid=<periodId>&isBlockSelected=false&request.preventCache=<timestamp>`
- Headers: `Cookie: JSESSIONID=...; schoolname=...`, `X-Requested-With: XMLHttpRequest`
- Response: HTML containing `<input type="hidden" name="_csrf" value="<token>">`
- The token is extracted via regex and reused in the POST below.

### checkAbsences (Abwesenheiten kontrolliert)

- Purpose: mark absences as checked for a period (and its block partner)
- Method: `POST /WebUntis/classregpage.do?request.preventCache=<timestamp>`
- Content-Type: `application/x-www-form-urlencoded`
- Headers: `Cookie`, `X-CSRF-TOKEN: <csrf_token>`, `X-Requested-With: XMLHttpRequest`
- Body (form-encoded): `ttid=<periodId>&isBlockSelected=false&request.preventCache=<timestamp>&absencechecked=absencechecked&reload=0&_csrf=<csrf_token>`
- Response (200): `{"args":[[<periodId>,<blockPartnerId>]],"method":"setAbsencesChecked","success":true}`
- Note: No JWT needed — uses session cookie + CSRF only. Block partner is auto-marked.
- CLI: `webuntis-agent absences check --period <id>`
- CLI: `webuntis-agent absences check-all --start <d> --end <d> [--delay 1.5]`

## Discovered API Surface (SPA bundles)

The WebUntis SPA loads JS bundles that contain ALL API routes the UI can
call. Extraction method: login → `GET /` → parse `/assets/*.js` URLs →
download bundles → regex-extract paths. Bundles saved under
`/tmp/opencode/bundles/` (not in repo).

Key route groups (full list in `/tmp/opencode/bundles/`, extract via
regex `/api/rest/view/v\d+...`):

- `students/{id}/lessons`, `students/{id}/change-class`, `students/{id}/form`,
  `students/{id}/class-history`, `students/overview` — student admin
  (admin role only; teachers get 500/0 results)
- `classreg/absences`, `classreg/lesson-topics`, `classreg/open-periods` — known
- `messages/*`, `exams/*`, `timetable/*`, `tt/horizons/*` — other modules

## Class Register Legacy App (iframe)

The class register is a legacy JSP app loaded in an iframe:
`/WebUntis/embedded.do#<hash-route>`. Hash routes (from SPA bundle
`webuntis-embedded/main.js`):

- `#classregpage?ttid={periodId}&isBlockSelected={bool}` — class register page
  (absences; documented above)
- `#lessonstudentlist.do?lsid={lessonId}` — "Schüler*innen im Unterricht"
  (lesson participant list); directly accessible at
  `/WebUntis/lessonstudentlist.do?lsid={lsId}`
- `#studentlessonperiodmatrix?lessonId={lessonId}` — student-period
  assignment matrix; widget:
  `grupet/widget/app/studentlessonperiodmatrix/StudentLessonPeriodMatrixPage`

Dojo CDN: `https://content.webuntis.com/WebUntis/static/2027.1.6/js/`
(needs `Referer: {host}/WebUntis/embedded.do` header, else 403).
Widget `grupet/widget/lesson/LessonStudentList.js` = only report/message
buttons — add/remove student logic is in `StudentLessonPeriodMatrixPage`.

## Students / Classes (current data, schoolyear 24 = 2026/27)

- Current schoolyear is resolved dynamically (was 21 for 2025/26, now
  24 for 2026/27 — do NOT hardcode).
- `GET /WebUntis/api/rest/view/v1/students/overview` (teacher OK):
  `{schoolyears:[{schoolYear:{id,name,dateRange}, isCurrentSchoolYear, classes:[{id,name,startDate}]}]}`
  — class ids per schoolyear. 3BAIF=4107, 5BAIF=4137 (SY24).
- `getStudents` (JSON-RPC) returns 0 for teachers; `/students` REST is
  admin-only (500).
- Lesson participant list page (`lessonstudentlist.do?lsid=X`) contains:
  - `students:[{elementId:"5.<studentId>", userIds:[<userId>,...]}]`
    in `data-dojo-props`
  - per-student `studentId` in onclick: `marklist?lsId=X&studentId=Y`
  - `multipleMarkEntryDialogArgs` with `lsId`, `periodId`,
    `studentgroup`, `subject`, `klassen`, `students[]`
  - NO add/remove buttons — the add mask is the
    StudentLessonPeriodMatrix widget (next to explore).
- Teacher's lessons per class via
  `GET /WebUntis/api/public/timetable/weekly/data?elementType=1&elementId={classId}&date={yyyy-MM-dd}&formatId=1`
  — response has `data.result.data.elementPeriods["{classId}"]` (periods
  with only element IDs) + `data.result.data.elements` (id→name lookup,
  type 1=class, 2=teacher, 3=subject, 4=room).
  Example SY24 week 1 for 3BAIF: POS1 lsId=215940 (GRG),
  WMC_1 lsId=218839 (GRG+LEA).

## Element Search / Klassenvorstand (teacher-name resolution)

`getTeachers()` (JSON-RPC) → error -8509 "no right for getTeachers()";
REST `/v1/teachers`, `/v1/teachers/{id}` → 403 Access Denied;
`messages/recipients/static/teachers` and `/search` → 200 but
ANONYMIZED (`personId:-1, displayName:""`, school-level privacy
setting). The weekly timetable elements carry SHORT names only.

Working path (CLI: `search`, `kv`):

- `GET /WebUntis/api/rest/view/v1/timetable/search?q={text}&schoolyear={id}`
  (REST headers incl. Bearer JWT; schoolyear id via `getSchoolyears`,
  e.g. 24 for 2026/27). Returns
  `{numPartialMatches, results:[{type: CLASS|TEACHER|STUDENT,
  resource:{id, shortName, longName, displayName}}]}` — displayName of
  a teacher is `"Lastname, Firstname (SHORT)"`.
- Klassenvorstand: JSON-RPC `getKlassen` entries carry `teacher1`
  (optionally teacher2/3) = teacher id of the class teacher.
  Resolve id → short name via the class's weekly timetable elements
  (type 2, probe up to 4 past weeks in case of lesson-free weeks),
  then short name → full name via timetable/search.
  Example: Melissa Tuncer (id 13442) is in klasse 4134 = 5AAIF,
  teacher1=147 = "Schiefer, Birgit (SB)".
- `allStudents.klasse` in the student matrix: `-1` = no class
  association in that context; otherwise the real class id (e.g.
  4137 = 5BAIF).

CLI commands: `search <text>`, `kv <class-id|class-name>`,
`students list --lsid X [--class-id Y] [--attending-only]`.

## Student Lesson Period Matrix (Schüler-Aufnahme / Teilnehmer)

The "add student to lesson" feature. Legacy jsonrpc_web service:

### getStudentLessonPeriodMatrix

- Purpose: load the attendance matrix for a lesson (ALL school students!)
- Prerequisites (both required, else 403 Access Denied):
  1. Fresh CSRF: `GET /WebUntis/embedded.do?showSidebar=true` → parse
     `"csrfToken":"..."` from body
  2. `POST /WebUntis/jsonrpc_web/jsonCalendarService` body
     `{"id":0,"method":"setSchoolyear","params":[<schoolyearId>],"jsonrpc":"2.0"}`
- Method: `POST /WebUntis/jsonrpc_web/jsonStudentgroupService`
- Headers: `Cookie`, `X-CSRF-TOKEN: <csrf>`, `Content-Type: application/json`,
  `X-Requested-With: XMLHttpRequest`, `Referer: {host}/WebUntis/embedded.do`
- Body: `{"id":0,"method":"getStudentLessonPeriodMatrix","params":[<lsId>],"jsonrpc":"2.0"}`
- Response (200): `{result:{lessonSubject, lessonPeriods:[{id,date,studentCount,...}],
  startDate, endDate, mainStudentgroupId, allStudents:[{name,id,gender,klasse,
  attendedPeriods:[YYYYMMDD,...]}], allKlassen, lessonKlassen, lessonTeachers}}`
- `allStudents` = all ~3600 school students; `attendedPeriods` = list of
  lesson DATES (int YYYYMMDD) the student attends; empty = not attending.

### submitStudentLessonPeriodData (write!)

- Purpose: save attendance changes for a lesson
- Same endpoint: `POST /WebUntis/jsonrpc_web/jsonStudentgroupService`
- Body: `{"id":0,"method":"submitStudentLessonPeriodData","params":[{
  "mainStudentgroupId":<id>,"lessonId":<lsId>,
  "students":[{"id":<studentId>,"attendedPeriods":[<dates>]}],
  "startDate":<YYYYMMDD>,"endDate":<YYYYMMDD>}],"jsonrpc":"2.0"}`
- Derived from `StudentLessonPeriodMatrixViewModel.getAttendingPeriodData()`:
  students array = all students of the UI-selected klasse(s) with their
  attendance lists. Include the lesson's own class unchanged plus the
  added student (from another class) with full lesson dates.

### Key ids (schoolyear 24 / 2026-27)

- Student "Badawi Mhd Nour": id=19405, klasse=4137 (5BAIF), attendedPeriods=[]
  (also "Al Badawi Mahmoud" id=19261, same class — likely sibling)
- 3BAIF lesson POS1: lsId=215940, periodIds 5936072/5936075, mainStudentgroupId 166074
- 3BAIF lesson WMC_1: lsId=218839 (GRG+LEA)
- 3BAIF classId=4107 (17 students), 5BAIF classId=4137

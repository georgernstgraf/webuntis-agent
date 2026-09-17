"""WebUntis API client.

Replays the endpoints discovered via CDP-Recorder (see
docs/WEBUNTIS_API.md). All dynamic values (teacherId, Tenant-Id,
School-Year-Id) are derived at runtime — no hardcoded constants.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import httpx

DEFAULT_HOST = "https://spengergasse.webuntis.com"
DEFAULT_SCHOOL = "spengergasse"


def _request_with_retry(
    http: httpx.Client, method: str, url: str, *,
    client: "Client | None" = None,
    retries: int = 3, backoff: float = 2.0,
    retry_on: tuple = (httpx.ConnectError, httpx.ReadError),
    **kwargs: Any,
) -> httpx.Response:
    """Send a request with exponential backoff on transient connection errors.

    `headers` may be a zero-arg callable returning the dict — it is then
    evaluated per attempt, so a re-login retry picks up the NEW session
    cookie / JWT. If `client` is set and the response signals a lost
    session (401 or redirect to the login form), the client re-logs in
    once and the request is retried with fresh headers.
    """
    last_exc: Exception | None = None

    def _send() -> httpx.Response:
        kw = dict(kwargs)
        h = kw.get("headers")
        if callable(h):
            kw["headers"] = h()
        return http.request(method, url, **kw)

    for attempt in range(retries + 1):
        try:
            r = _send()
        except retry_on as e:
            last_exc = e
            if attempt == retries:
                raise
            sleep_s = backoff * (2 ** attempt)
            time.sleep(sleep_s)
            continue
        if client is not None and client._auth_lost(r):
            client.relogin()
            return _send()
        return r
    assert last_exc is not None
    raise last_exc

# WebUntis subject short name -> candidate GRG-* repo names (incl. -T
# teacher companions). Matched by prefix so that group/level variants
# (e.g. SWP1x, SWP1y, WMC_1, INFIx, POS1, POS2, ...) are all covered.
# Extend this mapping when new subjects appear; the agent warns on
# unknown subjects so they can be added here.
SUBJECT_REPO_MAP: dict[str, list[str]] = {
    "POS": ["GRG-POSTHEORIE", "GRG-POSTHEORIE-T", "GRG-JAVA", "GRG-JAVA-T"],
    "SWP": ["GRG-SWP", "GRG-SWP-T", "GRG-CS", "GRG-CS-T"],
    "WMC": ["GRG-WMC", "GRG-WMC-T"],
    "INF": ["GRG-INFI", "GRG-INFI-T"],
    "CS": ["GRG-CS", "GRG-CS-T"],
}

# Subjects with a fixed text (no git-log analysis needed).
FIXED_TEXT_SUBJECTS: dict[str, str] = {
    "SS": "Sprechstunde",
    "BESP": "Bewegung und Sport",
}


def tokenize_search_query(query: str) -> list[str]:
    """Split a search query into deduped tokens (whitespace/comma).

    Pure helper, shared by the search fallback paths.
    """
    seen: list[str] = []
    lowered: set[str] = set()
    for part in re.split(r"[\s,;]+", query.strip()):
        if part and part.lower() not in lowered:
            lowered.add(part.lower())
            seen.append(part)
    return seen


def _search_result_text(result: dict[str, Any]) -> str:
    res = result.get("resource", {})
    return " ".join(str(res.get(k, "")) for k in
                    ("shortName", "longName", "displayName")).lower()


def is_shortname_hint(result: dict[str, Any],
                      tokens: list[str]) -> bool:
    """Heuristic: shortName looks like Lastname+Firstname-prefix.

    Student shortNames follow the pattern <lastname><firstname[:3]>
    (e.g. "MusterEri" for Erika Muster), while displayName carries only
    the last name. Returns True when the shortName matches such a
    combination of two query tokens. Heuristic only — flagged via
    `searchNote: shortname-hint`, never silently.
    """
    if len(tokens) < 2:
        return False
    short = str(result.get("resource", {}).get("shortName", "")).lower()
    if not short:
        return False
    toks = [t.lower() for t in tokens]
    for i, first in enumerate(toks):
        for last in toks[i + 1:]:
            for a, b in ((first, last), (last, first)):
                if short == b + a[:3]:
                    return True
                if (len(a) >= 2 and short.startswith(b)
                        and a[:3] in short[len(b):]):
                    return True
    return False


def merge_search_results(
    token_hits: dict[str, list[dict[str, Any]]],
    tokens: list[str],
) -> list[dict[str, Any]]:
    """Merge per-token timetable/search hits.

    Pure helper: dedupes by (type, id) and ranks hits matching ALL
    tokens (in shortName/longName/displayName) before partial hits.
    Every returned hit is a shallow copy annotated with `searchNote`
    ("token-fallback", plus "+shortname-hint" when the heuristic fires).
    """
    by_key: dict[tuple, dict[str, Any]] = {}
    for tok, hits in token_hits.items():
        for h in hits:
            res = h.get("resource", {})
            key = (h.get("type"), res.get("id"))
            entry = by_key.setdefault(key, {"hit": h, "tokens": set()})
            entry["tokens"].add(tok.lower())
    scored: list[tuple[tuple, dict[str, Any]]] = []
    for (typ, _id), entry in by_key.items():
        hit = dict(entry["hit"])
        texts = _search_result_text(hit)
        matches_all = all(t.lower() in texts for t in tokens)
        hint = is_shortname_hint(hit, tokens)
        note = "token-fallback" + ("+shortname-hint" if hint else "")
        hit["searchNote"] = note
        rank = (0 if matches_all else 1, -len(entry["tokens"]))
        scored.append((rank, hit))
    scored.sort(key=lambda s: s[0])
    return [h for _, h in scored]


def student_matches_overview(student: dict[str, Any],
                             tokens: list[str]) -> bool:
    """True when EVERY token matches first/last/short name (AND).

    Pure helper for the current-roster students/overview lookup, where
    full first+last names (unlike the anonymized search displayName)
    are available.
    """
    hay = " ".join([str(student.get("firstName", "")),
                    str(student.get("lastName", "")),
                    str(student.get("shortName", ""))]).lower()
    return all(t.lower() in hay for t in tokens)


def repos_for_subject(subject_short: str) -> list[str]:
    """Return candidate GRG-* repo names for a WebUntis subject short name.

    Matches by prefix so that variants (POS1, POS2, SWP1x, SWP1y, WMC_1,
    INFIx, ...) are all covered. Returns [] for unknown subjects so the
    caller can warn the user and extend SUBJECT_REPO_MAP.
    """
    if not subject_short:
        return []
    s = subject_short.upper()
    out: list[str] = []
    for prefix, repos in SUBJECT_REPO_MAP.items():
        if s.startswith(prefix):
            for r in repos:
                if r not in out:
                    out.append(r)
    return out


@dataclass
class Session:
    """WebUntis session state."""

    jsessionid: str
    schoolname_cookie: str
    school: str = DEFAULT_SCHOOL
    host: str = DEFAULT_HOST

    @classmethod
    def from_cookies(cls, cookies: list[dict[str, Any]]) -> "Session":
        jsessionid = ""
        schoolname = ""
        for c in cookies:
            if c.get("name") == "JSESSIONID":
                jsessionid = c.get("value", "")
            elif c.get("name") == "schoolname":
                schoolname = c.get("value", "")
        if not jsessionid or not schoolname:
            raise ValueError("Missing JSESSIONID or schoolname cookie")
        return cls(jsessionid=jsessionid, schoolname_cookie=schoolname)

    @property
    def cookie_header(self) -> str:
        return f"JSESSIONID={self.jsessionid}; schoolname={self.schoolname_cookie}"


@dataclass
class JwtPayload:
    teacher_id: int
    tenant_id: str
    username: str
    exp: int


def _decode_jwt(token: str) -> JwtPayload:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("malformed JWT")
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload))
    try:
        return JwtPayload(
            teacher_id=int(data["person_id"]),
            tenant_id=str(data["tenant_id"]),
            username=str(data["username"]),
            exp=int(data["exp"]),
        )
    except KeyError as e:
        raise ValueError(f"JWT missing field: {e}") from e


class Client:
    """WebUntis HTTP client. Auto-login via .env, then REST/JSON-RPC."""

    def __init__(self, host: str = DEFAULT_HOST, school: str = DEFAULT_SCHOOL,
                 user: str | None = None, password: str | None = None,
                 session: Session | None = None, timeout: float = 30.0,
                 session_path: str | None = None):
        self.host = host
        self.school = school
        self.user = user or os.environ.get("WEBUNTIS_USER", "")
        self.password = password or os.environ.get("WEBUNTIS_PASSWORD", "")
        self.http = httpx.Client(timeout=timeout, follow_redirects=False)
        self._session: Session | None = session
        self._jwt: str | None = None
        self._jwt_payload: JwtPayload | None = None
        self._schoolyears: list[dict[str, Any]] | None = None
        self.session_path = session_path

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ----- session / auth ---------------------------------------------

    @property
    def session(self) -> Session:
        if self._session is None:
            self.login()
        assert self._session is not None
        return self._session

    def login(self) -> None:
        if not self.user or not self.password:
            raise RuntimeError(
                "WEBUNTIS_USER / WEBUNTIS_PASSWORD not set "
                "(copy .env.example to .env)"
            )
        r = _request_with_retry(
            self.http, "POST",
            f"{self.host}/WebUntis/j_spring_security_check",
            data={
                "school": self.school,
                "j_username": self.user,
                "j_password": self.password,
                "token": "",
            },
        )
        # 302 is NOT a success signal: WebUntis redirects to /WebUntis/
        # for BOTH successful and failed logins (a failed login still
        # sets a fresh, anonymous JSESSIONID). Verify via the SPA
        # bootstrap page, which carries "anonymousMode":true|false.
        if r.status_code != 302:
            raise RuntimeError(
                f"login failed (status {r.status_code})"
            )
        v = self.http.get(
            f"{self.host}/WebUntis/",
            headers={"Cookie": self._session_cookie_from_response()},
            follow_redirects=True,
        )
        m = re.search(r'"anonymousMode":(true|false)', v.text)
        if not m:
            # fail-closed: without the marker we cannot verify the
            # login (e.g. after a SPA layout change) — refuse to
            # treat the session as authenticated.
            raise RuntimeError(
                "login could not be verified: anonymousMode marker "
                "missing on the SPA bootstrap page (layout change?)"
            )
        if m.group(1) == "true":
            err = re.search(r'"loginError":"([^"]*)"', v.text)
            detail = err.group(1) if err else "session not authenticated"
            raise RuntimeError(
                f"login rejected: {detail} (wrong credentials, or a "
                f"temporary login lockout/captcha after failed attempts)"
            )
        jsessionid = ""
        schoolname = ""
        for c in self.http.cookies.jar:
            if c.name == "JSESSIONID":
                jsessionid = c.value
            elif c.name == "schoolname":
                schoolname = c.value
        if not jsessionid:
            jsessionid = r.cookies.get("JSESSIONID", "")
            schoolname = r.cookies.get("schoolname", "")
        if not jsessionid:
            raise RuntimeError("login did not set JSESSIONID")
        self._session = Session(
            jsessionid=jsessionid,
            schoolname_cookie=schoolname or (
                "_" + base64.b64encode(self.school.encode()).decode()
            ),
            school=self.school, host=self.host,
        )
        self.save_session()

    def _session_cookie_from_response(self) -> str:
        parts = []
        for c in self.http.cookies.jar:
            if c.name in ("JSESSIONID", "schoolname", "Tenant-Id"):
                parts.append(f"{c.name}={c.value}")
        return "; ".join(parts)

    # ----- session cache (persisted login) ------------------------------

    def save_session(self) -> None:
        """Atomically persist the current session (chmod 600)."""
        if not self.session_path or self._session is None:
            return
        data = {
            "jsessionid": self._session.jsessionid,
            "schoolname": self._session.schoolname_cookie,
            "school": self._session.school,
            "host": self._session.host,
            "savedAt": datetime.now().isoformat(timespec="seconds"),
        }
        tmp = self.session_path + ".tmp"
        # O_CREAT with explicit 0o600 mode: the file must NOT exist with
        # wide-open umask permissions even for a moment before chmod
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, self.session_path)

    def load_cached_session(self) -> bool:
        """Adopt a persisted session if it matches host/school.

        Corrupt or foreign files are ignored (fresh login happens lazily
        on first request). Returns True when a cached session is loaded.
        """
        if not self.session_path or not os.path.exists(self.session_path):
            return False
        try:
            with open(self.session_path, encoding="utf-8") as f:
                data = json.load(f)
            s = Session(
                jsessionid=str(data["jsessionid"]),
                schoolname_cookie=str(data["schoolname"]),
                school=str(data.get("school", self.school)),
                host=str(data.get("host", self.host)),
            )
        except (OSError, ValueError, KeyError, TypeError):
            return False
        if s.school != self.school or s.host != self.host:
            return False
        self._session = s
        return True

    @staticmethod
    def _auth_lost(r: httpx.Response) -> bool:
        """True when the response indicates the server-side session died.

        A dead session does NOT answer 401 on every endpoint: the API
        redirects to /WebUntis/index.do instead.
        """
        if r.status_code == 401:
            return True
        loc = r.headers.get("location", "")
        if r.is_redirect and ("index.do" in loc or "login" in loc
                              or "j_spring_security_check" in loc):
            return True
        return False

    def relogin(self) -> None:
        """Force a fresh login (cache file is refreshed by login())."""
        self._session = None
        self._jwt = None
        self._jwt_payload = None
        self.login()

    def logout(self) -> None:
        """Best-effort server logout, then drop memory + cached session."""
        if self._session is not None:
            try:
                self.http.get(
                    f"{self.host}/WebUntis/logout.do",
                    headers={"Cookie": self._session.cookie_header},
                )
            except Exception:
                pass
        self._session = None
        self._jwt = None
        self._jwt_payload = None
        if self.session_path and os.path.exists(self.session_path):
            os.remove(self.session_path)

    def get_jwt(self) -> str:
        if self._jwt and self._jwt_payload and time.time() < self._jwt_payload.exp - 60:
            return self._jwt
        r = _request_with_retry(
            self.http, "GET",
            f"{self.host}/WebUntis/api/token/new",
            headers=lambda: {"Cookie": self.session.cookie_header},
            client=self,
        )
        r.raise_for_status()
        self._jwt = r.text.strip()
        self._jwt_payload = _decode_jwt(self._jwt)
        return self._jwt

    @property
    def jwt_payload(self) -> JwtPayload:
        if self._jwt_payload is None:
            self.get_jwt()
        assert self._jwt_payload is not None
        return self._jwt_payload

    @property
    def teacher_id(self) -> int:
        return self.jwt_payload.teacher_id

    @property
    def tenant_id(self) -> str:
        return self.jwt_payload.tenant_id

    # ----- schoolyear --------------------------------------------------

    def get_schoolyears(self) -> list[dict[str, Any]]:
        if self._schoolyears is None:
            r = _request_with_retry(
                self.http, "GET",
                f"{self.host}/WebUntis/api/rest/view/v1/schoolyears",
                headers=lambda: self._rest_headers(),
                client=self,
            )
            r.raise_for_status()
            self._schoolyears = r.json()
        return self._schoolyears

    def resolve_schoolyear_id(self, when: date | None = None,
                              override: int | None = None) -> int:
        if override is not None:
            return override
        when = when or date.today()
        for sy in self.get_schoolyears():
            dr = sy.get("dateRange", {})
            start = self._parse_iso(dr.get("start", ""))
            end = self._parse_iso(dr.get("end", ""))
            if start <= when <= end:
                return int(sy["id"])
        raise RuntimeError(
            f"no schoolyear matches {when.isoformat()} — schoolyear ids "
            "are NOT derivable arithmetically (see docs/ai/PITFALLS.md); "
            "resolve dynamically or override with --school-year-id"
        )

    @staticmethod
    def _parse_iso(s: str) -> date:
        return date.fromisoformat(s)

    # ----- REST helpers ------------------------------------------------

    def _rest_headers(self, extra: dict[str, str] | None = None,
                      school_year_id: int | None = None) -> dict[str, str]:
        h = {
            "Cookie": self.session.cookie_header,
            "Authorization": f"Bearer {self.get_jwt()}",
            "Tenant-Id": self.tenant_id,
        }
        if school_year_id is not None:
            h["X-Webuntis-Api-School-Year-Id"] = str(school_year_id)
        if extra:
            h.update(extra)
        return h

    # ----- Generic REST passthrough --------------------------------------

    def rest(self, path: str, method: str = "GET",
             json_body: Any = None,
             school_year_id: int | None = None) -> Any:
        """Generic passthrough to /WebUntis/api/<path>.

        `path` is relative to /WebUntis/api (leading slash optional).
        NOTE: HTTP method does NOT imply read vs. write in this API —
        `classreg/open-periods` and all JSON-RPC are POST but read-only,
        while writes are `PUT classreg/lesson-topics`,
        `submitStudentLessonPeriodData` and the `absencechecked` POST.
        """
        url = f"{self.host}/WebUntis/api/{path.lstrip('/')}"
        r = _request_with_retry(
            self.http, method, url,
            json=json_body if json_body is not None else None,
            # callable: after a transparent re-login the retry must pick
            # up the NEW session cookie / JWT
            headers=lambda: self._rest_headers(
                {"Content-Type": "application/json"}
                if json_body is not None else {},
                school_year_id=school_year_id,
            ),
            client=self,
        )
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text

    def get_app_data(self) -> dict[str, Any]:
        """SPA bootstrap payload (user, roles, permissions, tenant,
        timegrid, currentSchoolYear, ...)."""
        return self.rest("rest/view/v1/app/data")

    # ----- Lesson Topics (Lehrstoff) -----------------------------------

    def get_open_periods(self, start: str, end: str,
                        filter_: str = "TOPIC_OR_ABSENCE_OPEN",
                        school_year_id: int | None = None) -> dict[str, Any]:
        r = _request_with_retry(
            self.http, "POST",
            f"{self.host}/WebUntis/api/rest/view/v1/classreg/open-periods",
            json={
                "teacherId": self.teacher_id,
                "filter": filter_,
                "dateRange": {"start": start, "end": end},
            },
            headers=lambda: self._rest_headers(
                {"Content-Type": "application/json"},
                school_year_id=school_year_id,
            ),
            client=self,
        )
        r.raise_for_status()
        return r.json()

    def get_lesson_topic(self, period_id: int,
                         nearby: int = -5,
                         school_year_id: int | None = None) -> dict[str, Any]:
        r = _request_with_retry(
            self.http, "GET",
            f"{self.host}/WebUntis/api/rest/view/v1/classreg/lesson-topics/period/{period_id}",
            params={"nearbyCount": nearby, "exceptThis": "false"},
            headers=lambda: self._rest_headers(
                school_year_id=school_year_id),
            client=self,
        )
        r.raise_for_status()
        return r.json()

    def set_lesson_topic(self, period_id: int, topic_id: int, text: str,
                        attachments: list | None = None,
                        force_block: bool = False,
                        school_year_id: int | None = None) -> dict[str, Any]:
        r = _request_with_retry(
            self.http, "PUT",
            f"{self.host}/WebUntis/api/rest/view/v1/classreg/lesson-topics",
            json={
                "forceBlock": force_block,
                "topic": {
                    "id": topic_id,
                    "periodId": period_id,
                    "text": text,
                    "attachments": attachments or [],
                },
            },
            headers=lambda: self._rest_headers(
                {"Content-Type": "application/json"},
                school_year_id=school_year_id,
            ),
            client=self,
        )
        r.raise_for_status()
        return r.json()

    # ----- JSON-RPC (read-only, public) --------------------------------

    def rpc(self, method: str, params: dict[str, Any] | None = None,
            id_: str = "webuntis-agent") -> dict[str, Any]:
        r = _request_with_retry(
            self.http, "POST",
            f"{self.host}/WebUntis/jsonrpc.do",
            params={"school": self.school},
            json={
                "id": id_, "method": method,
                "params": params or {}, "jsonrpc": "2.0",
            },
            headers=lambda: {
                "Content-Type": "application/json",
                "Cookie": self.session.cookie_header,
            },
            client=self,
        )
        r.raise_for_status()
        data = r.json()
        self._raise_jsonrpc_error(data, method)
        return data

    @staticmethod
    def _raise_jsonrpc_error(data: Any, method: str) -> None:
        """Raise when a JSON-RPC payload carries an `error` object.

        Without this, server-side errors surface downstream as bogus
        empty results (e.g. getKlassen error -> "class not found").
        """
        if isinstance(data, dict) and data.get("error") is not None:
            err = data["error"]
            if isinstance(err, dict):
                code = err.get("code", "?")
                msg = err.get("message", err)
                extra = {k: v for k, v in err.items()
                         if k not in ("code", "message")}
            else:
                code, msg, extra = "?", err, {}
            raise RuntimeError(
                f"JSON-RPC {method} failed (code {code}): {msg}"
                + (f" {extra}" if extra else "")
            )

    def get_klassen(self, schoolyear_id: int | None = None) -> dict[str, Any]:
        params = {}
        if schoolyear_id is not None:
            params["schoolyearId"] = schoolyear_id
        return self.rpc("getKlassen", params)

    def get_subjects(self) -> dict[str, Any]:
        return self.rpc("getSubjects")

    def get_teachers(self) -> dict[str, Any]:
        return self.rpc("getTeachers")

    def get_current_schoolyear(self) -> dict[str, Any]:
        return self.rpc("getCurrentSchoolyear")

    # ----- Timetable search (element lookup with full names) -----------

    def search_timetable(self, query: str,
                          school_year_id: int | None = None
                          ) -> list[dict[str, Any]]:
        """Search classes/teachers/students with full display names.

        The only working name-resolution path for teacher accounts:
        getTeachers() and /v1/teachers are 403, but this search endpoint
        returns shortName + longName + displayName for every hit.

        NOTE: the server does NOT match multi-word phrases across
        first+last name (e.g. "Erika Muster" -> []). Use
        search_timetable_tokens() for a tokenizing fallback.
        """
        if school_year_id is None:
            school_year_id = self.resolve_schoolyear_id()
        r = _request_with_retry(
            self.http, "GET",
            f"{self.host}/WebUntis/api/rest/view/v1/timetable/search",
            params={"q": query, "schoolyear": school_year_id},
            headers=lambda: self._rest_headers(),
            client=self,
        )
        r.raise_for_status()
        return r.json().get("results", [])

    def search_timetable_tokens(
        self, query: str,
        school_year_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Tokenizing fallback around search_timetable().

        Shared helper — may be reused by other subcommands. Splits the
        query into tokens, searches each token (plus the exact phrase
        first, so exact matches keep top rank), and merges/dedupes via
        merge_search_results(). Annotated hits carry an extra
        `searchNote` key ("token-fallback" / "shortname-hint"); exact
        phrase hits are returned unannotated.
        """
        if school_year_id is None:
            school_year_id = self.resolve_schoolyear_id()
        tokens = tokenize_search_query(query)
        if len(tokens) <= 1:
            return self.search_timetable(query, school_year_id=school_year_id)
        phrase_hits = self.search_timetable(query, school_year_id=school_year_id)
        token_hits: dict[str, list[dict[str, Any]]] = {}
        for tok in tokens:
            token_hits[tok] = self.search_timetable(
                tok, school_year_id=school_year_id)
        merged = merge_search_results(token_hits, tokens)
        seen = {(h.get("type"),
                 h.get("resource", {}).get("id")) for h in merged}
        top = [h for h in phrase_hits
               if (h.get("type"), h.get("resource", {}).get("id")) not in seen]
        return top + merged

    def older_schoolyear_ids(self, current_id: int,
                             limit: int = 3) -> list[int]:
        """Ids of schoolyears older than `current_id`, newest first.

        Ordered by dateRange start (fallback: id) and capped at `limit`
        to avoid hammering the server with a full-history scan.
        """
        years = list(self.get_schoolyears())
        cur = next((y for y in years if int(y.get("id", -1)) == current_id),
                   None)
        if cur is None:
            return [int(y["id"]) for y in sorted(
                years, key=lambda y: int(y.get("id", 0)), reverse=True)
                if int(y.get("id", -1)) != current_id][:limit]
        cur_start = str(cur.get("dateRange", {}).get("start", ""))
        older = [y for y in years
                 if str(y.get("dateRange", {}).get("start", "")) < cur_start]
        older.sort(key=lambda y: str(
            y.get("dateRange", {}).get("start", "")), reverse=True)
        return [int(y["id"]) for y in older[:limit]]

    def schoolyear_label(self, schoolyear_id: int) -> str:
        """Human label for a schoolyear id, e.g. "2025/26"."""
        for y in self.get_schoolyears():
            if int(y.get("id", -1)) == schoolyear_id:
                return str(y.get("name", schoolyear_id))
        return str(schoolyear_id)

    def get_students_overview(self) -> dict[str, Any]:
        """Full student roster with first/last name + class info.

        NOTE: unlike timetable/search this endpoint is NOT
        schoolyear-sensitive — it always returns the current roster
        (classInfo carries the current class). Former students must be
        found via timetable/search with an older schoolyear id.
        """
        r = _request_with_retry(
            self.http, "GET",
            f"{self.host}/WebUntis/api/rest/view/v1/students/overview",
            headers=lambda: self._rest_headers(),
            client=self,
        )
        r.raise_for_status()
        return r.json()

    def get_weekly_timetable_elements(self, class_id: int,
                                      date: str) -> list[dict[str, Any]]:
        """Elements (id/name lookup) of a class's weekly timetable.

        Public endpoint; elements only carry SHORT names (e.g. 'SB').
        Resolve ids to full names via search_timetable().
        """
        r = _request_with_retry(
            self.http, "GET",
            f"{self.host}/WebUntis/api/public/timetable/weekly/data",
            params={"elementType": 1, "elementId": class_id,
                    "date": date, "formatId": 1},
            headers=lambda: {"Cookie": self.session.cookie_header},
            client=self,
        )
        r.raise_for_status()
        data = r.json()
        return data["data"]["result"]["data"]["elements"]

    # ----- Absences (Absenzenkontrolle) ---------------------------------

    def get_csrf_token(self, period_id: int) -> str:
        """GET classregpage.do for a period, extract _csrf from HTML."""
        ts = int(time.time() * 1000)
        r = _request_with_retry(
            self.http, "GET",
            f"{self.host}/WebUntis/classregpage.do",
            params={
                "ttid": period_id,
                "isBlockSelected": "false",
                "request.preventCache": ts,
            },
            headers=lambda: {
                "Cookie": self.session.cookie_header,
                "X-Requested-With": "XMLHttpRequest",
            },
            client=self,
        )
        r.raise_for_status()
        m = re.search(r'name="_csrf"\s+value="([^"]+)"', r.text)
        if not m:
            raise RuntimeError(
                f"could not extract _csrf from classregpage.do "
                f"for period {period_id}"
            )
        return m.group(1)

    def check_absences(self, period_id: int) -> dict[str, Any]:
        """Mark absences as checked for a period (and its block partner).

        Two-step: (1) GET classregpage.do to obtain _csrf token,
        (2) POST classregpage.do with absencechecked=absencechecked.
        """
        csrf = self.get_csrf_token(period_id)
        ts = int(time.time() * 1000)
        r = _request_with_retry(
            self.http, "POST",
            f"{self.host}/WebUntis/classregpage.do",
            params={"request.preventCache": ts},
            data={
                "ttid": str(period_id),
                "isBlockSelected": "false",
                "request.preventCache": str(ts),
                "absencechecked": "absencechecked",
                "reload": "0",
                "_csrf": csrf,
            },
            headers=lambda: {
                "Cookie": self.session.cookie_header,
                "X-CSRF-TOKEN": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            client=self,
        )
        r.raise_for_status()
        return r.json()

    # ----- Student Lesson Period Matrix (Schüler-Aufnahme) --------------

    def _jsonrpc_web(self, service: str, method: str, params: list,
                     id_: int = 0,
                     school_year_id: int | None = None) -> dict[str, Any]:
        """Call a legacy jsonrpc_web service (needs fresh CSRF + setSchoolyear)."""
        # fresh CSRF token from embedded.do
        r = _request_with_retry(
            self.http, "GET",
            f"{self.host}/WebUntis/embedded.do",
            params={"showSidebar": "true"},
            headers=lambda: {"Cookie": self.session.cookie_header},
            client=self,
        )
        r.raise_for_status()
        m = re.search(r'"csrfToken":"([^"]+)"', r.text)
        if not m:
            raise RuntimeError("could not extract csrfToken from embedded.do")
        csrf = m.group(1)

        def _json_headers() -> dict:
            return {
                "Cookie": self.session.cookie_header,
                "X-CSRF-TOKEN": csrf,
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.host}/WebUntis/embedded.do",
                "Origin": self.host,
            }

        # setSchoolyear is required before other jsonrpc_web calls
        sy = self.resolve_schoolyear_id(override=school_year_id)
        r0 = _request_with_retry(
            self.http, "POST",
            f"{self.host}/WebUntis/jsonrpc_web/jsonCalendarService",
            json={"id": id_, "method": "setSchoolyear",
                  "params": [sy], "jsonrpc": "2.0"},
            headers=_json_headers,
            client=self,
        )
        r0.raise_for_status()
        self._raise_jsonrpc_error(r0.json(), "setSchoolyear")

        r = _request_with_retry(
            self.http, "POST",
            f"{self.host}/WebUntis/jsonrpc_web/{service}",
            json={"id": id_, "method": method,
                  "params": params, "jsonrpc": "2.0"},
            headers=_json_headers,
            client=self,
        )
        r.raise_for_status()
        data = r.json()
        self._raise_jsonrpc_error(data, method)
        return data

    def get_student_lesson_period_matrix(
        self, ls_id: int,
        school_year_id: int | None = None,
    ) -> dict[str, Any]:
        """Load the attendance matrix for a lesson (all school students)."""
        return self._jsonrpc_web(
            "jsonStudentgroupService", "getStudentLessonPeriodMatrix", [ls_id],
            school_year_id=school_year_id,
        )

    def submit_student_lesson_period_data(
        self, ls_id: int, main_studentgroup_id: int,
        students: list[dict[str, Any]],
        start_date: int, end_date: int,
        school_year_id: int | None = None,
    ) -> dict[str, Any]:
        """Save attendance changes for a lesson.

        students: [{"id": <studentId>, "attendedPeriods": [<YYYYMMDD>, ...]}]
        """
        payload = {
            "mainStudentgroupId": main_studentgroup_id,
            "lessonId": ls_id,
            "students": students,
            "startDate": start_date,
            "endDate": end_date,
        }
        return self._jsonrpc_web(
            "jsonStudentgroupService", "submitStudentLessonPeriodData",
            [payload],
            school_year_id=school_year_id,
        )

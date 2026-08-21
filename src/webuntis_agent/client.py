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
    retries: int = 3, backoff: float = 2.0,
    retry_on: tuple = (httpx.ConnectError, httpx.ReadError),
    **kwargs: Any,
) -> httpx.Response:
    """Send a request with exponential backoff on transient connection errors.

    Used by the client to survive temporary IP rate-limiting / TCP resets.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return http.request(method, url, **kwargs)
        except retry_on as e:
            last_exc = e
            if attempt == retries:
                raise
            sleep_s = backoff * (2 ** attempt)
            time.sleep(sleep_s)
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
                 session: Session | None = None, timeout: float = 30.0):
        self.host = host
        self.school = school
        self.user = user or os.environ.get("WEBUNTIS_USER", "")
        self.password = password or os.environ.get("WEBUNTIS_PASSWORD", "")
        self.http = httpx.Client(timeout=timeout, follow_redirects=False)
        self._session: Session | None = session
        self._jwt: str | None = None
        self._jwt_payload: JwtPayload | None = None
        self._schoolyears: list[dict[str, Any]] | None = None

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
        # 302 = success, 200 = failed (back to login)
        if r.status_code != 302:
            raise RuntimeError(
                f"login failed (status {r.status_code})"
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

    def get_jwt(self) -> str:
        if self._jwt and self._jwt_payload and time.time() < self._jwt_payload.exp - 60:
            return self._jwt
        r = _request_with_retry(
            self.http, "GET",
            f"{self.host}/WebUntis/api/token/new",
            headers={"Cookie": self.session.cookie_header},
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
                headers=self._rest_headers(),
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
        return datetime.now().year - 2005

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
            headers=self._rest_headers(
                {"Content-Type": "application/json"},
                school_year_id=school_year_id,
            ),
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
            headers=self._rest_headers(school_year_id=school_year_id),
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
            headers=self._rest_headers(
                {"Content-Type": "application/json"},
                school_year_id=school_year_id,
            ),
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
            headers={
                "Content-Type": "application/json",
                "Cookie": self.session.cookie_header,
            },
        )
        r.raise_for_status()
        return r.json()

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
            headers={
                "Cookie": self.session.cookie_header,
                "X-Requested-With": "XMLHttpRequest",
            },
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
            headers={
                "Cookie": self.session.cookie_header,
                "X-CSRF-TOKEN": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        r.raise_for_status()
        return r.json()

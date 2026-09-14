"""Session cache + auto re-login behaviour (no network)."""

import json
import os

import httpx
import pytest

from webuntis_agent.client import Client, Session


def _make_client(tmp_path, handler, session_path="s.json") -> Client:
    c = Client(user="u", password="p",
               session_path=str(tmp_path / session_path))
    c.http = httpx.Client(transport=httpx.MockTransport(handler),
                          follow_redirects=False)
    return c


def test_save_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "s.json")
    c = Client(user="u", password="p", session_path=path)
    c._session = Session(jsessionid="ABC123", schoolname_cookie="_sch",
                         school="spengergasse",
                         host="https://spengergasse.webuntis.com")
    c.save_session()
    assert os.path.exists(path)
    stat = os.stat(path)
    assert stat.st_mode & 0o777 == 0o600
    c2 = Client(user="u", password="p", session_path=path)
    assert c2.load_cached_session() is True
    assert c2.session.jsessionid == "ABC123"
    assert c2.session.cookie_header == "JSESSIONID=ABC123; schoolname=_sch"


def test_load_rejects_foreign_school(tmp_path):
    path = str(tmp_path / "s.json")
    (tmp_path / "s.json").write_text(json.dumps(
        {"jsessionid": "X", "schoolname": "_y", "school": "other",
         "host": "https://x.example"}))
    c = Client(user="u", password="p", session_path=path,
               school="spengergasse", host="https://spengergasse.webuntis.com")
    assert c.load_cached_session() is False
    assert c._session is None


def test_load_ignores_corrupt_file(tmp_path):
    path = str(tmp_path / "s.json")
    (tmp_path / "s.json").write_text("{not json")
    c = Client(user="u", password="p", session_path=path)
    assert c.load_cached_session() is False


def test_auth_lost_detection():
    req = httpx.Request("GET", "https://x.example/")
    assert Client._auth_lost(httpx.Response(401, request=req)) is True
    assert Client._auth_lost(httpx.Response(
        302, headers={"location": "/WebUntis/j_spring_security_check"},
        request=req)) is True
    assert Client._auth_lost(httpx.Response(
        302, headers={"location": "/WebUntis/index.do"},
        request=req)) is True
    assert Client._auth_lost(httpx.Response(
        302, headers={"location": "/WebUntis/somewhere"}, request=req)) is False
    assert Client._auth_lost(httpx.Response(200, request=req)) is False


_ANON_PAGE = '<script>cfg={"anonymousMode":true,' \
             '"loginError":"Ungültiger Benutzername und/oder Passwort"}</script>'
_AUTH_PAGE = '<script>cfg={"anonymousMode":false,"loginError":""}</script>'


def test_login_rejects_anonymous_session(tmp_path, monkeypatch):
    """A 302 from the login POST is NOT success: verify anonymousMode."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("j_spring_security_check"):
            return httpx.Response(302, request=request,
                                  headers={"location": "/WebUntis/"})
        return httpx.Response(200, request=request, text=_ANON_PAGE)

    c = _make_client(tmp_path, handler)
    with pytest.raises(RuntimeError, match="Ungültiger Benutzername"):
        c.login()
    assert c._session is None  # no bogus session kept / persisted
    assert not (tmp_path / "s.json").exists()


def test_login_accepts_authenticated_page(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("j_spring_security_check"):
            request.headers.get("cookie", "")
            return httpx.Response(
                302, request=request,
                headers={"location": "/WebUntis/",
                         "set-cookie": "JSESSIONID=GOOD123; Path=/WebUntis"})
        return httpx.Response(200, request=request, text=_AUTH_PAGE)

    c = _make_client(tmp_path, handler)
    c.login()
    assert c.session.jsessionid == "GOOD123"
    assert (tmp_path / "s.json").exists()



def test_relogin_retry_uses_fresh_headers(tmp_path, monkeypatch):
    """After a 401 the retried request must carry the NEW session cookie."""
    logins = {"n": 0}

    def fake_login(self):
        logins["n"] += 1
        self._session = Session(
            jsessionid=f"FRESH{logins['n']}",
            schoolname_cookie="_sch", school=self.school, host=self.host)
        self.save_session()

    monkeypatch.setattr(Client, "login", fake_login)

    seen_cookies = []

    def handler(request: httpx.Request) -> httpx.Response:
        cookie = request.headers.get("cookie", "")
        seen_cookies.append(cookie)
        if "JSESSIONID=STALE" in cookie:
            return httpx.Response(401, request=request)
        return httpx.Response(
            200, request=request,
            json={"jsonrpc": "2.0", "id": "webuntis-agent",
                  "result": [{"id": 1, "name": "SB"}]})

    c = _make_client(tmp_path, handler)
    c._session = Session(jsessionid="STALE", schoolname_cookie="_sch",
                         school=c.school, host=c.host)
    result = c.get_subjects()
    assert result["result"][0]["name"] == "SB"
    assert logins["n"] == 1
    assert any("JSESSIONID=STALE" in ck for ck in seen_cookies)
    assert any("JSESSIONID=FRESH1" in ck for ck in seen_cookies)
    # the login persisted the new session
    assert c.session.jsessionid == "FRESH1"


def test_no_relogin_loop_on_permanent_401(tmp_path, monkeypatch):
    """One relogin per request max, even if the retry fails again."""
    monkeypatch.setattr(
        Client, "login",
        lambda self: setattr(self, "_session",
                             Session("FRESH", "_sch", self.school, self.host)))
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, request=request)

    c = _make_client(tmp_path, handler)
    c._session = Session("STALE", "_sch", c.school, c.host)
    with pytest.raises(httpx.HTTPStatusError):
        c.get_subjects()
    assert calls["n"] == 2  # original + single retry, no loop

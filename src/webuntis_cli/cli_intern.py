"""CLI intern-Befehle (versteckt): Session, Recorder, Passthroughs.

Diese Befehle sind Interna für Entwicklung, Session-Management und das
Agenten-Setup — sie erscheinen nicht in der Hilfe (`help=SUPPRESS`),
bleiben aber funktionsfähig (Escape-Hatch z.B. bei Captcha-Sperre).
"""

from __future__ import annotations

import argparse
import json
import sys

from webuntis_cli.cli_common import (
    _make_client,
    _session_path,
)
from webuntis_cli.errors import AuthError


def cmd_login(args: argparse.Namespace) -> int:
    """Einmal einloggen und Session für alle folgenden Aufrufe cachen."""
    c = _make_client(args)
    c._session = None
    c.login()
    sid = c.session.jsessionid
    masked = (sid[:6] + "...") if len(sid) > 6 else "..."
    print(f"eingeloggt als {c.user or '?'} @ {c.host}")
    print(f"Session gecacht: {_session_path()} (JSESSIONID {masked})")
    c.close()
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    """Server-Session ungültig machen und Session-Cache löschen."""
    c = _make_client(args)
    c.logout()
    print("ausgeloggt; Session-Cache entfernt")
    c.close()
    return 0


def cmd_session_status(args: argparse.Namespace) -> int:
    """Session-Cache-Info + Live-Check via app/data-Bootstrap."""
    from datetime import datetime as _dt
    from pathlib import Path
    cache_path = _session_path()
    cached = None
    if Path(cache_path).exists():
        try:
            cached = json.loads(Path(cache_path).read_text(
                encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
    status: dict = {"cachePath": cache_path, "cached": cached is not None}
    if cached:
        saved_at = cached.get("savedAt")
        age = None
        if saved_at:
            try:
                age = (_dt.now() - _dt.fromisoformat(saved_at)).total_seconds()
            except ValueError:
                pass
        status["savedAt"] = saved_at
        status["ageSeconds"] = round(age) if age is not None else None
        sid = str(cached.get("jsessionid", ""))
        status["jsessionidMasked"] = (sid[:6] + "...") if len(sid) > 6 \
            else "..."
        status["host"] = cached.get("host")
        status["school"] = cached.get("school")

    c = _make_client(args)
    live: dict = {"alive": False}
    try:
        data = c.get_app_data()
        live["alive"] = True
        live["user"] = data.get("user")
        live["roles"] = data.get("roles")
        live["permissions"] = data.get("permissions")
        live["currentSchoolYear"] = data.get("currentSchoolYear")
        if args.json:
            live["appData"] = data
    except Exception as e:
        live["error"] = str(e)
    status["live"] = live

    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0 if live["alive"] else AuthError.exit_code
    print(f"Cache: {cache_path}")
    if cached:
        age_txt = (f"{status['ageSeconds']}s alt"
                   if status.get("ageSeconds") is not None else "")
        print(f"  savedAt: {status.get('savedAt')} ({age_txt})")
        print(f"  JSESSIONID: {status.get('jsessionidMasked')}")
        print(f"  host/school: {status.get('host')} / {status.get('school')}")
    else:
        print("  (kein Cache vorhanden)")
    if live["alive"]:
        print("live: Session ALIVE")
        print(f"  user: {live.get('user')}")
        if live.get("roles") is not None:
            print(f"  roles: {live.get('roles')}")
        if live.get("currentSchoolYear") is not None:
            print(f"  currentSchoolYear: {live.get('currentSchoolYear')}")
        return 0
    print(f"live: Session NICHT lebendig ({live.get('error')})",
          file=sys.stderr)
    return AuthError.exit_code


def cmd_rpc(args: argparse.Namespace) -> int:
    """Generischer JSON-RPC-Passthrough (kann lesen UND schreiben)."""
    c = _make_client(args)
    params = {}
    if args.params_json:
        params = json.loads(args.params_json)
    res = c.rpc(args.method, params)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_rest(args: argparse.Namespace) -> int:
    """Generischer REST-Passthrough nach /WebUntis/api/<Pfad>.

    Methode ≠ lesen/schreiben in dieser API: open-periods und alle
    JSON-RPC sind POST aber lesend, während PUT classreg/lesson-topics,
    submitStudentLessonPeriodData und der absencechecked-POST SCHREIBEN.
    Methode + Body werden vor dem Senden nach stderr gemeldet.
    """
    c = _make_client(args)
    sy = args.school_year_id
    body = None
    if args.data_json:
        body = json.loads(args.data_json)
    print(f"--> {args.method} /WebUntis/api/{args.path.lstrip('/')}"
          + (f" body={json.dumps(body, ensure_ascii=False)}"
             if body is not None else ""),
          file=sys.stderr)
    res = c.rest(args.path, method=args.method, json_body=body,
                 school_year_id=sy)
    if isinstance(res, str):
        print(res)
        return 0
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0

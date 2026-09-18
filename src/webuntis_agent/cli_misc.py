"""CLI misc commands (split from cli.py, see #15)."""

from __future__ import annotations

import argparse
import json
import sys

from typing import TYPE_CHECKING

from webuntis_agent.cli_common import (
    _make_client,
    _session_path,
    _format_search_hit,
    _annotate_search_hits,
)

from webuntis_agent.cli_students import (
    _teacher_names_for_class,
)

if TYPE_CHECKING:
    from webuntis_agent.client import Client


def cmd_login(args: argparse.Namespace) -> int:
    """Log in once and persist the session for all following CLI calls."""
    c = _make_client(args)
    c._session = None
    c.login()
    sid = c.session.jsessionid
    masked = (sid[:6] + "...") if len(sid) > 6 else "..."
    print(f"logged in as {c.user or '?'} @ {c.host}")
    print(f"session cached: {_session_path()} (JSESSIONID {masked})")
    c.close()
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    """Invalidate the server session and delete the cached session file."""
    c = _make_client(args)
    c.logout()
    print("logged out; session cache removed")
    c.close()
    return 0


def cmd_rpc(args: argparse.Namespace) -> int:
    """Generic JSON-RPC passthrough (read AND write methods possible)."""
    c = _make_client(args)
    params = {}
    if args.params_json:
        params = json.loads(args.params_json)
    res = c.rpc(args.method, params)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_rest(args: argparse.Namespace) -> int:
    """Generic REST passthrough to /WebUntis/api/<path>.

    HTTP method does NOT imply read vs. write in this API: open-periods
    and all JSON-RPC are POST but read-only, while PUT classreg/
    lesson-topics, submitStudentLessonPeriodData and the absencechecked
    POST WRITE. Method + body are echoed to stderr before sending.
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


def cmd_lesson_info(args: argparse.Namespace) -> int:
    """Lesson diagnostics: teachers, klassen, mainStudentgroupId and the
    per-klasse roster vs. attending distribution."""
    c = _make_client(args)
    response = c.get_student_lesson_period_matrix(
        args.lsid, school_year_id=args.school_year_id)
    matrix = response["result"]
    periods = matrix.get("lessonPeriods", [])
    dates = sorted({p["date"] for p in periods})
    distribution: dict[str, dict] = {}
    for s in matrix.get("allStudents", []):
        key = str(s.get("klasse"))
        d = distribution.setdefault(
            key, {"klasse": s.get("klasse"), "total": 0, "attending": 0,
                  "attendanceCounts": []})
        d["total"] += 1
        att = s.get("attendedPeriods") or []
        if att:
            d["attending"] += 1
            d["attendanceCounts"].append(len(att))
    for d in distribution.values():
        counts = d.pop("attendanceCounts")
        d["termineMin"] = min(counts) if counts else 0
        d["termineMax"] = max(counts) if counts else 0
    info = {
        "lsId": args.lsid,
        "lessonSubject": matrix.get("lessonSubject"),
        "lessonTeachers": matrix.get("lessonTeachers"),
        "lessonKlassen": matrix.get("lessonKlassen"),
        "allKlassen": matrix.get("allKlassen"),
        "mainStudentgroupId": matrix.get("mainStudentgroupId"),
        "startDate": matrix.get("startDate"),
        "endDate": matrix.get("endDate"),
        "periodCount": len(periods),
        "lessonDates": dates,
        "klasseDistribution": sorted(
            distribution.values(),
            key=lambda d: (str(d["klasse"])),
        ),
    }
    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0
    print(f"lsId {args.lsid}: {info['lessonSubject']}  "
          f"{len(periods)} Perioden "
          f"({dates[0] if dates else '-'} .. {dates[-1] if dates else '-'})")
    print(f"  mainStudentgroupId: {info['mainStudentgroupId']}")
    print(f"  lessonTeachers: {info['lessonTeachers']}")
    print(f"  lessonKlassen: {info['lessonKlassen']}")
    print("  Klassen-Roster vs. attending (nur attending > 0; "
          "--json für alles):")
    shown = [d for d in info["klasseDistribution"] if d["attending"] > 0]
    omitted = len(info["klasseDistribution"]) - len(shown)
    for d in shown:
        print(f"    klasse={d['klasse']:>6}  attending {d['attending']}/"
              f"{d['total']}  Termine {d['termineMin']}..{d['termineMax']}")
    if omitted:
        print(f"    (+{omitted} Klassen ohne attending)")
    return 0


def cmd_session_status(args: argparse.Namespace) -> int:
    """Session cache info + live check via the app/data bootstrap."""
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
        return 0 if live["alive"] else 2
    print(f"cache: {cache_path}")
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
    return 2


def cmd_search(args: argparse.Namespace) -> int:
    """Search classes/teachers/students by text (full names included).

    Default (no flags): exact single-query search in one schoolyear —
    behavior and output identical to before. --fallback adds the
    tokenizing merge, --all-years repeats across older schoolyears
    (hits from older years flagged NICHT AKTUELL).
    """
    c = _make_client(args)
    override = args.school_year_id
    sy = c.resolve_schoolyear_id(override=override)
    use_fallback = bool(getattr(args, "fallback", False))
    use_all_years = bool(getattr(args, "all_years", False))
    if not use_fallback and not use_all_years:
        results = c.search_timetable(args.query, school_year_id=sy)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
            return 0
        if not results:
            print("(no results)")
            print("hint: try --fallback (Vor-/Nachname einzeln), "
                  "--all-years (ältere Schuljahre), or "
                  "`students find <name>` (Schüler, auto-fallback).",
                  file=sys.stderr)
            return 0
        for hit in results:
            res = hit.get("resource", {})
            print(
                f"{hit.get('type', '?'):>8}  id={res.get('id'):>6}  "
                f"{res.get('shortName', ''):12} "
                f"{res.get('displayName') or res.get('longName', '')}"
            )
        return 0
    # Flag path: tokenizing and/or multi-year, annotated output.
    years = [sy]
    if use_all_years and override is None:
        years += c.older_schoolyear_ids(sy)
    results: list[dict] = []
    for y in years:
        if use_fallback:
            hits = c.search_timetable_tokens(args.query, school_year_id=y)
        else:
            hits = c.search_timetable(args.query, school_year_id=y)
        results.extend(_annotate_search_hits(hits, c, y, sy))
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    if not results:
        print("(no results)")
        return 0
    for hit in results:
        print(_format_search_hit(hit))
    if any(hit.get("current") is False for hit in results):
        print("ACHTUNG: markierte Treffer sind NICHT AKTUELL — "
              "nur in älteren Schuljahren gefunden.", file=sys.stderr)
    return 0


def _kv_for_class(c: Client, sy: int, needle: int | str,
                  json_out: bool) -> int:
    """KV lookup for one class (id or exact name). Shared by `kv`."""
    res = c.get_klassen(schoolyear_id=sy)
    klassen = res.get("result", []) if isinstance(res, dict) else res
    if isinstance(needle, str) and needle.isdigit():
        needle = int(needle)
    hit = None
    for k in klassen:
        if isinstance(needle, int) and k.get("id") == needle:
            hit = k
            break
        if (isinstance(needle, str)
                and k.get("name", "").lower() == needle.lower()):
            hit = k
            break
    if hit is None:
        print(f"class '{needle}' not found", file=sys.stderr)
        return 2
    teacher_ids = [v for key in ("teacher1", "teacher2", "teacher3")
                   if (v := hit.get(key))]
    info = {
        "classId": hit.get("id"),
        "name": hit.get("name"),
        "longName": hit.get("longName"),
        "teachers": _teacher_names_for_class(c, hit["id"], teacher_ids, sy),
    }
    if json_out:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0
    print(f"{info['name']} ({info['longName']}):")
    for tid, name in info["teachers"].items():
        print(f"  KV: {name} (teacher id {tid})")
    return 0


def cmd_kv(args: argparse.Namespace) -> int:
    """Show the Klassenvorstand (class teacher) of a class.

    Either `<klasse>` (id or name) or `--student <name>`: student ->
    class(es) via students/overview, then KV per class.
    """
    if args.student is None and args.klasse is None:
        print("either KLASSE or --student required", file=sys.stderr)
        return 2
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    if args.student is not None:
        from webuntis_agent.client import (
            student_matches_overview,
            tokenize_search_query,
        )
        tokens = tokenize_search_query(args.student)
        try:
            overview = c.get_students_overview()
        except Exception as e:
            print(f"students/overview failed ({e})", file=sys.stderr)
            return 2
        matches = [s for s in overview.get("students", [])
                   if student_matches_overview(s, tokens)]
        if not matches:
            print(f"no current-roster student matches {args.student!r} "
                  "(try `students find` for former students)",
                  file=sys.stderr)
            return 2
        classes: dict[int, str] = {}
        for s in matches:
            ci = s.get("classInfo") or {}
            if ci.get("id") is not None:
                classes[ci["id"]] = ci.get("name", "")
        print(f"{len(matches)} Schüler-Treffer, {len(classes)} Klasse(n):")
        for s in matches:
            ci = s.get("classInfo") or {}
            name = f"{s.get('firstName', '')} {s.get('lastName', '')}".strip()
            print(f"  id={s.get('id'):>6}  {name}  Klasse {ci.get('name', '?')}")
        if len(classes) > 1:
            print("mehrdeutig: Student gehört zu mehreren Treffer-Klassen — "
                  "KV je Klasse:", file=sys.stderr)
        rc = 0
        for cid, cname in sorted(classes.items(), key=lambda x: str(x[1])):
            print()
            r = _kv_for_class(c, sy, cid if cname == "" else cname, args.json)
            if r != 0:
                rc = r
        return rc
    return _kv_for_class(c, sy, args.klasse, args.json)



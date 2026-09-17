"""CLI entry point for webuntis-agent."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date


def _load_env() -> None:
    try:
        from pathlib import Path
        p = Path(__file__).resolve().parents[2] / ".env"
        if not p.exists():
            return
        aliases = {"user": "WEBUNTIS_USER", "password": "WEBUNTIS_PASSWORD",
                   "school": "WEBUNTIS_SCHOOL", "host": "WEBUNTIS_HOST"}
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            env_key = aliases.get(k.lower(), k.upper())
            os.environ.setdefault(env_key, v.strip())
    except Exception:
        pass


def _session_path() -> str:
    """Persisted-login cache file, next to .env in the repo root."""
    from pathlib import Path
    return str(Path(__file__).resolve().parents[2] / ".webuntis_session.json")


def _make_client(args: argparse.Namespace):
    _load_env()
    from webuntis_agent.client import Client
    c = Client(
        host=os.environ.get("WEBUNTIS_HOST",
                            "https://spengergasse.webuntis.com"),
        school=os.environ.get("WEBUNTIS_SCHOOL", "spengergasse"),
        session_path=_session_path(),
    )
    c.load_cached_session()
    return c


def cmd_login(args: argparse.Namespace) -> int:
    """Log in once and persist the session for all following CLI calls."""
    _load_env()
    from webuntis_agent.client import Client
    c = Client(
        host=os.environ.get("WEBUNTIS_HOST",
                            "https://spengergasse.webuntis.com"),
        school=os.environ.get("WEBUNTIS_SCHOOL", "spengergasse"),
        session_path=_session_path(),
    )
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
    matrix = c.get_student_lesson_period_matrix(
        args.lsid, school_year_id=args.school_year_id)["result"]
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


def _fixed_text(subject: str) -> str | None:
    """Return a fixed text for subjects like SS/BESP that don't need git-log."""
    from webuntis_agent.client import FIXED_TEXT_SUBJECTS
    return FIXED_TEXT_SUBJECTS.get(subject)


def _date_arg(s: str) -> str:
    # accept yyyy-MM-dd
    date.fromisoformat(s)
    return s


def _lesson_details_url(host: str, period_id: int, class_id: int,
                        start_iso: str, end_iso: str,
                        ref_date: str,
                        element_type: int = 1) -> str:
    """Construct a browser-clickable URL for the lesson details view.

    Pattern (from captured browser navigation):
      /timetable/class/lessonDetails/{periodId}/{classId}/{elementType}/
      {startISO}/{endISO}/{bool}?date={refDate}&entityId={classId}
    """
    return (
        f"{host}/timetable/class/lessonDetails/"
        f"{period_id}/{class_id}/{element_type}/"
        f"{start_iso}/{end_iso}/true"
        f"?date={ref_date}&entityId={class_id}"
    )


def _block_bounds(periods: list[dict]) -> tuple[str, str]:
    """Given a list of period entries (same lsId), return (start, end) of
    the whole block in ISO format."""
    starts = [p.get("_start_iso", "") for p in periods if p.get("_start_iso")]
    ends = [p.get("_end_iso", "") for p in periods if p.get("_end_iso")]
    s = min(starts) if starts else ""
    e = max(ends) if ends else ""
    return s, e


def _open_period_entries(c: "object", sy: int, start: str, end: str,
                         filter_: str = "TOPIC_OR_ABSENCE_OPEN") -> list[dict]:
    """Fetch open periods and build enriched, flat period entries.

    Shared by `lehrstoff list`, `lessons` and the lsId resolver.
    """
    data = c.get_open_periods(start, end, filter_=filter_, school_year_id=sy)
    raw = data.get("periods", [])
    entries: list[dict] = []
    blocks: dict[int | None, list[dict]] = {}
    for p in raw:
        per = p.get("period", {})
        cls = per.get("classes", [{}])[0].get("el", {})
        subj = per.get("subject", {}).get("el", {})
        dt = per.get("dtRange", {})
        teachers = [t["el"] for t in per.get("teachers", []) if t.get("el")]
        rooms = []
        for r in per.get("rooms", []):
            el = r.get("el") or {}
            org = (r.get("orgEl") or {}).get("name")
            label = el.get("name", "")
            if org and org != label:
                label = f"{label} (org {org})"
            if label:
                rooms.append(label)
        entry = {
            "periodId": per.get("id"),
            "topicId": p.get("topicId"),
            "class": cls.get("name"),
            "classId": cls.get("id"),
            "subject": subj.get("nameShort"),
            "subjectLong": subj.get("name"),
            "date": (dt.get("start") or "")[:10],
            "time": (dt.get("start") or "")[11:16],
            "_start_iso": (dt.get("start") or "").replace(" ", "T"),
            "_end_iso": (dt.get("end") or "").replace(" ", "T"),
            "lsId": per.get("lsId"),
            "hr": per.get("hr"),
            "teachers": [t.get("name") for t in teachers],
            "teacherShorts": [t.get("nameShort") for t in teachers],
            "rooms": rooms,
        }
        entries.append(entry)
        blocks.setdefault(per.get("lsId"), []).append(entry)
    # Enrich each entry with block bounds + lesson details URL.
    for e in entries:
        siblings = blocks.get(e.get("lsId"), [e])
        bstart, bend = _block_bounds(siblings)
        ref_date = e["date"]
        e["lessonDetailsUrl"] = _lesson_details_url(
            c.host, e["periodId"], e["classId"], bstart, bend, ref_date,
        )
    return entries


def _group_lesson_entries(entries: list[dict]) -> list[dict]:
    """Group period entries by lsId; returns groups sorted by first date."""
    groups: dict[int | None, list[dict]] = {}
    for e in entries:
        groups.setdefault(e.get("lsId"), []).append(e)
    out = []
    for lsid, g in groups.items():
        g_sorted = sorted(g, key=lambda e: (e["date"], e["time"]))
        subj = g_sorted[0].get("subject") or "?"
        subj_long = g_sorted[0].get("subjectLong") or ""
        teachers: list[str] = []
        for e in g_sorted:
            for t in e.get("teachers", []):
                if t and t not in teachers:
                    teachers.append(t)
        shorts: list[str] = []
        for e in g_sorted:
            for t in e.get("teacherShorts", []):
                if t and t not in shorts:
                    shorts.append(t)
        rooms: list[str] = []
        for e in g_sorted:
            for r in e.get("rooms", []):
                if r and r not in rooms:
                    rooms.append(r)
        out.append({
            "lsId": lsid,
            "subject": subj,
            "subjectLong": subj_long,
            "class": g_sorted[0].get("class"),
            "classId": g_sorted[0].get("classId"),
            "periods": len(g_sorted),
            "firstDate": g_sorted[0]["date"],
            "lastDate": g_sorted[-1]["date"],
            "openTopicIds": sorted({e["topicId"] for e in g_sorted
                                    if e.get("topicId")}),
            "teachers": teachers,
            "teacherShorts": shorts,
            "rooms": rooms,
            "entries": g_sorted,
        })
    out.sort(key=lambda g: (g["firstDate"], g["subject"]))
    return out


def cmd_lessons(args: argparse.Namespace) -> int:
    """List the user's lessons for one class, grouped by lesson (lsId)."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    start, end = args.start, args.end
    if start is None or end is None:
        syr = next((y for y in c.get_schoolyears() if int(y["id"]) == sy),
                   None)
        if syr is None:
            print(f"schoolyear {sy} not found", file=sys.stderr)
            return 2
        dr = syr["dateRange"]
        start = start or str(dr["start"])[:10]
        end = end or str(dr["end"])[:10]
    entries = _open_period_entries(c, sy, start, end)
    cls_l = args.classname.lower()
    entries = [e for e in entries
               if (e.get("class") or "").lower() == cls_l]
    if args.subject:
        sl = args.subject.lower()
        entries = [e for e in entries
                   if (e.get("subject") or "").lower().startswith(sl)]
    if not entries:
        print(f"(no lessons for {args.classname}"
              + (f"/{args.subject}" if args.subject else "")
              + f" with open topics/absences in {start}..{end})")
        return 0
    groups = _group_lesson_entries(entries)

    full_by_short: dict[str, str] = {}
    if args.full_names:
        shorts = sorted({t for g in groups for t in g["teacherShorts"]})
        for short in shorts:
            hits = c.search_timetable(short, school_year_id=sy)
            match = next((h["resource"] for h in hits
                          if h.get("type") == "TEACHER"
                          and h["resource"].get("shortName") == short), None)
            if match:
                full_by_short[short] = (match.get("displayName")
                                        or match.get("longName") or short)

    if args.json:
        print(json.dumps({
            "class": args.classname,
            "range": {"start": start, "end": end},
            "lessons": [{k: v for k, v in g.items() if k != "entries"}
                        for g in groups],
            "entries": [{k: v for k, v in e.items()
                         if not k.startswith("_")} for e in entries],
        }, indent=2, ensure_ascii=False))
        return 0
    for g in groups:
        teachers = [full_by_short.get(s, t)
                    for t, s in zip(g["teachers"], g["teacherShorts"])] \
            if args.full_names else g["teachers"]
        print(f"lsId {g['lsId']}  {g['subject']} — {g['subjectLong']}")
        print(f"  {g['class']}  periods={g['periods']}  "
              f"{g['firstDate']} .. {g['lastDate']}  offen={len(g['entries'])}")
        if teachers:
            print(f"  Lehrer: {' + '.join(teachers)}")
        if g["rooms"]:
            print(f"  Räume:  {' + '.join(g['rooms'])}")
    return 0


def cmd_lehrstoff_list(args: argparse.Namespace) -> int:
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    entries = _open_period_entries(c, sy, args.start, args.end)
    if not entries:
        print("[]" if args.json else "(no open periods)")
        return 0
    if args.json:
        clean = [{k: v for k, v in e.items() if not k.startswith("_")}
                 for e in entries]
        print(json.dumps(clean, indent=2, ensure_ascii=False))
        return 0
    for e in entries:
        print(
            f"{e['periodId']:>10}  {e['date']}T{e['time']}  "
            f"{e['class'] or '':8} {e['subject'] or '':8} "
            f"topicId={e['topicId']}"
        )
    return 0


def cmd_lehrstoff_get(args: argparse.Namespace) -> int:
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    data = c.get_lesson_topic(args.period, school_year_id=sy)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def _read_text_arg(args: argparse.Namespace) -> str:
    """Resolve --text / --text-file / --text-stdin (exactly one required)."""
    sources = [
        ("--text", getattr(args, "text", None)),
        ("--text-file", getattr(args, "text_file", None)),
    ]
    if getattr(args, "text_stdin", False):
        sources.append(("--text-stdin", True))
    present = [(n, v) for n, v in sources if v]
    if not present:
        raise SystemExit("error: one of --text / --text-file / --text-stdin required")
    if len(present) > 1:
        raise SystemExit(
            f"error: only one of --text / --text-file / --text-stdin allowed "
            f"(got {[n for n, _ in present]})"
        )
    name, _ = present[0]
    if name == "--text":
        return args.text
    if name == "--text-file":
        from pathlib import Path
        return Path(args.text_file).read_text(encoding="utf-8")
    import sys
    return sys.stdin.read()


def cmd_lehrstoff_set(args: argparse.Namespace) -> int:
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    if args.topic_id is None:
        topic = c.get_lesson_topic(args.period, school_year_id=sy)
        pts = topic.get("periodTopics", [])
        if pts and pts[0].get("topic"):
            args.topic_id = pts[0]["topic"]["id"]
            print(f"resolved topic_id={args.topic_id}")
        else:
            args.topic_id = 0  # Neuanlage: server creates new topic row
    text = _read_text_arg(args)
    res = c.set_lesson_topic(
        args.period, args.topic_id, text,
        school_year_id=sy,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_lehrstoff_batch_set(args: argparse.Namespace) -> int:
    """Read a JSON file [{periodId, topicId, text, classId, start, end,
    date}, ...] and set each. Outputs a lesson-details URL per entry
    when classId + start + end + date are present. Sleeps --delay seconds
    between PUTs to avoid triggering rate-limiting.
    """
    from pathlib import Path
    items = json.loads(Path(args.file).read_text(encoding="utf-8"))
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    results: list[dict] = []
    for i, it in enumerate(items):
        if i and args.delay > 0:
            time.sleep(args.delay)
        pid = it["periodId"]
        tid = it.get("topicId")
        text = it["text"]
        if tid is None:
            topic = c.get_lesson_topic(pid, school_year_id=sy)
            pts = topic.get("periodTopics", [])
            if pts and pts[0].get("topic"):
                tid = pts[0]["topic"]["id"]
            else:
                tid = 0  # Neuanlage: server creates new topic row
        entry: dict = {"periodId": pid}
        if tid is None:
            entry["ok"] = False
            entry["error"] = "no topicId resolved"
            results.append(entry)
            continue
        try:
            res = c.set_lesson_topic(pid, tid, text, school_year_id=sy)
            topics = res.get("topics", [])
            entry["ok"] = True
            entry["updated"] = [t.get("id") for t in topics]
            cls_id = it.get("classId")
            start = it.get("start")
            end = it.get("end")
            ref_date = it.get("date") or (start or "")[:10]
            if cls_id and start and end:
                entry["lessonDetailsUrl"] = _lesson_details_url(
                    c.host, pid, cls_id, start, end, ref_date,
                )
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)
        results.append(entry)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(results)} updated", file=sys.stderr)
    return 0 if ok == len(results) else 1


def cmd_lehrstoff_from_git(args: argparse.Namespace) -> int:
    from webuntis_agent.client import repos_for_subject
    from webuntis_agent.gitlog import (
        get_commit_diff_by_name,
        get_commits_for_class,
        format_commits,
    )
    repos = repos_for_subject(args.subject)
    if not repos:
        print(
            f"WARNING: subject '{args.subject}' not in SUBJECT_REPO_MAP — "
            "add it in src/webuntis_agent/client.py",
            file=sys.stderr,
        )
        return 3
    d = date.fromisoformat(args.date)
    commits = get_commits_for_class(
        args.class_name, d, repo_filter=repos,
    )
    if not commits:
        text = f"(kein Unterricht gefunden für {args.class_name} am {args.date})"
        if args.dry_run:
            print(f"repos searched: {repos}")
            print(f"would set: {text}")
            return 0
    else:
        print(format_commits(commits))
        print("---")
        for ci in commits:
            diff = get_commit_diff_by_name(ci.repo, ci.hash)
            print(f"=== diff {ci.repo} {ci.hash[:8]} ===")
            print(diff)
            print()
        msgs = [ci.message for ci in commits if ci.message]
        text = "; ".join(dict.fromkeys(msgs))[:240] if msgs else "(no messages)"
        if args.dry_run:
            print(f"would set period={args.period} text={text!r}")
            return 0
    if args.period is None or args.topic_id is None:
        print("need --period and --topic-id (or --dry-run)", file=sys.stderr)
        return 2
    client = _make_client(args)
    sy = client.resolve_schoolyear_id(override=args.school_year_id)
    res = client.set_lesson_topic(args.period, args.topic_id, text,
                             school_year_id=sy)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def _fetch_open_periods(args: argparse.Namespace):
    """Shared helper: create client, resolve schoolyear, fetch periods."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    data = c.get_open_periods(args.start, args.end, school_year_id=sy)
    return c, sy, data.get("periods", [])


def _period_summary(p: dict) -> dict:
    """Extract a flat dict from a raw open-period entry."""
    per = p.get("period", {})
    cls = per.get("classes", [{}])[0].get("el", {})
    subj = per.get("subject", {}).get("el", {})
    dt = per.get("dtRange", {})
    return {
        "periodId": per.get("id"),
        "topicId": p.get("topicId"),
        "class": cls.get("name"),
        "classId": cls.get("id"),
        "subject": subj.get("nameShort"),
        "subjectLong": subj.get("name"),
        "date": (dt.get("start") or "")[:10],
        "time": (dt.get("start") or "")[11:16],
        "startIso": dt.get("start"),
        "endIso": dt.get("end"),
        "lsId": per.get("lsId"),
        "hr": per.get("hr"),
        "topicNeeded": p.get("topicNeeded"),
        "absCheckNeeded": p.get("absCheckNeeded"),
    }


def cmd_lehrstoff_status(args: argparse.Namespace) -> int:
    """Overview of open periods grouped by subject, class, month."""
    from collections import Counter, defaultdict
    c, sy, periods = _fetch_open_periods(args)
    if not periods:
        print("[]" if args.json else "(no open periods)")
        return 0
    summaries = [_period_summary(p) for p in periods]
    if args.json:
        print(json.dumps(summaries, indent=2, ensure_ascii=False))
        return 0
    by_subject = Counter(s["subject"] for s in summaries)
    print(f"total open periods: {len(summaries)}")
    print("\n--- by subject ---")
    for subj, cnt in by_subject.most_common():
        print(f"  {subj or '':8} {cnt}")
    combos = defaultdict(int)
    for s in summaries:
        combos[(s["class"], s["subject"])] += 1
    print(f"\n--- by class + subject ---")
    for (cls, subj), cnt in sorted(combos.items()):
        print(f"  {cls or '':8} {subj or '':8} {cnt:3}")
    return 0


def cmd_lehrstoff_fill(args: argparse.Namespace) -> int:
    """Fetch open periods, load git commits + diffs per block, output
    dry-run JSON for the skill/agent to formulate final texts.

    With --dry-run (default): prints JSON with raw data + proposed text.
    Without --dry-run: reads a confirmed batch JSON (--file) and submits.
    """
    from collections import defaultdict
    from pathlib import Path
    from webuntis_agent.client import repos_for_subject, FIXED_TEXT_SUBJECTS
    from webuntis_agent.gitlog import (
        get_commit_diff_by_name,
        get_commits_for_class,
    )

    c, sy, periods = _fetch_open_periods(args)
    if not periods:
        print("[]" if args.json else "(no open periods)")
        return 0

    summaries = [_period_summary(p) for p in periods]
    # group by lesson (lsId) — one PUT updates all block partners; fall
    # back to (class, subject, date) only when lsId is missing
    blocks: dict[tuple, list[dict]] = defaultdict(list)
    for s in summaries:
        lsid = s.get("lsId")
        key = ("lsid", lsid) if lsid is not None else \
            ("fallback", s["class"], s["subject"], s["date"])
        blocks[key].append(s)

    if not args.dry_run:
        if not args.file:
            print("error: --file required (confirmed batch JSON) without --dry-run",
                  file=sys.stderr)
            return 2
        items = json.loads(Path(args.file).read_text(encoding="utf-8"))
        results: list[dict] = []
        for i, it in enumerate(items):
            if i and args.delay > 0:
                time.sleep(args.delay)
            pid = it["periodId"]
            tid = it.get("topicId")
            text = it["text"]
            if tid is None:
                topic = c.get_lesson_topic(pid, school_year_id=sy)
                pts = topic.get("periodTopics", [])
                if pts and pts[0].get("topic"):
                    tid = pts[0]["topic"]["id"]
                else:
                    tid = 0
            entry: dict = {"periodId": pid}
            try:
                res = c.set_lesson_topic(pid, tid, text, school_year_id=sy)
                entry["ok"] = True
                entry["updated"] = [t.get("id") for t in res.get("topics", [])]
            except Exception as e:
                entry["ok"] = False
                entry["error"] = str(e)
            results.append(entry)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        ok = sum(1 for r in results if r.get("ok"))
        print(f"\n{ok}/{len(results)} updated", file=sys.stderr)
        return 0 if ok == len(results) else 1

    # dry-run: build raw data for the skill/agent
    blocks_out: list[dict] = []
    skipped: list[dict] = []
    for key, block_periods in blocks.items():
        p0 = block_periods[0]
        cls = p0["class"]
        subj = p0["subject"]
        d = p0["date"]
        entry = {
            "periodId": p0["periodId"],
            "topicId": p0["topicId"],
            "class": cls,
            "classId": p0["classId"],
            "subject": subj,
            "subjectLong": p0["subjectLong"],
            "date": d,
            "time": p0["time"],
            "lsId": p0["lsId"],
            "blockPeriods": [bp["periodId"] for bp in block_periods],
        }
        # real dtRange times; block start = earliest, end = latest
        starts = [bp["startIso"] for bp in block_periods if bp.get("startIso")]
        ends = [bp["endIso"] for bp in block_periods if bp.get("endIso")]
        start_iso = min(starts) if starts else f"{d}T{p0['time']}:00"
        if ends:
            end_iso = max(ends)
        else:
            end_iso = start_iso
            entry["warning"] = "no dtRange.end in open-periods payload"
        entry["start"] = start_iso
        entry["end"] = end_iso

        if subj in FIXED_TEXT_SUBJECTS:
            entry["source"] = "fixed"
            entry["proposedText"] = FIXED_TEXT_SUBJECTS[subj]
            entry["commits"] = []
            blocks_out.append(entry)
            continue

        repos = repos_for_subject(subj)
        if not repos:
            entry["source"] = "skipped"
            entry["proposedText"] = None
            entry["commits"] = []
            entry["warning"] = (
                f"subject '{subj}' not in SUBJECT_REPO_MAP — "
                "add it in src/webuntis_agent/client.py"
            )
            skipped.append(entry)
            continue

        commits = get_commits_for_class(
            cls, date.fromisoformat(d), repo_filter=repos,
        )
        commit_data: list[dict] = []
        for ci in commits:
            commit_data.append({
                "repo": ci.repo,
                "hash": ci.hash,
                "date": ci.date,
                "message": ci.message,
                "files": ci.files[:5],
                "diff": get_commit_diff_by_name(ci.repo, ci.hash),
            })
        entry["commits"] = commit_data
        if commit_data:
            entry["source"] = "git"
            msgs = [cd["message"] for cd in commit_data if cd["message"]]
            entry["proposedText"] = (
                "; ".join(dict.fromkeys(msgs))[:240] if msgs else "(no messages)"
            )
        else:
            entry["source"] = "dummy"
            entry["proposedText"] = (
                f"(kein Unterricht gefunden für {cls} am {d})"
            )
        blocks_out.append(entry)

    blocks_out.sort(key=lambda e: e.get("start") or "")
    output = {"blocks": blocks_out, "skipped": skipped}
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print(
        f"\n{len(blocks_out)} blocks ({len(skipped)} skipped) — "
        f"review, formulate texts, then run batch-set --file <json>",
        file=sys.stderr,
    )
    return 0


def cmd_lehrstoff_verify(args: argparse.Namespace) -> int:
    """Check which open periods truly have no topic text vs only missing absence check."""
    c, sy, periods = _fetch_open_periods(args)
    if not periods:
        print("[]" if args.json else "(no open periods)")
        return 0

    truly_empty: list[dict] = []
    has_text: list[dict] = []
    for p in periods:
        per = p.get("period", {})
        pid = per.get("id")
        summary = _period_summary(p)
        try:
            topic = c.get_lesson_topic(pid, school_year_id=sy)
            pts = topic.get("periodTopics", [])
            if pts and pts[0].get("topic") and pts[0]["topic"].get("text"):
                summary["topicText"] = pts[0]["topic"]["text"][:80]
                has_text.append(summary)
            else:
                summary["topicText"] = None
                truly_empty.append(summary)
        except Exception as e:
            summary["error"] = str(e)
            truly_empty.append(summary)

    if args.json:
        print(json.dumps({
            "trulyEmpty": truly_empty,
            "hasText": has_text,
        }, indent=2, ensure_ascii=False))
        return 0

    print(f"open periods: {len(periods)}")
    print(f"  truly empty (no topic text): {len(truly_empty)}")
    print(f"  has text (only absence check missing): {len(has_text)}")
    if truly_empty:
        print("\n--- truly empty ---")
        for s in truly_empty:
            print(f"  {s['periodId']:>10} {s['class'] or '':6} "
                  f"{s['subject'] or '':6} {s['date']}")
    if has_text:
        print(f"\n--- has text ({len(has_text)}) — first 5 ---")
        for s in has_text[:5]:
            print(f"  {s['periodId']:>10} {s['class'] or '':6} "
                  f"{s['subject'] or '':6} {s['date']} "
                  f"text={s.get('topicText', '')!r}")
    return 0


def cmd_lehrstoff_fill_fixed(args: argparse.Namespace) -> int:
    """Fill all open periods that have a fixed-text subject (SS, BESP)."""
    from webuntis_agent.client import FIXED_TEXT_SUBJECTS
    c, sy, periods = _fetch_open_periods(args)
    if not periods:
        print("[]" if args.json else "(no open periods)")
        return 0

    fixed_periods = []
    for p in periods:
        s = _period_summary(p)
        if s["subject"] in FIXED_TEXT_SUBJECTS:
            entry = dict(s)
            entry["text"] = FIXED_TEXT_SUBJECTS[s["subject"]]
            fixed_periods.append(entry)

    if not fixed_periods:
        print("(no fixed-text subjects in open periods)" if not args.json
              else "[]")
        return 0

    if args.dry_run:
        if args.json:
            print(json.dumps(fixed_periods, indent=2, ensure_ascii=False))
        else:
            print(f"{len(fixed_periods)} fixed-text periods (DRY RUN):")
            for e in fixed_periods:
                print(f"  {e['periodId']:>10} {e['class'] or '':6} "
                      f"{e['subject'] or '':6} {e['date']} "
                      f"text={e['text']!r}")
            print("Submit with --no-dry-run.", file=sys.stderr)
        return 0

    results: list[dict] = []
    for i, e in enumerate(fixed_periods):
        if i and args.delay > 0:
            time.sleep(args.delay)
        pid = e["periodId"]
        tid = e.get("topicId") or 0
        entry: dict = {"periodId": pid}
        try:
            res = c.set_lesson_topic(
                pid, tid, e["text"], school_year_id=sy,
            )
            entry["ok"] = True
            entry["updated"] = [t.get("id") for t in res.get("topics", [])]
        except Exception as ex:
            entry["ok"] = False
            entry["error"] = str(ex)
        results.append(entry)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(results)} fixed-text periods filled", file=sys.stderr)
    return 0 if ok == len(results) else 1


def _format_search_hit(r_: dict) -> str:
    res = r_.get("resource", {})
    line = (
        f"{r_.get('type', '?'):>8}  id={res.get('id'):>6}  "
        f"{res.get('shortName', ''):12} "
        f"{res.get('displayName') or res.get('longName', '')}"
    )
    if r_.get("searchNote"):
        line += f"  [{r_['searchNote']}]"
    if r_.get("current") is False:
        sy = r_.get("schoolYear") or {}
        line += (f"  [SJ {sy.get('name', '?')} (id {sy.get('id', '?')})"
                 f" — NICHT AKTUELL]")
    return line


def _annotate_search_hits(hits: list[dict], c: "object",
                          school_year_id: int, current_id: int) -> list[dict]:
    """Additive annotation for fallback/multi-year search output.

    Adds `schoolYear: {id, name}` + `current: bool` to each hit (shallow
    copies — server payload untouched). The default single-year path
    does NOT call this, so its output is byte-identical to before.
    """
    label = c.schoolyear_label(school_year_id)
    out = []
    for h in hits:
        h = dict(h)
        h["schoolYear"] = {"id": school_year_id, "name": label}
        h["current"] = (school_year_id == current_id)
        out.append(h)
    return out


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
        for r_ in results:
            res = r_.get("resource", {})
            print(
                f"{r_.get('type', '?'):>8}  id={res.get('id'):>6}  "
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
    for r_ in results:
        print(_format_search_hit(r_))
    if any(r_.get("current") is False for r_ in results):
        print("ACHTUNG: markierte Treffer sind NICHT AKTUELL — "
              "nur in älteren Schuljahren gefunden.", file=sys.stderr)
    return 0


def cmd_students_find(args: argparse.Namespace) -> int:
    """Find students by name with tokenizing + automatic year fallback.

    Unlike `search` (current schoolyear default), this command searches
    the current year first and then up to 3 older years automatically —
    former students are found without extra flags. Hits from older
    years are DEUTLICH als NICHT AKTUELL gekennzeichnet (text + JSON
    `current: false`). --school-year-id pins to a single year (no
    fallback). The current year is additionally matched against
    students/overview (full first/last names + class info).
    """
    from webuntis_agent.client import (
        student_matches_overview,
        tokenize_search_query,
    )
    c = _make_client(args)
    override = args.school_year_id
    if override is not None:
        years = [override]
        current_id = override
    else:
        current_id = c.resolve_schoolyear_id()
        years = [current_id] + c.older_schoolyear_ids(current_id)
    tokens = tokenize_search_query(args.name)
    cur_label = c.schoolyear_label(current_id)
    students: list[dict] = []
    seen_ids: set[int] = set()
    for y in years:
        label = c.schoolyear_label(y)
        current = (y == current_id)
        hits = [h for h in c.search_timetable_tokens(
                    args.name, school_year_id=y)
                if h.get("type") == "STUDENT"]
        for h in hits:
            res = h.get("resource", {})
            sid = res.get("id")
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            entry: dict = {
                "id": sid,
                "shortName": res.get("shortName", ""),
                "displayName": (res.get("displayName")
                                or res.get("longName", "")),
                "schoolYear": {"id": y, "name": label},
                "current": current,
            }
            if h.get("searchNote"):
                entry["searchNote"] = h["searchNote"]
            students.append(entry)
        if current:
            # Enrich the current year with the full roster (first/last
            # names + class), which the anonymized search lacks.
            try:
                overview = c.get_students_overview()
            except Exception as e:
                print(f"warning: students/overview failed ({e})",
                      file=sys.stderr)
                overview = {}
            for s in overview.get("students", []):
                if not student_matches_overview(s, tokens):
                    continue
                if s.get("id") in seen_ids:
                    for e in students:
                        if e["id"] == s.get("id"):
                            e["firstName"] = s.get("firstName", "")
                            e["lastName"] = s.get("lastName", "")
                            ci = s.get("classInfo") or {}
                            e["class"] = ci.get("name", "")
                            e["classId"] = ci.get("id")
                            break
                    continue
                seen_ids.add(s.get("id"))
                ci = s.get("classInfo") or {}
                students.append({
                    "id": s.get("id"),
                    "shortName": s.get("shortName", ""),
                    "displayName": s.get("lastName", ""),
                    "firstName": s.get("firstName", ""),
                    "lastName": s.get("lastName", ""),
                    "class": ci.get("name", ""),
                    "classId": ci.get("id"),
                    "schoolYear": {"id": y, "name": label},
                    "current": True,
                    "searchNote": "overview-match",
                })
    if getattr(args, "klasse", None):
        kl = args.klasse.lower()
        students = [s for s in students
                    if (s.get("class") or "").lower() == kl
                    or (s.get("shortName") or "").lower() == kl]
    if args.json:
        print(json.dumps({
            "query": args.name,
            "currentSchoolYear": {"id": current_id, "name": cur_label},
            "yearsSearched": years,
            "students": students,
        }, indent=2, ensure_ascii=False))
        return 0
    if not students:
        print("(no results)")
        return 0
    current_hits = [s for s in students if s.get("current")]
    old_hits = [s for s in students if not s.get("current")]
    print(f"{len(students)} Treffer für {args.name!r} "
          f"(SJ {cur_label} + Fallback {len(years) - 1} ältere):")
    for s in current_hits:
        name = (f"{s.get('firstName', '')} {s.get('lastName', '')}".strip()
                or s.get("displayName", ""))
        cls = f" — Klasse {s['class']}" if s.get("class") else ""
        note = f"  [{s['searchNote']}]" if s.get("searchNote") else ""
        print(f"  STUDENT  id={s['id']:>6}  {s.get('shortName', ''):12} "
              f"{name}{cls}{note}")
    for s in old_hits:
        sy = s.get("schoolYear") or {}
        name = (f"{s.get('firstName', '')} {s.get('lastName', '')}".strip()
                or s.get("displayName", ""))
        note = f"  [{s['searchNote']}]" if s.get("searchNote") else ""
        print(f"  STUDENT  id={s['id']:>6}  {s.get('shortName', ''):12} "
              f"{name}  [SJ {sy.get('name', '?')} (id {sy.get('id', '?')})"
              f" — NICHT AKTUELL]{note}")
    if old_hits and not current_hits:
        print("ACHTUNG: aktuell NICHT im System — nur Treffer aus "
              "älteren Schuljahren.", file=sys.stderr)
    elif old_hits:
        print("Hinweis: markierte Treffer sind NICHT AKTUELL.",
              file=sys.stderr)
    return 0


def _teacher_names_for_class(c: "object", class_id: int,
                             teacher_ids: list[int],
                             school_year_id: int | None) -> dict[int, str]:
    """Resolve teacher ids -> display names via weekly timetable short
    names + timetable search (getTeachers is 403 for teacher accounts)."""
    from datetime import date as _date, timedelta as _timedelta
    short_by_id: dict[int, str] = {}
    probe = _date.today()
    for _ in range(4):
        try:
            elements = c.get_weekly_timetable_elements(
                class_id, probe.isoformat())
        except Exception:
            elements = []
        for el in elements:
            if el.get("type") == 2 and el.get("id") in teacher_ids:
                short_by_id[el["id"]] = el.get("name", "")
        if all(t in short_by_id for t in teacher_ids):
            break
        probe -= _timedelta(days=7)
    out: dict[int, str] = {}
    for tid in teacher_ids:
        short = short_by_id.get(tid, "")
        if not short:
            out[tid] = f"(id {tid}, Kürzel nicht im Stundenplan gefunden)"
            continue
        hits = c.search_timetable(short, school_year_id=school_year_id)
        match = next(
            (h["resource"] for h in hits
             if h.get("type") == "TEACHER" and h["resource"].get("id") == tid),
            None)
        out[tid] = (match.get("displayName") or match.get("longName", short)
                    if match else short)
    return out


def _kv_for_class(c: "object", sy: int, needle: int | str,
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


def _resolve_lsid_from_class_subject(c: "object", sy: int,
                                     class_name: str, subject: str) -> int:
    """Find the lsId of a (class, subject) lesson via open periods.

    Scans a window around today (7 days back, 13 ahead). Case-
    insensitive matching; subject falls back to a prefix match. Returns
    the single matching lsId or raises RuntimeError with candidates.
    """
    from datetime import date as _date, timedelta as _timedelta
    start = (_date.today() - _timedelta(days=7)).isoformat()
    end = (_date.today() + _timedelta(days=13)).isoformat()
    entries = _open_period_entries(c, sy, start, end)
    cls_l = class_name.lower()
    subj_l = subject.lower()
    matches: dict[int, list[str]] = {}
    for e in entries:
        if (e["class"] or "").lower() != cls_l:
            continue
        subj = e["subject"] or ""
        if not (subj.lower() == subj_l
                or subj.lower().startswith(subj_l)
                or subj_l.startswith(subj.lower())):
            continue
        if e["lsId"] is not None:
            matches.setdefault(e["lsId"], []).append(e["date"])
    if not matches:
        avail = sorted({(e["class"] or "", e["subject"] or "")
                        for e in entries})
        hints = ", ".join(f"{a}/{b}" for a, b in avail if a.lower() == cls_l)
        raise RuntimeError(
            f"no lesson found for {class_name}/{subject} in "
            f"{start}..{end}" + (f"; available for {class_name}: {hints}"
                                 if hints else ""))
    if len(matches) > 1:
        cands = "; ".join(
            f"lsId={lsid} ({', '.join(sorted(set(ds)))})"
            for lsid, ds in sorted(matches.items()))
        raise RuntimeError(
            f"ambiguous lesson for {class_name}/{subject}: {cands}")
    return next(iter(matches))


def cmd_students_list(args: argparse.Namespace) -> int:
    """Dump the attendance matrix of a lesson (per-student dates).

    The lesson is given by --lsid, or resolved from positional
    CLASS SUBJECT (e.g. `students list 2AHWII SWP1x`) via the open
    periods of a window around today.
    """
    c = _make_client(args)
    lsid = args.lsid
    if lsid is None:
        if not args.class_name or not args.subject:
            print("either --lsid or CLASS SUBJECT are required",
                  file=sys.stderr)
            return 2
        sy = c.resolve_schoolyear_id(override=args.school_year_id)
        try:
            lsid = _resolve_lsid_from_class_subject(
                c, sy, args.class_name, args.subject)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"resolved {args.class_name}/{args.subject} -> lsId {lsid}",
              file=sys.stderr)
    matrix = c.get_student_lesson_period_matrix(
        lsid, school_year_id=args.school_year_id)["result"]
    dates = sorted({p["date"] for p in matrix["lessonPeriods"]})
    students = matrix["allStudents"]
    if args.class_id is not None:
        students = [s for s in students if s["klasse"] == args.class_id]
    if args.attending_only:
        students = [s for s in students if s["attendedPeriods"]]
    if args.json:
        print(json.dumps({
            "lsId": lsid,
            "mainStudentgroupId": matrix["mainStudentgroupId"],
            "lessonDates": dates,
            "students": [
                {"id": s["id"], "name": s["name"], "klasse": s["klasse"],
                 "attendedPeriods": s["attendedPeriods"]}
                for s in students
            ],
        }, indent=2, ensure_ascii=False))
        return 0
    if not args.all and not args.attending_only:
        attending = [s for s in students if s["attendedPeriods"]]
        print(f"(text view: attending only, {len(attending)}/{len(students)} "
              f"shown; --all or --json for everything)")
        students = attending
    print(f"lsId {lsid} (mainStudentgroupId {matrix['mainStudentgroupId']}): "
          f"{len(dates)} lesson dates, {len(students)} students listed")
    for s in students:
        n = len(s["attendedPeriods"])
        note = "alle" if n == len(dates) else str(n)
        print(f"  {s['id']:>6}  {s['name']:32} klasse={s['klasse']:>5}  "
              f"Termine: {note}")
    return 0


def cmd_students_add(args: argparse.Namespace) -> int:
    """Add a student to a lesson's attendance (Schüler-Aufnahme).

    Loads the student-lesson-period matrix for the lesson, sets the
    student's attendedPeriods to all lesson dates, and submits the
    combined payload (lesson class students unchanged + the added
    student). --dry-run (default) writes the payload JSON to --out and
    does NOT submit.
    """
    from pathlib import Path
    c = _make_client(args)
    matrix = c.get_student_lesson_period_matrix(
        args.lsid, school_year_id=args.school_year_id)
    result = matrix["result"]
    all_students = result["allStudents"]
    lesson_dates = sorted({p["date"] for p in result["lessonPeriods"]})

    # resolve the added student by id or name search
    target = None
    if args.student_id:
        target = next((s for s in all_students if s["id"] == args.student_id), None)
        if target is None:
            print(f"student id {args.student_id} not found in matrix",
                  file=sys.stderr)
            return 2
    else:
        needle = args.student_name.lower()
        hits = [s for s in all_students
                if needle in s["name"].lower()]
        if len(hits) != 1:
            for h in hits:
                print(f"  candidate: id={h['id']} {h['name']} klasse={h['klasse']}",
                      file=sys.stderr)
            print(f"student name '{args.student_name}' matched {len(hits)} students; "
                  "use --student-id", file=sys.stderr)
            return 2
        target = hits[0]

    # students of the lesson's class (unchanged) + the added student
    lesson_class = args.class_id
    students_payload = [
        {"id": s["id"], "attendedPeriods": list(s["attendedPeriods"])}
        for s in all_students if s["klasse"] == lesson_class
    ]
    target_entry = {"id": target["id"], "attendedPeriods": lesson_dates}
    students_payload.append(target_entry)

    payload = {
        "mainStudentgroupId": result["mainStudentgroupId"],
        "lessonId": args.lsid,
        "students": students_payload,
        "startDate": result["startDate"],
        "endDate": result["endDate"],
    }

    summary = {
        "student": target,
        "mainStudentgroupId": result["mainStudentgroupId"],
        "lessonDates": lesson_dates,
        "payloadStudents": len(students_payload),
        "payload": payload if args.verbose else "(use --verbose to dump)",
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8")
        summary["writtenTo"] = args.out

    if args.dry_run:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print(
            f"\nDRY RUN: {target['name']} (id={target['id']}) would attend "
            f"{len(lesson_dates)} lesson dates of lesson {args.lsid}; "
            f"payload has {len(students_payload)} students "
            f"(class {lesson_class} unchanged). "
            f"Submit with --no-dry-run.", file=sys.stderr)
        return 0

    res = c.submit_student_lesson_period_data(
        payload["lessonId"], payload["mainStudentgroupId"],
        payload["students"], payload["startDate"], payload["endDate"],
        school_year_id=args.school_year_id,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_students_edit(args: argparse.Namespace) -> int:
    """Edit a lesson's attendance: add and/or remove external students.

    Builds the full students payload (lesson class students unchanged,
    other attending students unchanged, removed students set to
    attendedPeriods=[], added students set to all lesson dates) and
    submits it via submitStudentLessonPeriodData. --dry-run (default)
    writes the payload JSON to --out and does NOT submit.
    """
    from pathlib import Path
    c = _make_client(args)
    matrix = c.get_student_lesson_period_matrix(
        args.lsid, school_year_id=args.school_year_id)
    result = matrix["result"]
    all_students = result["allStudents"]
    lesson_dates = sorted({p["date"] for p in result["lessonPeriods"]})

    add_ids = args.add_student_id or []
    remove_ids = args.remove_student_id or []
    if not add_ids and not remove_ids:
        print("nothing to do: pass --add-student-id and/or "
              "--remove-student-id", file=sys.stderr)
        return 2
    overlap = set(add_ids) & set(remove_ids)
    if overlap:
        print(f"ids both added and removed: {sorted(overlap)}",
              file=sys.stderr)
        return 2
    by_id = {s["id"]: s for s in all_students}
    for sid in add_ids + remove_ids:
        if sid not in by_id:
            print(f"student id {sid} not found in matrix", file=sys.stderr)
            return 2

    keep = [
        {"id": s["id"], "attendedPeriods": list(s["attendedPeriods"])}
        for s in all_students
        if s["id"] not in remove_ids
        and (s["klasse"] == args.class_id or s["attendedPeriods"])
    ]
    for sid in remove_ids:
        keep.append({"id": sid, "attendedPeriods": []})
    for sid in add_ids:
        keep.append({"id": sid, "attendedPeriods": lesson_dates})

    payload = {
        "mainStudentgroupId": result["mainStudentgroupId"],
        "lessonId": args.lsid,
        "students": keep,
        "startDate": result["startDate"],
        "endDate": result["endDate"],
    }

    summary = {
        "added": [by_id[sid]["name"] for sid in add_ids],
        "removed": [by_id[sid]["name"] for sid in remove_ids],
        "mainStudentgroupId": result["mainStudentgroupId"],
        "lessonDates": lesson_dates,
        "payloadStudents": len(keep),
        "payload": payload if args.verbose else "(use --verbose to dump)",
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8")
        summary["writtenTo"] = args.out

    if args.dry_run:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print(
            f"\nDRY RUN: +{[by_id[i]['name'] for i in add_ids]} "
            f"-{[by_id[i]['name'] for i in remove_ids]} "
            f"on lesson {args.lsid} ({len(lesson_dates)} lesson dates); "
            f"payload has {len(keep)} students. "
            f"Submit with --no-dry-run.", file=sys.stderr)
        return 0

    res = c.submit_student_lesson_period_data(
        payload["lessonId"], payload["mainStudentgroupId"],
        payload["students"], payload["startDate"], payload["endDate"],
        school_year_id=args.school_year_id,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_check_absences(args: argparse.Namespace) -> int:
    """Check absences for a single period."""
    c = _make_client(args)
    res = c.check_absences(args.period)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_batch_check_absences(args: argparse.Namespace) -> int:
    """Check absences for multiple periods from a JSON file.

    JSON format: [{"periodId": 123}, ...] (only periodId needed).
    """
    from pathlib import Path
    items = json.loads(Path(args.file).read_text(encoding="utf-8"))
    c = _make_client(args)
    results: list[dict] = []
    for i, it in enumerate(items):
        if i and args.delay > 0:
            time.sleep(args.delay)
        pid = it["periodId"]
        entry: dict = {"periodId": pid}
        try:
            res = c.check_absences(pid)
            entry["ok"] = res.get("success", False)
            entry["result"] = res
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)
        results.append(entry)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(results)} absences checked", file=sys.stderr)
    return 0 if ok == len(results) else 1


def cmd_check_all_absences(args: argparse.Namespace) -> int:
    """Fetch all open periods and check absences for every one that needs it."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    data = c.get_open_periods(args.start, args.end, school_year_id=sy)
    periods = data.get("periods", [])
    need_check = [p for p in periods if p.get("absCheckNeeded")]
    print(f"open periods: {len(periods)}, needing absence check: {len(need_check)}",
          file=sys.stderr)
    results: list[dict] = []
    for i, p in enumerate(need_check):
        if i and args.delay > 0:
            time.sleep(args.delay)
        pid = p.get("period", {}).get("id")
        entry: dict = {"periodId": pid}
        try:
            res = c.check_absences(pid)
            entry["ok"] = res.get("success", False)
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)
        results.append(entry)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(need_check)} absences checked", file=sys.stderr)
    return 0 if ok == len(need_check) else 1


def main() -> int:
    p = argparse.ArgumentParser(prog="webuntis-agent")
    p.add_argument("--school-year-id", type=int, default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="run the CDP recorder")
    rec.add_argument("--host", default="localhost",
                     help="CDP host of the browser (default localhost)")
    rec.add_argument("--port", type=int, default=9222,
                     help="CDP port of the browser (default 9222)")
    rec.add_argument("--domain", default="spengergasse.webuntis.com",
                     help="WebUntis domain to filter requests on")
    sub.add_parser("cookies", help="dump harvested cookies")

    sub.add_parser(
        "login",
        help="log in once and cache the session for all following calls")
    login_parser = sub.choices["login"]
    login_parser.set_defaults(func=cmd_login)

    sub.add_parser(
        "logout",
        help="invalidate the session and delete the session cache")
    sub.choices["logout"].set_defaults(func=cmd_logout)

    se = sub.add_parser(
        "search", help="search classes/teachers/students (full names)")
    se.add_argument("query")
    se.add_argument("--json", action="store_true")
    se.add_argument("--fallback", action="store_true",
                    help="tokenizing fallback: Vor-/Nachname einzeln "
                         "suchen und zusammenführen (findet z.B. "
                         "'Erika Muster' via Einzelteile + "
                         "Kurzname-Heuristik)")
    se.add_argument("--all-years", action="store_true",
                    help="bei Leerstand bzw. zusätzlich ältere Schuljahre "
                         "durchsuchen (Treffer als NICHT AKTUELL "
                         "gekennzeichnet; --school-year-id pinnt auf ein "
                         "Jahr ohne Fallback)")
    se.set_defaults(func=cmd_search)

    kv = sub.add_parser(
        "kv", help="show the Klassenvorstand of a class (id or name), "
                   "or of the class(es) of a student (--student)")
    kv.add_argument("klasse", nargs="?", default=None,
                    help="class id (e.g. 4134) or name (e.g. 5AAIF); "
                         "required unless --student")
    kv.add_argument("--student", default=None,
                    help="student name: resolve student -> class(es) "
                         "-> KV (tokenizing match on first/last/short name)")
    kv.add_argument("--json", action="store_true")
    kv.set_defaults(func=cmd_kv)

    rp = sub.add_parser(
        "rpc", help="generic JSON-RPC passthrough (JSON output)")
    rp.add_argument("method", help="JSON-RPC method, e.g. getKlassen")
    rp.add_argument("params_json", nargs="?", default=None,
                    help="params as JSON string, default {}")
    rp.set_defaults(func=cmd_rpc)

    rst = sub.add_parser(
        "rest", help="generic REST passthrough to /WebUntis/api/<path>")
    rst.add_argument("path", help="path relative to /WebUntis/api, e.g. "
                                  "rest/view/v1/schoolyears")
    rst.add_argument("--method", default="GET",
                     choices=["GET", "POST", "PUT", "DELETE"],
                     help="HTTP method (default GET). NOTE: method does "
                          "NOT imply read vs. write — POST open-periods "
                          "is read-only, PUT lesson-topics writes.")
    rst.add_argument("--data-json", default=None,
                     help="request body as JSON string (POST/PUT)")
    rst.set_defaults(func=cmd_rest)

    les = sub.add_parser(
        "lesson", help="lesson diagnostics")
    les_sub = les.add_subparsers(dest="sub", required=True)
    les_info = les_sub.add_parser(
        "info", help="teachers, klassen, mainStudentgroupId, "
                     "roster vs. attending distribution for one lsId")
    les_info.add_argument("lsid", type=int, help="lesson id (lsId)")
    les_info.add_argument("--json", action="store_true")
    les_info.set_defaults(func=cmd_lesson_info)

    sess = sub.add_parser(
        "session", help="session cache and diagnostics")
    sess_sub = sess.add_subparsers(dest="sub", required=True)
    sess_status = sess_sub.add_parser(
        "status", help="cache age + live check via app/data")
    sess_status.add_argument("--json", action="store_true",
                             help="include the full app/data payload")
    sess_status.set_defaults(func=cmd_session_status)

    le = sub.add_parser("lehrstoff", help="Lehrstoff (lesson topic)")
    le_sub = le.add_subparsers(dest="sub", required=True)
    le_list = le_sub.add_parser("list")
    le_list.add_argument("--start", type=_date_arg, required=True)
    le_list.add_argument("--end", type=_date_arg, required=True)
    le_list.add_argument("--json", action="store_true")
    le_list.set_defaults(func=cmd_lehrstoff_list)

    ls = sub.add_parser(
        "lessons", help="list the user's lessons for one class, "
                        "grouped by lesson (lsId)")
    ls.add_argument("classname", help="class name, e.g. 3BAIF")
    ls.add_argument("--subject", default=None,
                    help="filter by subject short name (prefix match)")
    ls.add_argument("--start", type=_date_arg, default=None,
                    help="default: current schoolyear start")
    ls.add_argument("--end", type=_date_arg, default=None,
                    help="default: current schoolyear end")
    ls.add_argument("--full-names", action="store_true",
                    help="resolve teacher shorts to 'Lastname, Firstname'")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=cmd_lessons)

    le_get = le_sub.add_parser("get")
    le_get.add_argument("--period", type=int, required=True)
    le_get.set_defaults(func=cmd_lehrstoff_get)

    le_set = le_sub.add_parser("set")
    le_set.add_argument("--period", type=int, required=True)
    le_set.add_argument("--topic-id", type=int, default=None)
    src = le_set.add_mutually_exclusive_group(required=True)
    src.add_argument("--text")
    src.add_argument("--text-file")
    src.add_argument("--text-stdin", action="store_true")
    le_set.set_defaults(func=cmd_lehrstoff_set)

    le_batch = le_sub.add_parser("batch-set",
                                 help="set multiple topics from a JSON file")
    le_batch.add_argument("--file", required=True,
                          help="JSON file: [{periodId, topicId, text, "
                               "classId, start, end, date}, ...]")
    le_batch.add_argument("--delay", type=float, default=1.0,
                          help="seconds to wait between PUTs (default 1.0, "
                               "avoids IP rate-limiting)")
    le_batch.set_defaults(func=cmd_lehrstoff_batch_set)

    le_git = le_sub.add_parser("from-git",
                               help="derive text from GRG-* git logs")
    le_git.add_argument("--class-name", required=True)
    le_git.add_argument("--subject", required=True,
                        help="WebUntis subject short name, e.g. SWP1y")
    le_git.add_argument("--date", type=_date_arg, required=True)
    le_git.add_argument("--period", type=int, default=None)
    le_git.add_argument("--topic-id", type=int, default=None)
    le_git.add_argument("--dry-run", action="store_true")
    le_git.set_defaults(func=cmd_lehrstoff_from_git)

    le_status = le_sub.add_parser("status", help="overview of open periods")
    le_status.add_argument("--start", type=_date_arg, required=True)
    le_status.add_argument("--end", type=_date_arg, required=True)
    le_status.add_argument("--json", action="store_true")
    le_status.set_defaults(func=cmd_lehrstoff_status)

    le_fill = le_sub.add_parser("fill",
                                help="fetch periods + git diffs, build batch JSON")
    le_fill.add_argument("--start", type=_date_arg, required=True)
    le_fill.add_argument("--end", type=_date_arg, required=True)
    le_fill.add_argument("--dry-run", action="store_true", default=True)
    le_fill.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    le_fill.add_argument("--file", default=None,
                          help="confirmed batch JSON (required without --dry-run)")
    le_fill.add_argument("--delay", type=float, default=1.0)
    le_fill.add_argument("--json", action="store_true")
    le_fill.set_defaults(func=cmd_lehrstoff_fill)

    le_verify = le_sub.add_parser("verify",
                                  help="check which periods truly have no text")
    le_verify.add_argument("--start", type=_date_arg, required=True)
    le_verify.add_argument("--end", type=_date_arg, required=True)
    le_verify.add_argument("--json", action="store_true")
    le_verify.set_defaults(func=cmd_lehrstoff_verify)

    le_fillfix = le_sub.add_parser("fill-fixed",
                                   help="fill SS/BESP with fixed text")
    le_fillfix.add_argument("--start", type=_date_arg, required=True)
    le_fillfix.add_argument("--end", type=_date_arg, required=True)
    le_fillfix.add_argument("--dry-run", action="store_true", default=True,
                            help="(default) show what would be filled, "
                                 "write nothing")
    le_fillfix.add_argument("--no-dry-run", dest="dry_run",
                            action="store_false",
                            help="actually submit the fixed-text topics")
    le_fillfix.add_argument("--json", action="store_true")
    le_fillfix.add_argument("--delay", type=float, default=1.0)
    le_fillfix.set_defaults(func=cmd_lehrstoff_fill_fixed)

    # -- absences --
    abs_parser = sub.add_parser("absences", help="Absenzenkontrolle")
    abs_sub = abs_parser.add_subparsers(dest="sub", required=True)

    abs_check = abs_sub.add_parser("check", help="check absences for one period")
    abs_check.add_argument("--period", type=int, required=True)
    abs_check.set_defaults(func=cmd_check_absences)

    abs_batch = abs_sub.add_parser("batch-check",
                                   help="check absences from JSON file")
    abs_batch.add_argument("--file", required=True,
                           help="JSON: [{periodId: int}, ...]")
    abs_batch.add_argument("--delay", type=float, default=1.0)
    abs_batch.set_defaults(func=cmd_batch_check_absences)

    abs_all = abs_sub.add_parser("check-all",
                                 help="fetch open periods and check all absences")
    abs_all.add_argument("--start", type=_date_arg, required=True)
    abs_all.add_argument("--end", type=_date_arg, required=True)
    abs_all.add_argument("--delay", type=float, default=1.0)
    abs_all.set_defaults(func=cmd_check_all_absences)

    # -- students --
    stu = sub.add_parser("students", help="Schülerverwaltung (lesson attendance)")
    stu_sub = stu.add_subparsers(dest="sub", required=True)

    stu_list = stu_sub.add_parser(
        "list", help="dump a lesson's attendance matrix")
    stu_list.add_argument("--lsid", type=int, default=None,
                          help="lesson id; optional if CLASS SUBJECT given")
    stu_list.add_argument("class_name", nargs="?", default=None,
                          help="class name, e.g. 2AHWII (with SUBJECT "
                               "resolves the lsId automatically)")
    stu_list.add_argument("subject", nargs="?", default=None,
                          help="subject short name, e.g. SWP1x")
    stu_list.add_argument("--class-id", type=int, default=None,
                          help="only students of this class id")
    stu_list.add_argument("--attending-only", action="store_true")
    stu_list.add_argument("--all", action="store_true",
                          help="text view: show every student, not only "
                               "attending ones (JSON always shows all)")
    stu_list.add_argument("--json", action="store_true")
    stu_list.set_defaults(func=cmd_students_list)

    stu_find = stu_sub.add_parser(
        "find",
        help="find students by name (tokenizing, auto-fallback "
             "to older schoolyears)")
    stu_find.add_argument("name", help="name, e.g. 'Erika Muster'")
    stu_find.add_argument("--class", dest="klasse", default=None,
                          help="filter by class name, e.g. 5BAIF")
    stu_find.add_argument("--json", action="store_true")
    stu_find.set_defaults(func=cmd_students_find)

    stu_add = stu_sub.add_parser("add",
                                 help="add a student to a lesson's attendance")
    stu_add.add_argument("--lsid", type=int, required=True,
                         help="lesson id (lsId) of the target lesson")
    stu_add.add_argument("--class-id", type=int, required=True,
                         help="class id of the lesson's own class (students "
                              "kept unchanged)")
    stu_add.add_argument("--student-id", type=int, default=None)
    stu_add.add_argument("--student-name", default=None,
                         help="search by (partial) name; needs unique match")
    stu_add.add_argument("--dry-run", action="store_true", default=True)
    stu_add.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    stu_add.add_argument("--out", default=None,
                         help="write the submit payload JSON to this file")
    stu_add.add_argument("--verbose", action="store_true")
    stu_add.set_defaults(func=cmd_students_add)

    stu_edit = stu_sub.add_parser(
        "edit",
        help="add/remove students in a lesson's attendance (single write)")
    stu_edit.add_argument("--lsid", type=int, required=True,
                          help="lesson id (lsId) of the target lesson")
    stu_edit.add_argument("--class-id", type=int, required=True,
                          help="class id of the lesson's own class (students "
                               "kept unchanged)")
    stu_edit.add_argument("--add-student-id", type=int, action="append",
                          default=None,
                          help="student id to enroll (repeatable)")
    stu_edit.add_argument("--remove-student-id", type=int, action="append",
                          default=None,
                          help="student id to un-enroll (attendedPeriods "
                               "reset to [], repeatable)")
    stu_edit.add_argument("--dry-run", action="store_true", default=True)
    stu_edit.add_argument("--no-dry-run", dest="dry_run",
                          action="store_false")
    stu_edit.add_argument("--out", default=None,
                          help="write the submit payload JSON to this file")
    stu_edit.add_argument("--verbose", action="store_true")
    stu_edit.set_defaults(func=cmd_students_edit)

    args = p.parse_args()
    try:
        if args.cmd == "record":
            from webuntis_agent.recorder import main as rec
            return rec([f"--host={args.host}", f"--port={args.port}",
                        f"--domain={args.domain}"])
        if args.cmd == "cookies":
            print("TODO: implement cookies dump")
            return 1
        if hasattr(args, "func"):
            return args.func(args)
    except ModuleNotFoundError as e:
        print(
            f"Fehler: Python-Modul fehlt ({e.name}).\n\n"
            "Anleitung — venv im Repo anlegen:\n"
            "  python3 -m venv .venv\n"
            "  .venv/bin/pip install -e .\n\n"
            "Danach wu (.venv/bin/python) verwenden oder "
            "PYTHON_BIN auf das venv-Python setzen.",
            file=sys.stderr,
        )
        return 3
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

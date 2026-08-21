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


def _make_client(args: argparse.Namespace):
    _load_env()
    from webuntis_agent.client import Client
    return Client(
        host=os.environ.get("WEBUNTIS_HOST",
                            "https://spengergasse.webuntis.com"),
        school=os.environ.get("WEBUNTIS_SCHOOL", "spengergasse"),
    )


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


def cmd_lehrstoff_list(args: argparse.Namespace) -> int:
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    data = c.get_open_periods(args.start, args.end, school_year_id=sy)
    raw = data.get("periods", [])
    if not raw:
        print("[]" if args.json else "(no open periods)")
        return 0
    # Build a flat list of period entries, group by lsId for block bounds.
    entries: list[dict] = []
    blocks: dict[int | None, list[dict]] = {}
    for p in raw:
        per = p.get("period", {})
        cls = per.get("classes", [{}])[0].get("el", {})
        subj = per.get("subject", {}).get("el", {})
        dt = per.get("dtRange", {})
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
    sub.add_parser("cookies", help="dump harvested cookies")

    le = sub.add_parser("lehrstoff", help="Lehrstoff (lesson topic)")
    le_sub = le.add_subparsers(dest="sub", required=True)
    le_list = le_sub.add_parser("list")
    le_list.add_argument("--start", type=_date_arg, required=True)
    le_list.add_argument("--end", type=_date_arg, required=True)
    le_list.add_argument("--json", action="store_true")
    le_list.set_defaults(func=cmd_lehrstoff_list)

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
    le_batch.add_argument("--delay", type=float, default=0.5,
                          help="seconds to wait between PUTs (default 0.5)")
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

    args = p.parse_args()
    if args.cmd == "record":
        from webuntis_agent.recorder import main as rec
        return rec()
    if args.cmd == "cookies":
        print("TODO: implement cookies dump")
        return 1
    if hasattr(args, "func"):
        return args.func(args)
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

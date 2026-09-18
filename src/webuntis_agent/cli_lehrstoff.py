"""CLI lehrstoff commands (split from cli.py, see #15)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from collections import Counter, defaultdict

from typing import TYPE_CHECKING

from webuntis_agent.cli_common import (
    _make_client,
    _fetch_open_periods,
    _period_summary,
    _open_period_entries,
    _group_lesson_entries,
    _submit_topic_entries,
    _resolve_topic_id,
    _read_text_arg,
    _no_open_periods,
)

if TYPE_CHECKING:
    from webuntis_agent.client import Client


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
        return _no_open_periods(args)
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


def cmd_lehrstoff_set(args: argparse.Namespace) -> int:
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    if args.topic_id is None:
        args.topic_id = _resolve_topic_id(c, sy, args.period, None)
        print(f"resolved topic_id={args.topic_id}")
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
    results = _submit_topic_entries(
        c, sy, items, delay=args.delay, url_fields=True)
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


def cmd_lehrstoff_status(args: argparse.Namespace) -> int:
    """Overview of open periods grouped by subject, class, month."""
    from collections import Counter, defaultdict
    c, sy, periods = _fetch_open_periods(args)
    if not periods:
        return _no_open_periods(args)
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
        return _no_open_periods(args)

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
        results = _submit_topic_entries(c, sy, items, delay=args.delay)
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
        return _no_open_periods(args)

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
        return _no_open_periods(args)

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

    results = _submit_topic_entries(c, sy, fixed_periods, delay=args.delay)
    ok = sum(1 for r in results if r.get("ok"))
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        by_period = {e["periodId"]: e for e in fixed_periods}
        for r in results:
            e = by_period.get(r.get("periodId"), {})
            status = "ok" if r.get("ok") else f"FAILED: {r.get('error', '?')}"
            print(f"  {r.get('periodId'):>10} {e.get('class') or '':6} "
                  f"{e.get('subject') or '':6} {e.get('date') or ''} "
                  f"{status}")
    print(f"\n{ok}/{len(results)} fixed-text periods filled", file=sys.stderr)
    return 0 if ok == len(results) else 1



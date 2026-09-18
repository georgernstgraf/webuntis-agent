"""CLI students commands (split from cli.py, see #15)."""

from __future__ import annotations

import argparse
import json
import sys

from typing import TYPE_CHECKING

from webuntis_agent.cli_common import (
    _date_arg,
    _make_client,
    _open_period_entries,
)

if TYPE_CHECKING:
    from webuntis_agent.client import Client


def _teacher_names_for_class(c: Client, class_id: int,
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


def _pick_closest_lesson(matches: dict[int, list[str]],
                         ref_date: str) -> int:
    """Pick the lsId whose dates best match ref_date (YYYY-MM-DD).

    An exact date hit (distance 0) wins; otherwise the smallest
    absolute day distance; ties broken by smallest lsId (deterministic).
    Pure function (no network) — unit-tested.
    """
    from datetime import date as _date
    ref = _date.fromisoformat(ref_date)

    def dist(dates: list[str]) -> int:
        deltas = []
        for d in dates:
            try:
                deltas.append(abs((_date.fromisoformat(d) - ref).days))
            except ValueError:
                continue
        return min(deltas) if deltas else 10 ** 9

    return min(matches, key=lambda lsid: (dist(matches[lsid]), lsid))


def _nearest_date(dates: list[str], ref_date: str) -> str:
    """Nearest unit date to ref_date (both YYYY-MM-DD).

    Smallest absolute day distance; ties broken by earlier date.
    Pure function (no network) — unit-tested.
    """
    from datetime import date as _date
    ref = _date.fromisoformat(ref_date)
    return min(dates, key=lambda d: (abs((_date.fromisoformat(d) - ref).days),
                                     d))


def _resolve_lesson_from_class_subject(
        c: Client, sy: int, class_name: str, subject: str,
        ref_date: str | None = None) -> dict:
    """Find the lesson of a (class, subject) pair, return match details.

    Scans a window around today (7 days back, 13 ahead). Case-
    insensitive matching; subject falls back to a prefix match. Returns
    `{"lsId", "class", "subject", "dates", "candidates"}` with the
    exact Untis class/subject strings of the picked lesson. On multiple
    matches the one closest to `ref_date` (default: today) is picked
    and a warning is printed to stderr; no match raises RuntimeError
    with candidates.
    """
    from datetime import date as _date, timedelta as _timedelta
    ref = ref_date or _date.today().isoformat()
    start = (_date.today() - _timedelta(days=7)).isoformat()
    end = (_date.today() + _timedelta(days=13)).isoformat()
    entries = _open_period_entries(c, sy, start, end)
    cls_l = class_name.lower()
    subj_l = subject.lower()
    matches: dict[int, dict] = {}
    for e in entries:
        if (e["class"] or "").lower() != cls_l:
            continue
        subj = e["subject"] or ""
        if not (subj.lower() == subj_l
                or subj.lower().startswith(subj_l)
                or subj_l.startswith(subj.lower())):
            continue
        if e["lsId"] is not None:
            m = matches.setdefault(e["lsId"], {"dates": [], "units": []})
            m["dates"].append(e["date"])
            m["units"].append((e["date"], e["class"], e["subject"]))
    if not matches:
        avail = sorted({(e["class"] or "", e["subject"] or "")
                        for e in entries})
        hints = ", ".join(f"{a}/{b}" for a, b in avail if a.lower() == cls_l)
        raise RuntimeError(
            f"no lesson found for {class_name}/{subject} in "
            f"{start}..{end}" + (f"; available for {class_name}: {hints}"
                                 if hints else ""))
    if len(matches) > 1:
        picked = _pick_closest_lesson(
            {lsid: m["dates"] for lsid, m in matches.items()}, ref)
        print(f"warning: ambiguous lesson for {class_name}/{subject}: "
              f"{len(matches)} candidates, picked lsId={picked} "
              f"closest to {ref}", file=sys.stderr)
        for lsid in sorted(matches):
            m = matches[lsid]
            units = sorted({(u[1], u[2]) for u in m["units"]})
            # one line per candidate: exact Untis label + unit date
            # nearest to ref (all units share class/subject per lesson,
            # first label wins on mixed data)
            klass, subj = units[0]
            print(f"{klass}/{subj} "
                  f"({_nearest_date(m['dates'], ref)})", file=sys.stderr)
    else:
        picked = next(iter(matches))
    m = matches[picked]
    # label: prefer the unit entry on ref_date (exact Untis designation
    # of the requested unit), else the first entry of the lesson
    label_unit = next((u for u in m["units"] if u[0] == ref), m["units"][0])
    return {"lsId": picked, "class": label_unit[1],
            "subject": label_unit[2],
            "dates": sorted(set(m["dates"])),
            "candidates": sorted(matches)}


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
            lesson = _resolve_lesson_from_class_subject(
                c, sy, args.class_name, args.subject)
            lsid = lesson["lsId"]
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"resolved {args.class_name}/{args.subject} -> lsId {lsid} "
              f"({lesson['class']}/{lesson['subject']})",
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


def _build_students_payload(all_students: list[dict], class_id: int,
                            add_ids: list[int], remove_ids: list[int],
                            lesson_dates: list) -> list[dict]:
    """Build the students list for submitStudentLessonPeriodData.

    Shared edit semantics (single source of truth for `students add`
    and `students edit`): lesson-class students unchanged, already-
    attending students of ANY class kept (dropping them would un-enroll
    them), removed students reset to attendedPeriods=[], added students
    get ALL lesson dates (merged into existing attendance if already
    partially attending). add_ids and remove_ids must be disjoint —
    callers validate that.
    """
    add_set = set(add_ids)
    remove_set = set(remove_ids)
    keep = []
    for s in all_students:
        sid = s["id"]
        if sid in remove_set:
            continue
        if sid in add_set:
            keep.append({"id": sid,
                         "attendedPeriods": sorted(
                             set(s["attendedPeriods"]) | set(lesson_dates))})
        elif s["klasse"] == class_id or s["attendedPeriods"]:
            keep.append({"id": sid,
                         "attendedPeriods": list(s["attendedPeriods"])})
    for sid in remove_ids:
        keep.append({"id": sid, "attendedPeriods": []})
    known = {e["id"] for e in keep}
    for sid in add_ids:
        if sid not in known:
            keep.append({"id": sid, "attendedPeriods": lesson_dates})
    return keep


def _finish_students_command(c, args: argparse.Namespace,
                             payload: dict, summary: dict,
                             dry_msg: str) -> int:
    """Shared tail for `students add`/`students edit` (single source).

    Handles `--out` payload dump, `--dry-run` (default) summary output
    and the single `submitStudentLessonPeriodData` write. Callers build
    `payload` + `summary` (payload already embedded unless --verbose
    placeholder) and only differ in their dry-run message.
    """
    from pathlib import Path
    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8")
        summary["writtenTo"] = args.out
    if args.dry_run:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print(dry_msg, file=sys.stderr)
        return 0
    res = c.submit_student_lesson_period_data(
        payload["lessonId"], payload["mainStudentgroupId"],
        payload["students"], payload["startDate"], payload["endDate"],
        school_year_id=args.school_year_id,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_students_add(args: argparse.Namespace) -> int:
    """Add a student to a lesson's attendance (Schüler-Aufnahme).

    Loads the student-lesson-period matrix for the lesson, sets the
    student's attendedPeriods to all lesson dates, and submits the
    combined payload (lesson class students unchanged + the added
    student). --dry-run (default) writes the payload JSON to --out and
    does NOT submit.
    """
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

    # payload with edit semantics: lesson class unchanged, already-
    # attending students (any class) kept, target on all lesson dates
    students_payload = _build_students_payload(
        all_students, args.class_id, [target["id"]], [], lesson_dates)

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
    return _finish_students_command(
        c, args, payload, summary,
        f"\nDRY RUN: {target['name']} (id={target['id']}) would attend "
        f"{len(lesson_dates)} lesson dates of lesson {args.lsid}; "
        f"payload has {len(students_payload)} students "
        f"(class roster + attending kept). "
        f"Submit with --no-dry-run.")


def cmd_students_edit(args: argparse.Namespace) -> int:
    """Edit a lesson's attendance: add and/or remove external students.

    Builds the full students payload (lesson class students unchanged,
    other attending students unchanged, removed students set to
    attendedPeriods=[], added students set to all lesson dates) and
    submits it via submitStudentLessonPeriodData. --dry-run (default)
    writes the payload JSON to --out and does NOT submit.
    """
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

    keep = _build_students_payload(
        all_students, args.class_id, add_ids, remove_ids, lesson_dates)

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
    return _finish_students_command(
        c, args, payload, summary,
        f"\nDRY RUN: +{[by_id[i]['name'] for i in add_ids]} "
        f"-{[by_id[i]['name'] for i in remove_ids]} "
        f"on lesson {args.lsid} ({len(lesson_dates)} lesson dates); "
        f"payload has {len(keep)} students. "
        f"Submit with --no-dry-run.")


def _lesson_label_for_lsid(c: Client, sy: int, lsid: int,
                           day: str) -> str | None:
    """Best-effort exact 'class/subject' label for an lsId (#16).

    Reverse lookup via open periods on the unit day itself. Returns None
    when the lesson has no open periods that day (all topics set and
    absences checked) — callers then omit the label line.
    """
    try:
        entries = _open_period_entries(c, sy, day, day)
    except Exception:
        return None
    for e in entries:
        if (e.get("lsId") == lsid and e.get("class")
                and e.get("subject")):
            return f"{e['class']}/{e['subject']}"
    return None


def _resolve_roster_date(value: str) -> str:
    """Resolve --date for `students roster`: 'now' -> today (YYYY-MM-DD),
    otherwise a validated YYYY-MM-DD date."""
    if value.lower() == "now":
        from datetime import date as _date
        return _date.today().isoformat()
    return _date_arg(value)


def _tsv_cell(value: object) -> str:
    """Make a value TSV-safe (no tabs/newlines inside a cell)."""
    return str(value if value is not None else "").replace("\t", " ").replace(
        "\n", " ").replace("\r", "")


def _roster_rows(matrix_result: dict, overview_by_id: dict,
                 ymd: int) -> tuple[list[tuple[str, str]], list[str]]:
    """Build sorted (name-cell, klasse-cell) TSV rows for one unit date.

    Participants are matrix students whose attendedPeriods contain `ymd`.
    Names come from students/overview (full first/last names — matrix
    names are shortened); matrix names are the fallback. Returns
    (rows, unmatched_names); rows are sorted by (last, first).
    """
    klassen = {k.get("id"): k.get("name")
               for k in matrix_result.get("allKlassen", [])}
    keyed: list[tuple[tuple[str, str], str, str]] = []
    unmatched: list[str] = []
    for s in matrix_result.get("allStudents", []):
        if ymd not in (s.get("attendedPeriods") or []):
            continue
        ov = overview_by_id.get(s.get("id"))
        if ov and ov.get("lastName"):
            last = ov.get("lastName", "")
            first = ov.get("firstName", "")
            sortkey = (last.lower(), first.lower())
            cell = f"{last} {first}".strip()
            klass = (ov.get("classInfo") or {}).get("name")
        else:
            cell = s.get("name", "")
            sortkey = (cell.lower(), "")
            klass = None
            unmatched.append(cell)
        if not klass:
            klass = klassen.get(s.get("klasse"), str(s.get("klasse")))
        keyed.append((sortkey, _tsv_cell(cell), _tsv_cell(klass)))
    keyed.sort(key=lambda r: r[0])
    return [(name, klass) for _, name, klass in keyed], unmatched


def cmd_students_roster(args: argparse.Namespace) -> int:
    """Excel-pasteable TSV participant list for one lesson unit (#16).

    The lesson is given by --lsid, or resolved from positional
    CLASS SUBJECT (e.g. `students roster 3AAIF WMC --date now`) via the
    open periods of a window around today. --date (YYYY-MM-DD or 'now')
    selects the unit day: participants are students whose
    attendedPeriods contain that date — the same set Untis shows when
    opening that unit's attendance check. Read-only (no writes).
    """
    c = _make_client(args)
    day = args.date
    ymd = int(day.replace("-", ""))
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    lsid = args.lsid
    lesson_label = None
    if lsid is None:
        if not args.class_name or not args.subject:
            print("either --lsid or CLASS SUBJECT are required",
                  file=sys.stderr)
            return 2
        try:
            lesson = _resolve_lesson_from_class_subject(
                c, sy, args.class_name, args.subject, ref_date=day)
            lsid = lesson["lsId"]
            lesson_label = f"{lesson['class']}/{lesson['subject']}"
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"resolved {args.class_name}/{args.subject} -> lsId {lsid} "
              f"({lesson_label})",
              file=sys.stderr)
    else:
        lesson_label = _lesson_label_for_lsid(c, sy, lsid, day)
    result = c.get_student_lesson_period_matrix(
        lsid, school_year_id=args.school_year_id)["result"]
    period_dates = {p.get("date") for p in result.get("lessonPeriods", [])}
    requested_day = day
    if ymd not in period_dates:
        if not period_dates:
            print(f"no lesson units at all for lsId {lsid}", file=sys.stderr)
            return 2
        # future-first fallback (#16): nearest upcoming unit, else last held
        future = [d for d in period_dates if d > ymd]
        pick = min(future) if future else max(period_dates)
        day = f"{pick // 10000:04d}-{(pick // 100) % 100:02d}-{pick % 100:02d}"
        ymd = pick
        print(f"note: no unit on {requested_day} for lsId {lsid}, "
              f"using nearest unit {day}", file=sys.stderr)
    try:
        overview = c.get_students_overview()
    except Exception as e:
        print(f"warning: students/overview failed ({e}) — "
              "using short matrix names", file=sys.stderr)
        overview = {}
    by_id = {s.get("id"): s for s in overview.get("students", [])}
    rows, unmatched = _roster_rows(result, by_id, ymd)
    if args.json:
        payload: dict = {
            "lsId": lsid,
            "lesson": lesson_label,
            "date": day,
            "students": [{"name": name, "klasse": klass}
                         for name, klass in rows],
        }
        if day != requested_day:
            payload["requestedDate"] = requested_day
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if lesson_label:
        print(lesson_label if day == requested_day
              else f"{lesson_label} ({day})")
    if not args.no_header:
        print("Name\tKlasse")
    for name, klass in rows:
        print(f"{name}\t{klass}")
    expected = next((p.get("studentCount")
                     for p in result.get("lessonPeriods", [])
                     if p.get("date") == ymd), None)
    if expected is not None and expected != len(rows):
        print(f"warning: studentCount={expected} but {len(rows)} rows listed",
              file=sys.stderr)
    if unmatched:
        print(f"note: {len(unmatched)} without overview match "
              "(short names used)", file=sys.stderr)
    return 0



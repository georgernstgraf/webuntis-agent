"""CLI common commands (split from cli.py, see #15)."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webuntis_agent.client import Client

from dataclasses import dataclass


@dataclass(frozen=True)
class PeriodFields:
    """Typed view of the DOMAIN.md `Period` base fields.

    Wire format stays a plain dict (`to_dict`, original key order) so
    CLI JSON output is byte-identical — this only replaces the raw-dict
    plumbing inside `_base_period_fields`.
    """

    period_id: int | None
    topic_id: int | None
    class_name: str | None
    class_id: int | None
    subject: str | None
    subject_long: str | None
    date: str
    time: str

    @classmethod
    def from_raw(cls, per: dict, topic_id: int | None) -> "PeriodFields":
        cls_el = per.get("classes", [{}])[0].get("el", {})
        subj_el = per.get("subject", {}).get("el", {})
        dt = per.get("dtRange", {})
        return cls(
            period_id=per.get("id"),
            topic_id=topic_id,
            class_name=cls_el.get("name"),
            class_id=cls_el.get("id"),
            subject=subj_el.get("nameShort"),
            subject_long=subj_el.get("name"),
            date=(dt.get("start") or "")[:10],
            time=(dt.get("start") or "")[11:16],
        )

    def to_dict(self) -> dict:
        return {
            "periodId": self.period_id,
            "topicId": self.topic_id,
            "class": self.class_name,
            "classId": self.class_id,
            "subject": self.subject,
            "subjectLong": self.subject_long,
            "date": self.date,
            "time": self.time,
        }


@dataclass
class LessonGroup:
    """Typed view of a DOMAIN.md lesson block (`lsId` group).

    `to_dict` keeps the original key order so `lessons` JSON output is
    byte-identical.
    """

    ls_id: int | None
    subject: str
    subject_long: str
    class_name: str | None
    class_id: int | None
    periods: int
    first_date: str
    last_date: str
    open_topic_ids: list
    teachers: list
    teacher_shorts: list
    rooms: list
    entries: list

    def to_dict(self) -> dict:
        return {
            "lsId": self.ls_id,
            "subject": self.subject,
            "subjectLong": self.subject_long,
            "class": self.class_name,
            "classId": self.class_id,
            "periods": self.periods,
            "firstDate": self.first_date,
            "lastDate": self.last_date,
            "openTopicIds": self.open_topic_ids,
            "teachers": self.teachers,
            "teacherShorts": self.teacher_shorts,
            "rooms": self.rooms,
            "entries": self.entries,
        }


@dataclass(frozen=True)
class SubmitItem:
    """Typed view of one DOMAIN.md `Topic` write (`lehrstoff` PUT item)."""

    period_id: int
    topic_id: int | None
    text: str
    class_id: int | None = None
    start: str | None = None
    end: str | None = None
    date: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "SubmitItem":
        return cls(
            period_id=d["periodId"],
            topic_id=d.get("topicId"),
            text=d["text"],
            class_id=d.get("classId"),
            start=d.get("start"),
            end=d.get("end"),
            date=d.get("date"),
        )


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


def _add_school_year_arg(sp):
    """Allow --school-year-id AFTER the subcommand (both positions work).

    The top-level parser also defines it (before the subcommand). This
    copy uses default=SUPPRESS so it only overwrites when explicitly
    given — otherwise the global value is preserved.
    """
    sp.add_argument("--school-year-id", type=int,
                    default=argparse.SUPPRESS,
                    help="pin schoolyear id (default: resolve via date range)")


def _sleep_between(i: int, delay: float) -> None:
    """Sleep `delay` seconds between write-loop iterations (not before #0).

    Single source of truth for the IP rate-limit pause (TCP resets, not
    HTTP 429) shared by `_submit_topic_entries`, `batch-check` and
    `check-all`.
    """
    if i and delay > 0:
        time.sleep(delay)


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


def _base_period_fields(per: dict, topic_id: int | None) -> dict:
    """Shared period/class/subject/dtRange extraction (single source).

    Used by `_open_period_entries` and `_period_summary` — both read the
    same `period.classes[0].el`, `period.subject.el` and `dtRange` shape.
    Typed via `PeriodFields`; wire format (dict) unchanged.
    """
    return PeriodFields.from_raw(per, topic_id).to_dict()


def _open_period_entries(c: Client, sy: int, start: str, end: str,
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
        entry = _base_period_fields(per, p.get("topicId"))
        entry.update({
            "_start_iso": (dt.get("start") or "").replace(" ", "T"),
            "_end_iso": (dt.get("end") or "").replace(" ", "T"),
            "lsId": per.get("lsId"),
            "hr": per.get("hr"),
            "teachers": [t.get("name") for t in teachers],
            "teacherShorts": [t.get("nameShort") for t in teachers],
            "rooms": rooms,
        })
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
        out.append(LessonGroup(
            ls_id=lsid,
            subject=subj,
            subject_long=subj_long,
            class_name=g_sorted[0].get("class"),
            class_id=g_sorted[0].get("classId"),
            periods=len(g_sorted),
            first_date=g_sorted[0]["date"],
            last_date=g_sorted[-1]["date"],
            open_topic_ids=sorted({e["topicId"] for e in g_sorted
                                   if e.get("topicId")}),
            teachers=teachers,
            teacher_shorts=shorts,
            rooms=rooms,
            entries=g_sorted,
        ).to_dict())
    out.sort(key=lambda g: (g["firstDate"], g["subject"]))
    return out


def _period_summary(p: dict) -> dict:
    """Extract a flat dict from a raw open-period entry."""
    per = p.get("period", {})
    dt = per.get("dtRange", {})
    summary = _base_period_fields(per, p.get("topicId"))
    summary.update({
        "startIso": dt.get("start"),
        "endIso": dt.get("end"),
        "lsId": per.get("lsId"),
        "hr": per.get("hr"),
        "topicNeeded": p.get("topicNeeded"),
        "absCheckNeeded": p.get("absCheckNeeded"),
    })
    return summary


def _fetch_open_periods(args: argparse.Namespace):
    """Shared helper: create client, resolve schoolyear, fetch periods."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    data = c.get_open_periods(args.start, args.end, school_year_id=sy)
    return c, sy, data.get("periods", [])


def _no_open_periods(args: argparse.Namespace) -> int:
    """Shared empty-result output for open-period commands (single source).

    Used by `lehrstoff list/status/fill/verify/fill-fixed`: JSON callers
    get `[]`, text callers `(no open periods)`.
    """
    print("[]" if args.json else "(no open periods)")
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


def _resolve_topic_id(c, sy: int, period_id: int,
                      topic_id: int | None) -> int:
    """Resolve a missing topicId via GET lesson-topic (single source of truth).

    Shared by `lehrstoff set` and `_submit_topic_entries`: returns the
    given id when present, otherwise the existing row id, or 0 to create
    a new topic row (server creates it on PUT).
    """
    if topic_id is not None:
        return topic_id
    topic = c.get_lesson_topic(period_id, school_year_id=sy)
    pts = topic.get("periodTopics", [])
    if pts and pts[0].get("topic"):
        return pts[0]["topic"]["id"]
    return 0  # Neuanlage: server creates new topic row


def _submit_topic_entries(c, sy: int, items: list[dict],
                          delay: float = 1.0,
                          url_fields: bool = False) -> list[dict]:
    """Shared write loop for lehrstoff topic submissions.

    Single source of truth for `lehrstoff batch-set`, `lehrstoff fill
    --no-dry-run` and `lehrstoff fill-fixed`: per item, resolve a
    missing topicId via `_resolve_topic_id` (GET lesson-topic; id=0
    creates a new topic row), PUT the topic, sleep `delay` between PUTs
    (rate-limit). With `url_fields`, items may carry classId/start/end/
    date to enrich the result with a lessonDetailsUrl.

    NOTE (url_fields decision, #14): only `batch-set` passes
    `url_fields=True`. `fill`/`fill-fixed` intentionally do not enrich
    URLs — the pre-refactor code had no URLs there either (no
    regression); `batch-set` remains the single URL producer.
    """
    results: list[dict] = []
    for i, raw in enumerate(items):
        _sleep_between(i, delay)
        try:
            item = SubmitItem.from_dict(raw)
        except KeyError as e:
            results.append({
                "periodId": raw.get("periodId"),
                "ok": False,
                "error": f"malformed item: missing {e}",
            })
            continue
        entry: dict = {"periodId": item.period_id}
        tid = item.topic_id
        if tid is None:
            try:
                tid = _resolve_topic_id(c, sy, item.period_id, None)
            except Exception as e:
                entry["ok"] = False
                entry["error"] = f"topicId resolution failed: {e}"
                results.append(entry)
                continue
        try:
            res = c.set_lesson_topic(
                item.period_id, tid, item.text, school_year_id=sy)
            entry["ok"] = True
            entry["updated"] = [t.get("id") for t in res.get("topics", [])]
            if url_fields:
                ref_date = item.date or (item.start or "")[:10]
                if item.class_id and item.start and item.end:
                    entry["lessonDetailsUrl"] = _lesson_details_url(
                        c.host, item.period_id, item.class_id,
                        item.start, item.end, ref_date,
                    )
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)
        results.append(entry)
    return results


def _format_search_hit(hit: dict) -> str:
    res = hit.get("resource", {})
    line = (
        f"{hit.get('type', '?'):>8}  id={res.get('id'):>6}  "
        f"{res.get('shortName', ''):12} "
        f"{res.get('displayName') or res.get('longName', '')}"
    )
    if hit.get("searchNote"):
        line += f"  [{hit['searchNote']}]"
    if hit.get("current") is False:
        year = hit.get("schoolYear") or {}
        line += (f"  [SJ {year.get('name', '?')} (id {year.get('id', '?')})"
                 f" — NICHT AKTUELL]")
    return line


def _annotate_search_hits(hits: list[dict], c: Client,
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



"""CLI klasse-Befehle: alles zu einer Klasse (z.B. 3AHWII).

Der Default-Befehl liefert Roster (Schülerliste) und Fächer
(eigene Lessons in dieser Klasse) sowie den Klassenvorstand.
"""

from __future__ import annotations

import argparse
import json
import sys

from typing import TYPE_CHECKING

from webuntis_agent.cli_common import (
    _group_lesson_entries,
    _make_client,
    _open_period_entries,
)
from webuntis_agent.cli_lesson import _teacher_names_for_class

if TYPE_CHECKING:
    from webuntis_agent.client import Client


def _kv_info(c: Client, sy: int, needle: int | str) -> dict:
    """KV-Info einer Klasse (ID oder exakter Name) als Dict.

    Wirft RuntimeError, wenn die Klasse nicht gefunden wird.
    """
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
        raise RuntimeError(f"Klasse '{needle}' nicht gefunden")
    teacher_ids = [v for key in ("teacher1", "teacher2", "teacher3")
                   if (v := hit.get(key))]
    return {
        "classId": hit.get("id"),
        "name": hit.get("name"),
        "longName": hit.get("longName"),
        "teachers": _teacher_names_for_class(c, hit["id"], teacher_ids, sy),
    }


def cmd_klasse_kv(args: argparse.Namespace) -> int:
    """Klassenvorstand einer Klasse anzeigen (Name oder ID)."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    try:
        info = _kv_info(c, sy, args.klassenname)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0
    print(f"{info['name']} ({info['longName']}):")
    for tid, name in info["teachers"].items():
        print(f"  KV: {name} (Lehrer-ID {tid})")
    return 0


def _faecher_groups(c: Client, sy: int, klassenname: str,
                    start: str | None, end: str | None,
                    fach: str | None = None) -> tuple[list[dict], str, str]:
    """Eigene Lessons einer Klasse als lsId-Gruppen (Fächer).

    Quelle sind die offenen Perioden im Zeitraum (Standard: Schuljahr bis
    heute) — d.h. Lessons mit noch offenen Lehrstoffen/Absenzen. Liefert
    (Gruppen, von, bis).
    """
    if start is None or end is None:
        syr = next((y for y in c.get_schoolyears() if int(y["id"]) == sy),
                   None)
        if syr is None:
            raise RuntimeError(f"Schuljahr {sy} nicht gefunden")
        dr = syr["dateRange"]
        start = start or str(dr["start"])[:10]
        end = end or str(dr["end"])[:10]
    entries = _open_period_entries(c, sy, start, end)
    cls_l = klassenname.lower()
    entries = [e for e in entries
               if (e.get("class") or "").lower() == cls_l]
    if fach:
        fl = fach.lower()
        entries = [e for e in entries
                   if (e.get("subject") or "").lower().startswith(fl)]
    return _group_lesson_entries(entries), start, end


def cmd_klasse_faecher(args: argparse.Namespace) -> int:
    """Eigene Lessons (Fächer) einer Klasse auflisten, gruppiert je Lesson."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    try:
        groups, start, end = _faecher_groups(
            c, sy, args.klassenname, args.start, args.end, args.fach)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    if not groups:
        print(f"(keine offenen Lessons für {args.klassenname}"
              + (f"/{args.fach}" if args.fach else "")
              + f" in {start}..{end})")
        return 0
    full_by_short: dict[str, str] = {}
    if args.volle_namen:
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
            "class": args.klassenname,
            "range": {"start": start, "end": end},
            "lessons": [{k: v for k, v in g.items() if k != "entries"}
                        for g in groups],
        }, indent=2, ensure_ascii=False))
        return 0
    for g in groups:
        teachers = [full_by_short.get(s, t)
                    for t, s in zip(g["teachers"], g["teacherShorts"])] \
            if args.volle_namen else g["teachers"]
        print(f"lsId {g['lsId']}  {g['subject']} — {g['subjectLong']}")
        print(f"  {g['class']}  Perioden={g['periods']}  "
              f"{g['firstDate']} .. {g['lastDate']}  offen={len(g['entries'])}")
        if teachers:
            print(f"  Lehrer: {' + '.join(teachers)}")
        if g["rooms"]:
            print(f"  Räume:  {' + '.join(g['rooms'])}")
    return 0


def _klassen_roster(c: Client, klassenname: str) -> list[tuple[str, str]]:
    """Roster einer Klasse aus students/overview (volle Namen).

    Liefert sortierte (Name, Klasse)-Zeilen; wirft RuntimeError ohne Treffer.
    """
    try:
        overview = c.get_students_overview()
    except Exception as e:
        raise RuntimeError(f"students/overview fehlgeschlagen ({e})")
    kl_l = klassenname.lower()
    rows = []
    for s in overview.get("students", []):
        ci = s.get("classInfo") or {}
        if (ci.get("name") or "").lower() != kl_l:
            continue
        name = f"{s.get('lastName', '')} {s.get('firstName', '')}".strip()
        rows.append(((s.get("lastName", "").lower(),
                      s.get("firstName", "").lower()),
                     name, ci.get("name", "")))
    if not rows:
        raise RuntimeError(
            f"keine Schüler für Klasse '{klassenname}' im aktuellen Roster")
    rows.sort(key=lambda r: r[0])
    return [(name, klass) for _, name, klass in rows]


def cmd_klasse_roster(args: argparse.Namespace) -> int:
    """Schülerliste (Roster) einer Klasse, Excel-einfügbare TSV-Ausgabe."""
    from webuntis_agent.cli_lesson import _tsv_cell
    c = _make_client(args)
    try:
        rows = _klassen_roster(c, args.klassenname)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({
            "class": args.klassenname,
            "students": [{"name": n, "klasse": k} for n, k in rows],
        }, indent=2, ensure_ascii=False))
        return 0
    if not args.ohne_kopf:
        print("Name\tKlasse")
    for name, klass in rows:
        print(f"{_tsv_cell(name)}\t{_tsv_cell(klass)}")
    return 0


def cmd_klasse(args: argparse.Namespace) -> int:
    """Klassen-Übersicht (Default): KV, Fächer und Roster.

    Nur lesend. --json liefert alles strukturiert.
    """
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    try:
        info = _kv_info(c, sy, args.klassenname)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        groups, start, end = _faecher_groups(c, sy, args.klassenname,
                                             args.start, args.end, None)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        rows = _klassen_roster(c, args.klassenname)
    except RuntimeError as e:
        print(f"Hinweis: {e}", file=sys.stderr)
        rows = []
    if args.json:
        print(json.dumps({
            "class": info["name"],
            "longName": info["longName"],
            "kv": info["teachers"],
            "range": {"start": start, "end": end},
            "lessons": [{k: v for k, v in g.items() if k != "entries"}
                        for g in groups],
            "students": [{"name": n, "klasse": k} for n, k in rows],
        }, indent=2, ensure_ascii=False))
        return 0
    print(f"{info['name']} ({info['longName']})")
    for tid, name in info["teachers"].items():
        print(f"  KV: {name}")
    print(f"\nFächer (eigene Lessons, offen in {start}..{end}):")
    if not groups:
        print("  (keine)")
    for g in groups:
        lehrer = f" ({' + '.join(g['teachers'])})" if g["teachers"] else ""
        print(f"  {g['subject']:8} — {g['subjectLong']}{lehrer} "
              f"[lsId {g['lsId']}]")
    print(f"\nRoster ({len(rows)} Schüler):")
    for name, klass in rows:
        print(f"  {name}")
    return 0

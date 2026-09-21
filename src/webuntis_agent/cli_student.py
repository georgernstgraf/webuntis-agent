"""CLI student-Befehle: alles zu einem Schüler (Singular).

Sucht per tokenisierender Stundenplan-Suche (mit automatischem Fallback
in ältere Schuljahre) und reichert aktuelle Treffer aus students/overview
an (volle Namen + Klasse). Detail je aktuellem Schüler: Klasse, KV und
belegte/nicht belegte Lessons aus dem SCHÜLER-STUNDENPLAN (Join mit dem
Klassen-Plan, ohne Matrix-Calls). Absenzen nur mit --absenzen (opt-in),
dann Matrix-Scans über die EIGENEN Lessons der Klasse (gedrosselt).
"""

from __future__ import annotations

import argparse
import json
import sys

from webuntis_agent.cli_common import (
    _find_klasse,
    _make_client,
    _sleep_between,
)
from webuntis_agent.cli_klasse import _kv_info


def _suchen(c, sy: int, query: str, fallback: bool, alle_jahre: bool,
            override: int | None) -> tuple[list[dict], int, list[int]]:
    """Gemeinsame Schüler-Suche: aktuelles Jahr + bis zu 3 ältere.

    Liefert (Treffer, aktuelle_id, durchsuchte_jahre). Treffer aus älteren
    Jahren tragen `current: False` (NICHT AKTUELL).
    """
    from webuntis_agent.client import (
        student_matches_overview,
        tokenize_search_query,
    )
    if override is not None:
        years = [override]
        current_id = override
    else:
        current_id = c.resolve_schoolyear_id()
        years = [current_id]
        if alle_jahre:
            years += c.older_schoolyear_ids(current_id)
    tokens = tokenize_search_query(query)
    cur_label = c.schoolyear_label(current_id)
    students: list[dict] = []
    seen_ids: set[int] = set()
    for y in years:
        label = c.schoolyear_label(y)
        current = (y == current_id)
        if fallback:
            raw = c.search_timetable_tokens(query, school_year_id=y)
        else:
            raw = c.search_timetable(query, school_year_id=y)
        hits = [h for h in raw if h.get("type") == "STUDENT"]
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
            try:
                overview = c.get_students_overview()
            except Exception as e:
                print(f"Warnung: students/overview fehlgeschlagen ({e})",
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
    return students, current_id, years


def _faecher_aus_plaenen(c, sy: int, student_id: int,
                         klassenname: str) -> dict:
    """Belegte/nicht belegte Lessons eines Schülers aus Stundenplänen.

    2 Calls: Klassen-Plan (alle Lessons der Klasse) + Schüler-Plan,
    Join über das Fach-Kürzel derselben Klasse. „Belegt" =
    eingeschrieben (Fach erscheint im Schüler-Plan) — Anwesenheit
    spielt KEINE Rolle (kranke Schüler bleiben belegt). Klassenfremde
    Lessons (andere Klasse im Schüler-Plan) werden zusätzlich gelistet.
    Kein Matrix-Call, keine lsId nötig.
    """
    from datetime import date as _date
    from webuntis_agent.cli_lesson import _fetch_class_plan
    from webuntis_agent.client import (
        group_timetable_lessons,
        parse_timetable_entries,
    )
    k = _find_klasse(c, sy, klassenname)
    class_entries, week = _fetch_class_plan(c, int(k["id"]), _date.today())
    student_raw = c.get_timetable_entries(
        "STUDENT", student_id, week[0], week[1])
    student_entries = parse_timetable_entries(student_raw)
    lessons = group_timetable_lessons(class_entries)
    kl_l = (k.get("name") or klassenname).lower()
    # Fach -> Lehrer-Kürzel aus dem Schüler-Plan (eigene Klasse):
    # parallele Gruppen desselben Fachs werden über den Primary-Lehrer
    # unterschieden (z.B. POS1-Gruppen); Anwesenheit spielt keine Rolle.
    subj_teachers: dict[str, set[str]] = {}
    for e in student_entries:
        if (e.get("class") or "").lower() != kl_l or not e.get("subject"):
            continue
        subj_teachers.setdefault(e["subject"].lower(), set()).update(
            t.lower() for t in (e.get("teachers") or []) if t)
    fremd_entries = [e for e in student_entries
                     if e.get("class")
                     and (e.get("class") or "").lower() != kl_l
                     and e.get("subject")]
    fremd: dict[tuple, dict] = {}
    for e in fremd_entries:
        key = ((e.get("class") or "").lower(),
               (e.get("subject") or "").lower())
        g = fremd.setdefault(key, {
            "subject": e["subject"], "subjectLong": e.get("subjectLong"),
            "class": e.get("class"),
            "teachers": [], "dates": []})
        for t in e.get("teachers") or []:
            if t and t not in g["teachers"]:
                g["teachers"].append(t)
        if e.get("date") and e["date"] not in g["dates"]:
            g["dates"].append(e["date"])
    def _lesson_item(g: dict) -> dict:
        return {"subject": g.get("subject"),
                "subjectLong": g.get("subjectLong"),
                "teachers": g.get("teachers"),
                "primaryTeacher": g.get("primaryTeacher"),
                "parallel": bool(g.get("parallel")),
                "rooms": g.get("rooms") or [],
                "termine": len(g.get("entries") or g.get("dates") or [])}
    def _is_belegt(g: dict) -> bool:
        subj_l = (g.get("subject") or "").lower()
        if subj_l not in subj_teachers:
            return False
        tset = subj_teachers[subj_l]
        primary = g.get("primaryTeacher")
        return primary is None or not tset or primary.lower() in tset
    belegt = [_lesson_item(g) for g in lessons if _is_belegt(g)]
    nicht_belegt = [_lesson_item(g) for g in lessons if not _is_belegt(g)]
    # Fach im Schüler-Plan, aber keine Gruppe passt (Vertretungs-Woche):
    unmatched = sorted(
        s for s in subj_teachers
        if not any((g.get("subject") or "").lower() == s and _is_belegt(g)
                   for g in lessons))
    if unmatched:
        print(f"Hinweis: Gruppe nicht eindeutig zuordenbar "
              f"(Lehrer-Abweichung im Schüler-Plan?): "
              f"{', '.join(unmatched)}", file=sys.stderr)
    return {"belegt": sorted(belegt, key=lambda e: e["subject"] or ""),
            "klassenfremd": sorted(
                [_lesson_item(g) for g in fremd.values()],
                key=lambda e: (e.get("class") or "", e["subject"] or "")),
            "nichtBelegt": sorted(nicht_belegt,
                                  key=lambda e: e["subject"] or ""),
            "woche": {"start": week[0], "end": week[1]},
            "quelle": "stundenplan"}


def _absenzen_eigene_lessons(c, sy: int, student_id: int,
                             klassenname: str, pause: float = 1.0) -> dict:
    """Absenz-Übersicht über die EIGENEN Lessons der Klasse (opt-in).

    Quelle: Mein Stundenplan (MY_TIMETABLE) ∩ Klasse → je Lesson ein
    calendar-entry/detail-Call (lsId) + eine Matrix. Gezählt werden nur
    gehaltene Termine (bis heute). Fremde Lessons der Klasse werden
    nicht geprüft (deren Absenzenkontrolle obliegt deren Lehrer).
    """
    from datetime import date as _date
    from webuntis_agent.cli_lesson import (
        _entry_dt,
        _fetch_class_plan,
        _lsid_from_detail,
        _week_bounds,
    )
    from webuntis_agent.client import (
        group_timetable_lessons,
        parse_timetable_entries,
    )
    k = _find_klasse(c, sy, klassenname)
    class_id = int(k["id"])
    _, week = _fetch_class_plan(c, class_id, _date.today())
    kl_l = (k.get("name") or klassenname).lower()
    my_raw = c.get_timetable_entries(
        "TEACHER", c.teacher_id, week[0], week[1],
        timetable_type="MY_TIMETABLE")
    my_entries = [e for e in parse_timetable_entries(my_raw)
                  if (e.get("class") or "").lower() == kl_l
                  and e.get("subject")]
    heute = int(_date.today().isoformat().replace("-", ""))
    rows: list[dict] = []
    fehlt_gesamt = 0
    gehalten_gesamt = 0
    for i, g in enumerate(group_timetable_lessons(my_entries)):
        rep = g["entries"][0]
        try:
            lsid = _lsid_from_detail(c, class_id, rep)
            matrix = c.get_student_lesson_period_matrix(
                lsid, school_year_id=sy)["result"]
        except Exception as e:
            print(f"Warnung: Lesson {g['subject']} nicht prüfbar ({e})",
                  file=sys.stderr)
            continue
        _sleep_between(i, pause)
        s = next((x for x in matrix.get("allStudents", [])
                  if x.get("id") == student_id), None)
        if s is None:
            continue
        gehalten = sorted({p["date"] for p in matrix.get("lessonPeriods", [])
                           if p.get("date", 0) <= heute})
        anwesend = set(s.get("attendedPeriods") or []) & set(gehalten)
        fehlt = len(gehalten) - len(anwesend)
        fehlt_gesamt += fehlt
        gehalten_gesamt += len(gehalten)
        rows.append({"subject": g["subject"],
                     "subjectLong": g.get("subjectLong"),
                     "lsId": lsid,
                     "termineGehalten": len(gehalten),
                     "termineAnwesend": len(anwesend),
                     "termineFehlt": fehlt})
    return {"lessons": sorted(rows, key=lambda r: r["subject"] or ""),
            "gesamt": {"gehalten": gehalten_gesamt, "fehlt": fehlt_gesamt},
            "scope": "eigene Lessons"}


def _print_student_detail(c, sy: int, s: dict,
                          absenzen: bool = False,
                          pause: float = 1.0) -> None:
    """Menschliche Detail-Ausgabe eines aktuellen Schüler-Treffers.

    Einzige Quelle für `student`-Detail und `search --detail` (Dispatch).
    """
    name = (f"{s.get('firstName', '')} {s.get('lastName', '')}".strip()
            or s.get("displayName", ""))
    print(f"\n--- {name} (id={s['id']}), Klasse {s['class']} ---")
    try:
        kv = _kv_info(c, sy, s["class"])
        for tid, tname in kv["teachers"].items():
            print(f"  KV: {tname}")
    except RuntimeError as e:
        print(f"  KV: ({e})")
    try:
        fa = _faecher_aus_plaenen(c, sy, s["id"], s["class"])
    except RuntimeError as e:
        print(f"  Fächer: ({e})")
        return
    w = fa["woche"]
    print(f"  Belegte Fächer (Klasse {s['class']}, Stundenplan "
          f"{w['start']}..{w['end']}):")
    for e in fa["belegt"]:
        lehrer = f"  Lehrer: {'/'.join(e['teachers'])}" if e["teachers"] \
            else ""
        print(f"    {e['subject']:8} Termine/Woche: {e['termine']}{lehrer}")
    if fa["klassenfremd"]:
        print("  Klassenfremde Lessons (andere Klasse):")
        for e in fa["klassenfremd"]:
            print(f"    {e['subject']:8} ({e['class']})  "
                  f"Termine/Woche: {e['termine']}")
    if fa["nichtBelegt"]:
        print("  Nicht belegte Fächer (Klasse):")
        for e in fa["nichtBelegt"]:
            print(f"    {e['subject']:8} Termine/Woche: {e['termine']}")
    if not absenzen:
        print("  (Absenzen: `--absenzen` für die eigenen Lessons)")
        return
    try:
        ab = _absenzen_eigene_lessons(c, sy, s["id"], s["class"],
                                      pause=pause)
    except RuntimeError as e:
        print(f"  Absenzen: ({e})")
        return
    print(f"  Absenzen ({ab['scope']}):")
    for r in ab["lessons"]:
        print(f"    {r['subject']:8} anwesend "
              f"{r['termineAnwesend']}/{r['termineGehalten']}  "
              f"fehlt {r['termineFehlt']}")
    g = ab["gesamt"]
    print(f"    gesamt: {g['fehlt']} von {g['gehalten']} gehaltenen "
          f"Stunden gefehlt")


def cmd_student(args: argparse.Namespace) -> int:
    """Alle Infos zu einem Schüler: Treffer, Klasse, KV, Fächer, Absenzen."""
    c = _make_client(args)
    override = args.school_year_id
    sy = c.resolve_schoolyear_id(override=override)
    students, current_id, years = _suchen(
        c, sy, args.name, args.wortteile, args.alle_jahre, override)
    if getattr(args, "klasse", None):
        kl = args.klasse.lower()
        students = [s for s in students
                    if (s.get("class") or "").lower() == kl
                    or (s.get("shortName") or "").lower() == kl]
    if args.json:
        payload: dict = {
            "query": args.name,
            "currentSchoolYear": {"id": current_id,
                                  "name": c.schoolyear_label(current_id)},
            "yearsSearched": years,
            "students": students,
        }
        details = []
        for s in students:
            if not s.get("current") or not s.get("class"):
                continue
            try:
                kv = _kv_info(c, current_id, s["class"])
                fa = _faecher_aus_plaenen(c, current_id, s["id"],
                                          s["class"])
                ab = (_absenzen_eigene_lessons(
                    c, current_id, s["id"], s["class"],
                    pause=getattr(args, "pause", 1.0))
                    if args.absenzen else None)
            except RuntimeError as e:
                details.append({"id": s["id"], "error": str(e)})
                continue
            details.append({"id": s["id"], "kv": kv["teachers"],
                            "class": s["class"], **fa, "absenzen": ab})
        if details:
            payload["details"] = details
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if not students:
        print("(keine Treffer)")
        return 0
    current_hits = [s for s in students if s.get("current")]
    old_hits = [s for s in students if not s.get("current")]
    print(f"{len(students)} Treffer für {args.name!r}:")
    for s in current_hits:
        name = (f"{s.get('firstName', '')} {s.get('lastName', '')}".strip()
                or s.get("displayName", ""))
        cls = f" — Klasse {s['class']}" if s.get("class") else ""
        note = f"  [{s['searchNote']}]" if s.get("searchNote") else ""
        print(f"  id={s['id']:>6}  {s.get('shortName', ''):12} "
              f"{name}{cls}{note}")
    for s in old_hits:
        year = s.get("schoolYear") or {}
        name = (f"{s.get('firstName', '')} {s.get('lastName', '')}".strip()
                or s.get("displayName", ""))
        note = f"  [{s['searchNote']}]" if s.get("searchNote") else ""
        print(f"  id={s['id']:>6}  {s.get('shortName', ''):12} "
              f"{name}  [SJ {year.get('name', '?')} "
              f"(id {year.get('id', '?')}) — NICHT AKTUELL]{note}")
    if old_hits and not current_hits:
        print("ACHTUNG: aktuell NICHT im System — nur Treffer aus "
              "älteren Schuljahren.", file=sys.stderr)
        return 0
    # Detail je aktuellem Treffer mit Klasse
    for s in [x for x in current_hits if x.get("class")]:
        _print_student_detail(c, current_id, s,
                              absenzen=args.absenzen,
                              pause=getattr(args, "pause", 1.0))
    return 0

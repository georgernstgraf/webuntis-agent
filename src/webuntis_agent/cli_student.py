"""CLI student-Befehle: alles zu einem Schüler (Singular).

Sucht per tokenisierender Stundenplan-Suche (mit automatischem Fallback
in ältere Schuljahre) und reichert aktuelle Treffer aus students/overview
an (volle Namen + Klasse). Detail je aktuellem Schüler: Klasse, KV,
belegte/nicht belegte Fächer und Absenz-Übersicht aus den
Lesson-Matrizen seiner Klasse.
"""

from __future__ import annotations

import argparse
import json
import sys

from webuntis_agent.cli_common import (
    _group_lesson_entries,
    _make_client,
    _open_period_entries,
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


def _faecher_und_absenzen(c, sy: int, student_id: int,
                          klassenname: str) -> dict:
    """Belegte/nicht belegte Fächer + Absenzen eines Schülers.

    Scannt die Matrizen aller Lessons seiner Klasse (Zeitraum:
    Schuljahresstart bis heute): belegt = mindestens ein gehaltener Termin
    besucht; Absenzen = gehaltene Termine ohne Anwesenheit, je Fach und
    gesamt. Externe Lessons (außerhalb der eigenen Klasse) werden nicht
    gescannt — Hinweis im Ergebnis.
    """
    from datetime import date as _date
    syr = next((y for y in c.get_schoolyears() if int(y["id"]) == sy), None)
    if syr is None:
        raise RuntimeError(f"Schuljahr {sy} nicht gefunden")
    start = str(syr["dateRange"]["start"])[:10]
    heute = _date.today()
    heute_ymd = int(heute.isoformat().replace("-", ""))
    entries = _open_period_entries(c, sy, start, heute.isoformat())
    kl_l = klassenname.lower()
    entries = [e for e in entries if (e.get("class") or "").lower() == kl_l]
    groups = _group_lesson_entries(entries)
    print(f"{len(groups)} Lessons von {klassenname} werden geprüft …",
          file=sys.stderr)
    belegt: list[dict] = []
    nicht_belegt: list[dict] = []
    fehlt_gesamt = 0
    gehalten_gesamt = 0
    for g in groups:
        lsid = g.get("lsId")
        if lsid is None:
            continue
        try:
            matrix = c.get_student_lesson_period_matrix(lsid)["result"]
        except Exception as e:
            print(f"Warnung: Matrix lsId {lsid} fehlgeschlagen ({e})",
                  file=sys.stderr)
            continue
        s = next((x for x in matrix.get("allStudents", [])
                  if x.get("id") == student_id), None)
        if s is None:
            continue
        gehalten = sorted({p["date"] for p in matrix.get("lessonPeriods", [])
                           if p.get("date", 0) <= heute_ymd})
        anwesend = set(s.get("attendedPeriods") or []) & set(gehalten)
        fehlt = len(gehalten) - len(anwesend)
        fehlt_gesamt += fehlt
        gehalten_gesamt += len(gehalten)
        eintrag = {"subject": g.get("subject"),
                   "subjectLong": g.get("subjectLong"),
                   "lsId": lsid,
                   "termineGehalten": len(gehalten),
                   "termineAnwesend": len(anwesend),
                   "termineFehlt": fehlt}
        (belegt if anwesend else nicht_belegt).append(eintrag)
    return {"belegt": sorted(belegt, key=lambda e: e["subject"] or ""),
            "nichtBelegt": sorted(nicht_belegt,
                                  key=lambda e: e["subject"] or ""),
            "absenzenGesamt": {"gehalten": gehalten_gesamt,
                               "fehlt": fehlt_gesamt},
            "hinweis": "nur Lessons der eigenen Klasse gescannt; "
                       "klassenfremde Teilnahme (z.B. Gruppen) nicht enthalten"}


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
                fa = _faecher_und_absenzen(c, current_id, s["id"],
                                           s["class"])
            except RuntimeError as e:
                details.append({"id": s["id"], "error": str(e)})
                continue
            details.append({"id": s["id"], "kv": kv["teachers"],
                            "class": s["class"], **fa})
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
        name = (f"{s.get('firstName', '')} {s.get('lastName', '')}".strip()
                or s.get("displayName", ""))
        print(f"\n--- {name} (id={s['id']}), Klasse {s['class']} ---")
        try:
            kv = _kv_info(c, current_id, s["class"])
            for tid, tname in kv["teachers"].items():
                print(f"  KV: {tname}")
        except RuntimeError as e:
            print(f"  KV: ({e})")
        try:
            fa = _faecher_und_absenzen(c, current_id, s["id"], s["class"])
        except RuntimeError as e:
            print(f"  Fächer: ({e})")
            continue
        print("  Belegte Fächer:")
        for e in fa["belegt"]:
            print(f"    {e['subject']:8} anwesend "
                  f"{e['termineAnwesend']}/{e['termineGehalten']}  "
                  f"fehlt {e['termineFehlt']}")
        if fa["nichtBelegt"]:
            print("  Nicht belegte Fächer:")
            for e in fa["nichtBelegt"]:
                print(f"    {e['subject']:8} ({e['termineGehalten']} "
                      f"gehaltene Termine)")
        g = fa["absenzenGesamt"]
        print(f"  Absenzen gesamt: {g['fehlt']} von {g['gehalten']} "
              f"gehaltenen Stunden gefehlt")
    return 0

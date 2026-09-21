"""CLI search-Befehl (Top-Level): Personen/Klassen suchen mit Dispatch.

Standard: Trefferliste (Klassen/Lehrer/Schüler). Mit --detail und genau
einem Treffer wird direkt die passende Sicht geöffnet: Schüler →
Student-Detail, Lehrer → Lehrer-Steckbrief (KV-Klassen), Klasse →
Klassen-Übersicht. Fremde Lehrer-Stundenpläne sind via API nicht lesbar
(s. PITFALLS.md) — daher kein Wochenplan beim Lehrer.
"""

from __future__ import annotations

import argparse
import json
import sys

from webuntis_agent.cli_common import (
    _annotate_search_hits,
    _format_search_hit,
    _make_client,
)


def cmd_search(args: argparse.Namespace) -> int:
    """Klassen/Lehrer/Schüler per Text suchen (volle Namen inklusive).

    Standard (ohne Flags): exakte Einzelabfrage in einem Schuljahr.
    --wortteile ergänzt die tokenisierende Suche (Vor-/Nachname einzeln),
    --alle-jahre wiederholt über ältere Schuljahre (Treffer als NICHT
    AKTUELL markiert). Mit --detail und genau einem Treffer öffnet sich
    die Detail-Sicht (Student/Klasse/Lehrer).
    """
    c = _make_client(args)
    override = args.school_year_id
    sy = c.resolve_schoolyear_id(override=override)
    use_fallback = bool(getattr(args, "wortteile", False))
    use_all_years = bool(getattr(args, "alle_jahre", False))
    if not use_fallback and not use_all_years:
        results = c.search_timetable(args.anfrage, school_year_id=sy)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
            return 0
        if not results:
            print("(keine Treffer)")
            print("Hinweis: --wortteile (Vor-/Nachname einzeln), "
                  "--alle-jahre (ältere Schuljahre) oder "
                  "`student <Name>` (Schüler, Auto-Fallback) versuchen.",
                  file=sys.stderr)
            return 0
        for hit in results:
            res = hit.get("resource", {})
            print(
                f"{hit.get('type', '?'):>8}  id={res.get('id'):>6}  "
                f"{res.get('shortName', ''):12} "
                f"{res.get('displayName') or res.get('longName', '')}"
            )
        if getattr(args, "detail", False):
            return _dispatch(c, sy, args, results)
        return 0
    years = [sy]
    if use_all_years and override is None:
        years += c.older_schoolyear_ids(sy)
    results = []
    for y in years:
        if use_fallback:
            hits = c.search_timetable_tokens(args.anfrage, school_year_id=y)
        else:
            hits = c.search_timetable(args.anfrage, school_year_id=y)
        results.extend(_annotate_search_hits(hits, c, y, sy))
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    if not results:
        print("(keine Treffer)")
        return 0
    for hit in results:
        print(_format_search_hit(hit))
    if any(hit.get("current") is False for hit in results):
        print("ACHTUNG: markierte Treffer sind NICHT AKTUELL — "
              "nur in älteren Schuljahren gefunden.", file=sys.stderr)
    if getattr(args, "detail", False):
        return _dispatch(c, sy, args, results)
    return 0


def _dispatch(c, sy: int, args: argparse.Namespace,
              results: list[dict]) -> int:
    """Detail-Sicht für genau einen Treffer öffnen."""
    if len(results) != 1:
        print(f"--detail braucht genau einen Treffer "
              f"({len(results)} gefunden)", file=sys.stderr)
        return 2
    hit = results[0]
    typ = hit.get("type")
    res = hit.get("resource", {})
    if typ == "STUDENT":
        return _dispatch_student(c, sy, args, hit, res)
    if typ == "TEACHER":
        return _dispatch_teacher(c, sy, args, res)
    if typ == "CLASS":
        return _dispatch_class(args, res)
    print(f"--detail für Typ {typ!r} nicht unterstützt", file=sys.stderr)
    return 2


def _dispatch_student(c, sy: int, args: argparse.Namespace,
                      hit: dict, res: dict) -> int:
    """Student-Treffer → dieselbe Ausgabe wie `student` (Detail)."""
    from webuntis_agent.cli_student import _faecher_und_absenzen
    from webuntis_agent.cli_klasse import _kv_info
    sid = res.get("id")
    overview = {}
    try:
        ov = c.get_students_overview()
        overview = {s.get("id"): s for s in ov.get("students", [])}
    except Exception as e:
        print(f"Warnung: students/overview fehlgeschlagen ({e})",
              file=sys.stderr)
    s = overview.get(sid)
    if s is None:
        print(f"Schüler id={sid} ist aktuell NICHT im System "
              "(nur Treffer aus älteren Schuljahren) — keine Detaildaten.",
              file=sys.stderr)
        return 0
    name = f"{s.get('firstName', '')} {s.get('lastName', '')}".strip()
    ci = s.get("classInfo") or {}
    klass = ci.get("name", "")
    print(f"\n--- {name} (id={sid}), Klasse {klass} ---")
    try:
        kv = _kv_info(c, sy, klass)
        for tid, tname in kv["teachers"].items():
            print(f"  KV: {tname}")
    except RuntimeError as e:
        print(f"  KV: ({e})")
    try:
        fa = _faecher_und_absenzen(c, sy, sid, klass)
    except RuntimeError as e:
        print(f"  Fächer: ({e})")
        return 0
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


def _dispatch_teacher(c, sy: int, args: argparse.Namespace,
                      res: dict) -> int:
    """Lehrer-Treffer → Steckbrief + KV-Klassen (kein Wochenplan möglich)."""
    tid = res.get("id")
    print(f"{res.get('displayName') or res.get('longName', '')} "
          f"(Kürzel {res.get('shortName', '')}, Lehrer-ID {tid})")
    try:
        klassen = c.get_klassen(schoolyear_id=sy)
        klassen = klassen.get("result", []) \
            if isinstance(klassen, dict) else klassen
    except Exception as e:
        print(f"  KV-Klassen: (nicht ladbar: {e})")
        return 0
    kv_klassen = [k.get("name", "?") for k in klassen
                  if tid in [k.get("teacher1"), k.get("teacher2"),
                             k.get("teacher3")]]
    if kv_klassen:
        print(f"  KV in: {', '.join(sorted(kv_klassen))}")
    else:
        print("  KV in: (keine Klasse)")
    print("  Hinweis: Wochenstundenplan fremder Lehrer ist via API nicht "
          "lesbar; eigene Lessons via `klasse <KLASSE>` prüfen.")
    return 0


def _dispatch_class(args: argparse.Namespace, res: dict) -> int:
    """Klassen-Treffer → dieselbe Ausgabe wie `klasse` (Übersicht)."""
    from webuntis_agent.cli_klasse import cmd_klasse
    name = res.get("shortName") or res.get("longName") or ""
    sub = argparse.Namespace(
        klassenname=name, json=args.json, start=None, end=None,
        fach=None, school_year_id=args.school_year_id,
    )
    return cmd_klasse(sub)

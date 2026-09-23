"""CLI lehrer-Befehl: alles zu einem Lehrer (Singular).

Sucht einen Lehrer per Kürzel/Name (tokenisierender Stundenplan-Suche
mit optionalem Fallback in ältere Schuljahre) und zeigt den Steckbrief:
Kürzel, Lehrer-ID und die KV-Klassen (aus getKlassen teacher1/2/3).

Fremde Lehrer-Stundenpläne sind via API nicht lesbar (403/„not
authenticated", s. PITFALLS.md) — daher kein Wochenplan.
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


def _lehrer_suchen(c, sy: int, query: str, fallback: bool,
                   alle_jahre: bool, override: int | None) -> tuple:
    """Lehrer-Suche im aktuellen Jahr + optional älteren.

    Liefert (Treffer, current_id, years). Treffer aus älteren Jahren
    tragen `current: False` (NICHT AKTUELL).
    """
    if override is not None:
        years = [override]
        current_id = override
    else:
        current_id = c.resolve_schoolyear_id()
        years = [current_id]
        if alle_jahre:
            years += c.older_schoolyear_ids(current_id)
    hits: list[dict] = []
    seen: set[int] = set()
    for y in years:
        raw = (c.search_timetable_tokens(query, school_year_id=y)
               if fallback else c.search_timetable(query, school_year_id=y))
        for h in _annotate_search_hits(raw, c, y, current_id):
            res = h.get("resource", {})
            if h.get("type") != "TEACHER" or res.get("id") in seen:
                continue
            seen.add(res.get("id"))
            hits.append(h)
    return hits, current_id, years


def _print_lehrer_detail(c, sy: int, res: dict) -> None:
    """Steckbrief eines Lehrers: Kürzel, ID und KV-Klassen."""
    tid = res.get("id")
    name = res.get("displayName") or res.get("longName", "")
    print(f"\n--- {name} (Kürzel {res.get('shortName', '')}, "
          f"Lehrer-ID {tid}) ---")
    try:
        klassen = c.get_klassen(schoolyear_id=sy)
        klassen = klassen.get("result", []) \
            if isinstance(klassen, dict) else klassen
    except Exception as e:
        print(f"  KV-Klassen: (nicht ladbar: {e})")
        return
    kv_klassen = [k.get("name", "?") for k in klassen
                  if tid in [k.get("teacher1"), k.get("teacher2"),
                             k.get("teacher3")]]
    if kv_klassen:
        print(f"  KV in: {', '.join(sorted(kv_klassen))}")
    else:
        print("  KV in: (keine Klasse)")
    print("  Hinweis: Wochenstundenplan fremder Lehrer ist via API nicht "
          "lesbar; eigene Lessons via `klasse <KLASSE>` prüfen.")


def cmd_lehrer(args: argparse.Namespace) -> int:
    """Alles zu einem Lehrer: Treffer, Kürzel, KV-Klassen."""
    c = _make_client(args)
    override = args.school_year_id
    sy = c.resolve_schoolyear_id(override=override)
    hits, current_id, years = _lehrer_suchen(
        c, sy, args.name, args.wortteile, args.alle_jahre, override)
    if args.json:
        payload: dict = {
            "query": args.name,
            "currentSchoolYear": {"id": current_id,
                                  "name": c.schoolyear_label(current_id)},
            "yearsSearched": years,
            "lehrer": hits,
        }
        details = []
        for h in hits:
            if not h.get("current"):
                continue
            res = h.get("resource", {})
            try:
                klassen = c.get_klassen(schoolyear_id=current_id)
                klassen = klassen.get("result", []) \
                    if isinstance(klassen, dict) else klassen
            except Exception as e:
                details.append({"id": res.get("id"), "error": str(e)})
                continue
            tid = res.get("id")
            details.append({
                "id": tid,
                "shortName": res.get("shortName", ""),
                "displayName": (res.get("displayName")
                                or res.get("longName", "")),
                "kv": [k.get("name", "?") for k in klassen
                       if tid in [k.get("teacher1"), k.get("teacher2"),
                                  k.get("teacher3")]],
            })
        if details:
            payload["details"] = details
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if not hits:
        print(f"(keine Treffer für {args.name!r})")
        print("Hinweis: --wortteile (Vor-/Nachname einzeln) oder "
              "--alle-jahre (ältere Schuljahre) versuchen.",
              file=sys.stderr)
        return 0
    current = [h for h in hits if h.get("current")]
    old = [h for h in hits if not h.get("current")]
    print(f"{len(hits)} Treffer für {args.name!r}:")
    for h in current + old:
        print(_format_search_hit(h))
    if old and not current:
        print("ACHTUNG: markierte Treffer sind NICHT AKTUELL — nur in "
              "älteren Schuljahren gefunden.", file=sys.stderr)
    for h in current:
        _print_lehrer_detail(c, current_id, h.get("resource", {}))
    return 0

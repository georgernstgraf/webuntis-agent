"""CLI lesson-Befehle: alles zu einer Lesson (KLASSE/FACH).

Eine Lesson ist ein Unterrichtsfach innerhalb einer Klasse
(z.B. 3AHWII/SWP1x). Alle Befehle arbeiten auf der
Anwesenheits-Matrix dieser Lesson (getStudentLessonPeriodMatrix).
"""

from __future__ import annotations

import argparse
import json
import sys

from typing import TYPE_CHECKING

from webuntis_agent.cli_common import (
    _datum_arg,
    _make_client,
    _open_period_entries,
    _read_text_arg,
    _resolve_topic_id,
    _sleep_between,
    _split_klasse_fach,
)

if TYPE_CHECKING:
    from webuntis_agent.client import Client


def _teacher_names_for_class(c: Client, class_id: int,
                             teacher_ids: list[int],
                             school_year_id: int | None) -> dict[int, str]:
    """Lehrer-IDs -> Anzeigenamen via Wochenstundenplan-Kürzel + Suche.

    getTeachers ist für Lehrer-Accounts 403 — daher der Umweg über den
    Stundenplan (Kürzel) plus Stundenplan-Suche (Vollname).
    """
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
    """lsId wählen, deren Termine am besten zu ref_date (YYYY-MM-DD) passen.

    Exakter Datumstreffer (Abstand 0) gewinnt, sonst kleinster absoluter
    Tagesabstand; Gleichstand entscheidet die kleinste lsId (deterministisch).
    Reine Funktion (kein Netz) — unit-getestet.
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
    """Nächster Termin zu ref_date (beide YYYY-MM-DD).

    Kleinster absoluter Tagesabstand; Gleichstand gewinnt das frühere Datum.
    Reine Funktion (kein Netz) — unit-getestet.
    """
    from datetime import date as _date
    ref = _date.fromisoformat(ref_date)
    return min(dates, key=lambda d: (abs((_date.fromisoformat(d) - ref).days),
                                     d))


def _resolve_lesson_from_class_subject(
        c: Client, sy: int, class_name: str, subject: str,
        ref_date: str | None = None) -> dict:
    """Lesson eines (Klasse, Fach)-Paares finden, Trefferdetails liefern.

    Sucht in einem Fenster um heute (7 Tage zurück, 13 voraus).
    Groß-/Kleinschreibung egal; Fach fällt auf Präfix-Match zurück.
    Liefert `{"lsId", "class", "subject", "dates", "candidates"}` mit den
    exakten Untis-Bezeichnungen. Bei mehreren Treffern wird der nächste zu
    `ref_date` (Standard: heute) gewählt und eine Warnung nach stderr
    geschrieben; ohne Treffer RuntimeError mit Kandidaten.
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
            f"keine Lesson für {class_name}/{subject} in "
            f"{start}..{end}" + (f"; verfügbar für {class_name}: {hints}"
                                 if hints else ""))
    if len(matches) > 1:
        picked = _pick_closest_lesson(
            {lsid: m["dates"] for lsid, m in matches.items()}, ref)
        print(f"Warnung: mehrdeutige Lesson für {class_name}/{subject}: "
              f"{len(matches)} Kandidaten, gewählt lsId={picked} "
              f"(nächste zu {ref})", file=sys.stderr)
        for lsid in sorted(matches):
            m = matches[lsid]
            units = sorted({(u[1], u[2]) for u in m["units"]})
            # eine Zeile je Kandidat: exakte Untis-Bezeichnung + Termin
            # (nächster zu ref; alle Termine einer Lesson teilen sich
            # Klasse/Fach, bei gemischten Daten gewinnt der erste)
            klass, subj = units[0]
            print(f"{klass}/{subj} "
                  f"({_nearest_date(m['dates'], ref)})", file=sys.stderr)
    else:
        picked = next(iter(matches))
    m = matches[picked]
    # Label: bevorzugt der Eintrag auf ref_date (exakte Untis-Bezeichnung
    # des gewünschten Termins), sonst der erste Eintrag der Lesson
    label_unit = next((u for u in m["units"] if u[0] == ref), m["units"][0])
    return {"lsId": picked, "class": label_unit[1],
            "subject": label_unit[2],
            "dates": sorted(set(m["dates"])),
            "candidates": sorted(matches)}


def _resolve_lsid(c: Client, args: argparse.Namespace,
                  ref_date: str | None = None) -> tuple[int, str | None]:
    """lsId aus --lsid oder KLASSE/FACH auflösen.

    Liefert (lsId, lesson_label); label ist None bei direkter --lsid
    (wird dann per Reverse-Lookup bestimmt, wo nötig).
    """
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    if args.lsid is not None:
        return args.lsid, None
    if not getattr(args, "klasse_fach", None):
        print("entweder KLASSE/FACH oder --lsid angeben "
              "(z.B. `lesson 3AHWII/SWP1x`)", file=sys.stderr)
        raise SystemExit(2)
    klasse, fach = _split_klasse_fach(args.klasse_fach)
    try:
        lesson = _resolve_lesson_from_class_subject(
            c, sy, klasse, fach, ref_date=ref_date)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(2)
    print(f"aufgelöst {klasse}/{fach} -> lsId {lesson['lsId']} "
          f"({lesson['class']}/{lesson['subject']})",
          file=sys.stderr)
    return lesson["lsId"], f"{lesson['class']}/{lesson['subject']}"


def _lesson_label_for_lsid(c: Client, sy: int, lsid: int,
                           day: str) -> str | None:
    """Best-effort exaktes 'Klasse/Fach'-Label für eine lsId.

    Reverse-Lookup über offene Perioden am Termin-Tag selbst. Liefert None,
    wenn die Lesson dort keine offenen Perioden hat (alle Lehrstoffe
    eingetragen und Absenzen geprüft) — Aufrufer lassen die Label-Zeile weg.
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


def _tsv_cell(value: object) -> str:
    """Wert TSV-sicher machen (keine Tabs/Zeilenumbrüche in der Zelle)."""
    return str(value if value is not None else "").replace("\t", " ").replace(
        "\n", " ").replace("\r", "")


def _roster_rows(matrix_result: dict, overview_by_id: dict,
                 ymd: int) -> tuple[list[tuple[str, str]], list[str]]:
    """Sortierte (Name-Zelle, Klasse-Zelle)-TSV-Zeilen für ein Termindatum.

    Teilnehmer sind Matrix-Schüler, deren attendedPeriods `ymd` enthält.
    Namen kommen aus students/overview (volle Vor-/Nachnamen — Matrix-Namen
    sind gekürzt); Matrix-Namen sind der Fallback. Liefert
    (Zeilen, nicht_zugeordnete_Namen); Zeilen sortiert nach (Nach, Vor).
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


def cmd_lesson_roster(args: argparse.Namespace) -> int:
    """Excel-einfügbare TSV-Teilnehmerliste für einen Lesson-Termin.

    --datum (YYYY-MM-DD oder 'heute') wählt den Termin: Teilnehmer sind
    Schüler, deren attendedPeriods dieses Datum enthält — dieselbe Menge,
    die Untis bei der Anwesenheitskontrolle dieses Termins zeigt.
    Nur lesend (keine Writes).
    """
    c = _make_client(args)
    day = args.datum
    ymd = int(day.replace("-", ""))
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    lsid, lesson_label = _resolve_lsid(c, args, ref_date=day)
    if lesson_label is None:
        lesson_label = _lesson_label_for_lsid(c, sy, lsid, day)
    result = c.get_student_lesson_period_matrix(
        lsid, school_year_id=args.school_year_id)["result"]
    period_dates = {p.get("date") for p in result.get("lessonPeriods", [])}
    requested_day = day
    if ymd not in period_dates:
        if not period_dates:
            print(f"keine Lesson-Termine für lsId {lsid}", file=sys.stderr)
            return 2
        # Zukunft-zuerst-Fallback: nächster kommender Termin, sonst letzter
        # gehaltener
        future = [d for d in period_dates if d > ymd]
        pick = min(future) if future else max(period_dates)
        day = f"{pick // 10000:04d}-{(pick // 100) % 100:02d}-{pick % 100:02d}"
        ymd = pick
        print(f"Hinweis: kein Termin am {requested_day} für lsId {lsid}, "
              f"nächster Termin {day} wird verwendet", file=sys.stderr)
    try:
        overview = c.get_students_overview()
    except Exception as e:
        print(f"Warnung: students/overview fehlgeschlagen ({e}) — "
              "kurze Matrix-Namen werden verwendet", file=sys.stderr)
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
    if not args.ohne_kopf:
        print("Name\tKlasse")
    for name, klass in rows:
        print(f"{name}\t{klass}")
    expected = next((p.get("studentCount")
                     for p in result.get("lessonPeriods", [])
                     if p.get("date") == ymd), None)
    if expected is not None and expected != len(rows):
        print(f"Warnung: studentCount={expected}, aber {len(rows)} Zeilen",
              file=sys.stderr)
    if unmatched:
        print(f"Hinweis: {len(unmatched)} ohne Overview-Treffer "
              "(kurze Namen verwendet)", file=sys.stderr)
    return 0


def cmd_lesson_matrix(args: argparse.Namespace) -> int:
    """Anwesenheits-Matrix einer Lesson ausgeben (Termine je Schüler).

    Die Lesson wird per --lsid oder KLASSE/FACH angegeben.
    """
    c = _make_client(args)
    lsid, _ = _resolve_lsid(c, args)
    matrix = c.get_student_lesson_period_matrix(
        lsid, school_year_id=args.school_year_id)["result"]
    dates = sorted({p["date"] for p in matrix["lessonPeriods"]})
    students = matrix["allStudents"]
    if args.klassen_id is not None:
        students = [s for s in students if s["klasse"] == args.klassen_id]
    if args.nur_anwesende:
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
    if not args.alle and not args.nur_anwesende:
        attending = [s for s in students if s["attendedPeriods"]]
        print(f"(Textansicht: nur Anwesende, {len(attending)}/{len(students)} "
              f"gezeigt; --alle oder --json für alle)")
        students = attending
    print(f"lsId {lsid} (mainStudentgroupId {matrix['mainStudentgroupId']}): "
          f"{len(dates)} Lesson-Termine, {len(students)} Schüler")
    for s in students:
        n = len(s["attendedPeriods"])
        note = "alle" if n == len(dates) else str(n)
        print(f"  {s['id']:>6}  {s['name']:32} klasse={s['klasse']:>5}  "
              f"Termine: {note}")
    return 0


def cmd_lesson_termine(args: argparse.Namespace) -> int:
    """Alle Termine einer Lesson mit Offen-Status (und optional Lehrstoff).

    Zu jedem Termin zeigt die Lesson ihren Lehrstoff — hier steht je Termin,
    ob er noch offen ist (Lehrstoff fehlt oder Absenzen ungeprüft) oder
    erledigt. Mit --mit-lehrstoff werden zusätzlich die eingetragenen
    Texte geladen (je ein API-Call pro Termin, daher gedrosselt).
    Nur lesend.
    """
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    lsid, lesson_label = _resolve_lsid(c, args)
    result = c.get_student_lesson_period_matrix(
        lsid, school_year_id=args.school_year_id)["result"]
    periods = sorted(result.get("lessonPeriods", []),
                     key=lambda p: p.get("date", 0))
    if not periods:
        print(f"keine Lesson-Termine für lsId {lsid}", file=sys.stderr)
        return 2
    von = args.start or f"{periods[0]['date'] // 10000:04d}-01-01"
    bis = args.end or "9999-12-31"
    offen_ids: set[int] = set()
    try:
        for e in _open_period_entries(c, sy, von, bis):
            if e.get("lsId") == lsid and e.get("periodId") is not None:
                offen_ids.add(e["periodId"])
    except Exception as e:
        print(f"Warnung: Offen-Status nicht ladbar ({e})", file=sys.stderr)
    rows = []
    for i, p in enumerate(periods):
        ymd = p.get("date", 0)
        day = f"{ymd // 10000:04d}-{(ymd // 100) % 100:02d}-{ymd % 100:02d}"
        status = "offen" if p.get("id") in offen_ids else "erledigt"
        text = None
        if args.mit_lehrstoff:
            _sleep_between(i, args.pause)
            try:
                topic = c.get_lesson_topic(p["id"], school_year_id=sy)
                pts = topic.get("periodTopics", [])
                if pts and pts[0].get("topic") and pts[0]["topic"].get("text"):
                    text = pts[0]["topic"]["text"]
            except Exception as e:
                text = f"(Fehler: {e})"
        rows.append({"periodId": p.get("id"), "date": day,
                     "studentCount": p.get("studentCount"),
                     "status": status, "topicText": text})
    if args.json:
        print(json.dumps({"lsId": lsid, "lesson": lesson_label,
                          "termine": rows},
                         indent=2, ensure_ascii=False))
        return 0
    label = f"{lesson_label}: " if lesson_label else f"lsId {lsid}: "
    print(f"{label}{len(rows)} Termine")
    for r in rows:
        line = (f"  {r['periodId']:>10}  {r['date']}  "
                f"{r['status']:8}  Anwesende: {r['studentCount']}")
        if r["topicText"] is not None:
            line += f"  Lehrstoff: {r['topicText'][:80]}"
        print(line)
    return 0


def cmd_lesson_info(args: argparse.Namespace) -> int:
    """Lesson-Diagnostik: Lehrer, Klassen, mainStudentgroupId und
    Roster- vs. Anwesenheits-Verteilung je Klasse."""
    c = _make_client(args)
    lsid, _ = _resolve_lsid(c, args)
    matrix = c.get_student_lesson_period_matrix(
        lsid, school_year_id=args.school_year_id)["result"]
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
        "lsId": lsid,
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
    print(f"lsId {lsid}: {info['lessonSubject']}  "
          f"{len(periods)} Perioden "
          f"({dates[0] if dates else '-'} .. {dates[-1] if dates else '-'})")
    print(f"  mainStudentgroupId: {info['mainStudentgroupId']}")
    print(f"  lessonTeachers: {info['lessonTeachers']}")
    print(f"  lessonKlassen: {info['lessonKlassen']}")
    print("  Klassen-Roster vs. anwesend (nur anwesend > 0; "
          "--json für alles):")
    shown = [d for d in info["klasseDistribution"] if d["attending"] > 0]
    omitted = len(info["klasseDistribution"]) - len(shown)
    for d in shown:
        print(f"    klasse={d['klasse']:>6}  anwesend {d['attending']}/"
              f"{d['total']}  Termine {d['termineMin']}..{d['termineMax']}")
    if omitted:
        print(f"    (+{omitted} Klassen ohne Anwesende)")
    return 0


def _build_students_payload(all_students: list[dict], class_id: int,
                            add_ids: list[int], remove_ids: list[int],
                            lesson_dates: list) -> list[dict]:
    """Teilnehmerliste für submitStudentLessonPeriodData bauen.

    Gemeinsame Edit-Semantik (einzige Quelle für `aufnehmen` und
    `anpassen`): Schüler der Lesson-Klasse unverändert, bereits anwesende
    Schüler JEDER Klasse bleiben (sie zu streichen würde sie abmelden),
    entfernte Schüler bekommen attendedPeriods=[], aufgenommene alle
    Lesson-Termine (mit bestehender Anwesenheit vereint). add_ids und
    remove_ids müssen disjunkt sein — Aufrufer prüfen das.
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


def _finish_teilnehmer_command(c, args: argparse.Namespace,
                               payload: dict, summary: dict,
                               dry_msg: str) -> int:
    """Gemeinsames Ende für `aufnehmen`/`anpassen` (einzige Quelle).

    Behandelt `--ausgabe` (Payload-Dump), `--testlauf` (Standard:
    Zusammenfassung + kein Write) und den einzelnen
    `submitStudentLessonPeriodData`-Write.
    """
    from pathlib import Path
    if args.ausgabe:
        Path(args.ausgabe).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8")
        summary["writtenTo"] = args.ausgabe
    if args.testlauf:
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


def cmd_lesson_aufnehmen(args: argparse.Namespace) -> int:
    """Schüler in die Anwesenheit einer Lesson aufnehmen.

    Lädt die Matrix der Lesson, setzt attendedPeriods des Schülers auf
    alle Lesson-Termine und schickt die kombinierte Payload (Schüler der
    Lesson-Klasse unverändert + aufgenommener Schüler). --testlauf
    (Standard) schreibt die Payload nach --ausgabe und schickt NICHT ab.
    """
    c = _make_client(args)
    lsid, _ = _resolve_lsid(c, args)
    matrix = c.get_student_lesson_period_matrix(
        lsid, school_year_id=args.school_year_id)
    result = matrix["result"]
    all_students = result["allStudents"]
    lesson_dates = sorted({p["date"] for p in result["lessonPeriods"]})

    target = None
    if args.schueler_id:
        target = next((s for s in all_students if s["id"] == args.schueler_id),
                      None)
        if target is None:
            print(f"Schüler-ID {args.schueler_id} nicht in der Matrix gefunden",
                  file=sys.stderr)
            return 2
    else:
        needle = args.schueler_name.lower()
        hits = [s for s in all_students
                if needle in s["name"].lower()]
        if len(hits) != 1:
            for h in hits:
                print(f"  Kandidat: id={h['id']} {h['name']} "
                      f"klasse={h['klasse']}", file=sys.stderr)
            print(f"Schülername '{args.schueler_name}' trifft {len(hits)} "
                  "Schüler; --schueler-id verwenden", file=sys.stderr)
            return 2
        target = hits[0]

    students_payload = _build_students_payload(
        all_students, args.klassen_id, [target["id"]], [], lesson_dates)

    payload = {
        "mainStudentgroupId": result["mainStudentgroupId"],
        "lessonId": lsid,
        "students": students_payload,
        "startDate": result["startDate"],
        "endDate": result["endDate"],
    }

    summary = {
        "student": target,
        "mainStudentgroupId": result["mainStudentgroupId"],
        "lessonDates": lesson_dates,
        "payloadStudents": len(students_payload),
        "payload": payload if args.details else "(mit --details anzeigen)",
    }
    return _finish_teilnehmer_command(
        c, args, payload, summary,
        f"\nTESTLAUF: {target['name']} (id={target['id']}) würde an "
        f"{len(lesson_dates)} Lesson-Terminen von Lesson {lsid} teilnehmen; "
        f"Payload hat {len(students_payload)} Schüler "
        f"(Klassen-Roster + Anwesende bleiben). "
        f"Abschicken mit --ausfuehren.")


def cmd_lesson_anpassen(args: argparse.Namespace) -> int:
    """Anwesenheit einer Lesson ändern: Schüler aufnehmen und/oder entfernen.

    Baut die volle Teilnehmer-Payload (Lesson-Klasse unverändert, sonstige
    Anwesende unverändert, Entfernte auf attendedPeriods=[], Aufgenommene
    auf alle Lesson-Termine) und schickt sie via
    submitStudentLessonPeriodData ab. --testlauf (Standard) schreibt die
    Payload nach --ausgabe und schickt NICHT ab.
    """
    c = _make_client(args)
    lsid, _ = _resolve_lsid(c, args)
    matrix = c.get_student_lesson_period_matrix(
        lsid, school_year_id=args.school_year_id)
    result = matrix["result"]
    all_students = result["allStudents"]
    lesson_dates = sorted({p["date"] for p in result["lessonPeriods"]})

    add_ids = args.aufnehmen_id or []
    remove_ids = args.entfernen_id or []
    if not add_ids and not remove_ids:
        print("nichts zu tun: --aufnehmen-id und/oder --entfernen-id angeben",
              file=sys.stderr)
        return 2
    overlap = set(add_ids) & set(remove_ids)
    if overlap:
        print(f"IDs gleichzeitig aufgenommen und entfernt: {sorted(overlap)}",
              file=sys.stderr)
        return 2
    by_id = {s["id"]: s for s in all_students}
    for sid in add_ids + remove_ids:
        if sid not in by_id:
            print(f"Schüler-ID {sid} nicht in der Matrix gefunden",
                  file=sys.stderr)
            return 2

    keep = _build_students_payload(
        all_students, args.klassen_id, add_ids, remove_ids, lesson_dates)

    payload = {
        "mainStudentgroupId": result["mainStudentgroupId"],
        "lessonId": lsid,
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
        "payload": payload if args.details else "(mit --details anzeigen)",
    }
    return _finish_teilnehmer_command(
        c, args, payload, summary,
        f"\nTESTLAUF: +{[by_id[i]['name'] for i in add_ids]} "
        f"-{[by_id[i]['name'] for i in remove_ids]} "
        f"in Lesson {lsid} ({len(lesson_dates)} Lesson-Termine); "
        f"Payload hat {len(keep)} Schüler. "
        f"Abschicken mit --ausfuehren.")


def cmd_lehrstoff_zeigen(args: argparse.Namespace) -> int:
    """Eingetragenen Lehrstoff eines Termins anzeigen."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    data = c.get_lesson_topic(args.termin, school_year_id=sy)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def cmd_lehrstoff_eintragen(args: argparse.Namespace) -> int:
    """Lehrstoff für einen Termin eintragen (einzelner Write)."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    if args.thema is None:
        args.thema = _resolve_topic_id(c, sy, args.termin, None)
        print(f"aufgelöste thema-id={args.thema}")
    text = _read_text_arg(args)
    res = c.set_lesson_topic(
        args.termin, args.thema, text,
        school_year_id=sy,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_lehrstoff_aus_git(args: argparse.Namespace) -> int:
    """Lehrstoff-Text aus den GRG-*-Git-Logs ableiten.

    Mit --testlauf (Standard): Commits + Diffs zeigen, nichts schreiben.
    Mit --ausfuehren: --termin-id und --thema-id nötig, Text wird
    eingetragen.
    """
    from webuntis_agent.client import repos_for_subject
    from webuntis_agent.gitlog import (
        get_commit_diff_by_name,
        get_commits_for_class,
        format_commits,
    )
    klasse, fach = _split_klasse_fach(args.klasse_fach)
    repos = repos_for_subject(fach)
    if not repos:
        print(
            f"WARNUNG: Fach '{fach}' nicht in SUBJECT_REPO_MAP — "
            "in src/webuntis_agent/client.py ergänzen",
            file=sys.stderr,
        )
        return 3
    d = _datum_arg(args.datum)
    from datetime import date as _date
    commits = get_commits_for_class(
        klasse, _date.fromisoformat(d), repo_filter=repos,
    )
    if not commits:
        text = f"(kein Unterricht gefunden für {klasse} am {d})"
        if args.testlauf:
            print(f"durchsuchte Repos: {repos}")
            print(f"würde eintragen: {text}")
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
        if args.testlauf:
            print(f"würde eintragen: termin={args.termin} text={text!r}")
            return 0
    if args.termin is None or args.thema is None:
        print("nötig: --termin-id und --thema-id (oder --testlauf)",
              file=sys.stderr)
        return 2
    client = _make_client(args)
    sy = client.resolve_schoolyear_id(override=args.school_year_id)
    res = client.set_lesson_topic(args.termin, args.thema, text,
                                  school_year_id=sy)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_absenzen_zeigen(args: argparse.Namespace) -> int:
    """Grobe Absenz-Zusammenfassung je Schüler: fehlende vs. gehaltene Stunden.

    Gezählt werden nur Termine bis einschließlich heute — zukünftige
    Termine fließen nicht ein. Grundlage ist die Anwesenheits-Matrix
    (Anwesenheit je Termin), keine separaten Absenz-Records.
    Nur lesend.
    """
    from datetime import date as _date
    c = _make_client(args)
    lsid, lesson_label = _resolve_lsid(c, args)
    result = c.get_student_lesson_period_matrix(
        lsid, school_year_id=args.school_year_id)["result"]
    heute = int(_date.today().isoformat().replace("-", ""))
    gehalten = sorted({p["date"] for p in result.get("lessonPeriods", [])
                       if p.get("date", 0) <= heute})
    gehalten_set = set(gehalten)
    alle = result.get("allStudents", [])
    if not args.alle and not args.nur_fehlende:
        teilnehmer = [s for s in alle if s.get("attendedPeriods")]
        print(f"(nur je Anwesende, {len(teilnehmer)}/{len(alle)} gezeigt; "
              f"--alle oder --json für alle)")
        alle = teilnehmer
    rows = []
    for s in alle:
        anwesend = sorted(set(s.get("attendedPeriods") or []) & gehalten_set)
        fehlt = len(gehalten) - len(anwesend)
        rows.append({"id": s.get("id"), "name": s.get("name"),
                     "klasse": s.get("klasse"),
                     "gehalten": len(gehalten), "anwesend": len(anwesend),
                     "fehlt": fehlt})
    if args.nur_fehlende:
        rows = [r for r in rows if r["fehlt"] > 0]
    rows.sort(key=lambda r: (-r["fehlt"], str(r["name"])))
    if args.json:
        print(json.dumps({"lsId": lsid, "lesson": lesson_label,
                          "termineGehalten": len(gehalten),
                          "absenzen": rows},
                         indent=2, ensure_ascii=False))
        return 0
    label = f"{lesson_label}: " if lesson_label else f"lsId {lsid}: "
    print(f"{label}{len(gehalten)} gehaltene Termine, "
          f"{len(rows)} Schüler")
    for r in rows:
        print(f"  {r['id']:>6}  {r['name']:32} "
              f"anwesend {r['anwesend']}/{r['gehalten']}  "
              f"fehlt {r['fehlt']}")
    return 0


def cmd_absenzen_pruefen(args: argparse.Namespace) -> int:
    """Absenzenkontrolle für eine Lesson durchführen (Write).

    Mit --termin-id: genau dieser Termin. Ohne: alle ungeprüften Termine
    dieser Lesson im Zeitraum (--von/--bis, Standard: Schuljahresstart bis
    heute). Zwischen den Calls --pause Sekunden (IP-Rate-Limit).
    """
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    results: list[dict] = []
    if args.termin is not None:
        pids = [args.termin]
    else:
        from datetime import date as _date
        lsid, _ = _resolve_lsid(c, args)
        von = args.start
        bis = args.end or _date.today().isoformat()
        if von is None:
            syr = next((y for y in c.get_schoolyears()
                        if int(y["id"]) == sy), None)
            if syr is None:
                print(f"Schuljahr {sy} nicht gefunden", file=sys.stderr)
                return 2
            von = str(syr["dateRange"]["start"])[:10]
        raw = c.get_open_periods(von, bis, school_year_id=sy).get("periods",
                                                                  [])
        pids = [p.get("period", {}).get("id") for p in raw
                if p.get("absCheckNeeded")
                and p.get("period", {}).get("lsId") == lsid
                and p.get("period", {}).get("id") is not None]
        print(f"{len(pids)} ungeprüfte Termine der Lesson im Zeitraum "
              f"{von}..{bis}", file=sys.stderr)
        if not pids:
            print("[]")
            return 0
    for i, pid in enumerate(pids):
        _sleep_between(i, args.pause)
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
    print(f"\n{ok}/{len(results)} Absenzen geprüft", file=sys.stderr)
    return 0 if ok == len(results) else 1

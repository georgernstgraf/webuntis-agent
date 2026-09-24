"""Timetable-Parser: entries -> Entries -> Lessons (reine Funktionen).

No network, fictitious data only (anonymized — no real ids/names).
"""

from webuntis_cli.client import (
    group_timetable_lessons,
    parse_dojo_viewmodel,
    parse_timetable_entries,
)


def _cur(typ, short, long_=None):
    return {"type": typ, "status": "REGULAR", "shortName": short,
            "longName": long_, "displayName": short}


def _grid(day, start, end, ids, positions):
    return {"ids": ids, "duration": {"start": f"{day}T{start}",
                                     "end": f"{day}T{end}"},
            "type": "NORMAL_TEACHING_PERIOD", "status": "REGULAR",
            **{f"position{i}": arr for i, arr in positions.items()}}


def _class_plan_days():
    # Klassen-Plan: Positionen 1=Lehrer 2=Fach 3=Raum 4=null (Klasse
    # steht im day.resource); gleiche Lesson zweimal pro Woche
    return [
        {"date": "2026-09-14", "resourceType": "CLASS",
         "resource": {"id": 111, "shortName": "5XZY",
                      "longName": "Fiktive Klasse"},
         "status": "REGULAR",
         "dayEntries": [],
         "gridEntries": [
             _grid("2026-09-14", "08:00", "08:50", [11], {
                 1: [{"current": _cur("TEACHER", "MUS", "Musterlehrerin"),
                      "removed": None}],
                 2: [{"current": _cur("SUBJECT", "POS1", "Fiktives Fach"),
                      "removed": None}],
                 3: [{"current": _cur("ROOM", "A1.01", "Stammklasse"),
                      "removed": None}],
                 4: None}),
         ],
         "backEntries": []},
        {"date": "2026-09-16", "resourceType": "CLASS",
         "resource": {"id": 111, "shortName": "5XZY",
                      "longName": "Fiktive Klasse"},
         "status": "REGULAR",
         "dayEntries": [],
         "gridEntries": [
             # Block (2 Perioden) + SUBSTITUTION (removed Lehrer)
             _grid("2026-09-16", "13:25", "15:15", [12, 13], {
                 1: [{"current": _cur("TEACHER", "MUS", "Musterlehrerin"),
                      "removed": _cur("TEACHER", "ALT", "AltLehrer")},
                     {"current": _cur("TEACHER", "ZWE", "Zweitlehrer"),
                      "removed": None}],
                 2: [{"current": _cur("SUBJECT", "POS1", "Fiktives Fach"),
                      "removed": None}],
                 3: [{"current": _cur("ROOM", "B2.02", "Stammklasse"),
                      "removed": None}]}),
             _grid("2026-09-16", "08:00", "08:50", [14], {
                 1: [{"current": _cur("TEACHER", "MUS", "Musterlehrerin"),
                      "removed": None}],
                 2: [{"current": _cur("SUBJECT", "WMC_1", "Fiktives Fach 2"),
                      "removed": None}]}),
         ],
         "backEntries": []},
    ]


def test_parse_entries_class_plan_class_from_day_resource():
    entries = parse_timetable_entries(
        {"format": 1, "days": _class_plan_days(), "errors": []})
    assert len(entries) == 3
    by_subject = {e["subject"]: e for e in entries}
    assert set(by_subject) == {"POS1", "WMC_1"}
    # Klasse fehlt in position4 -> Fallback auf day.resource
    assert all(e["class"] == "5XZY" for e in entries)
    assert any(e["periodIds"] == [12, 13] for e in entries)
    assert by_subject["POS1"]["teachers"] == ["MUS", "ZWE"]
    assert by_subject["POS1"]["rooms"] == ["B2.02"]
    assert by_subject["WMC_1"]["start"] == "2026-09-16T08:00"


def test_parse_entries_student_plan_class_from_position4():
    # Schüler-Plan: Klasse steht in position4 (type CLASS)
    e = _grid("2026-09-16", "08:00", "08:50", [20], {
        1: [{"current": _cur("TEACHER", "MUS", "Musterlehrerin"),
             "removed": None}],
        2: [{"current": _cur("SUBJECT", "WMC_1", "Fiktives Fach 2"),
             "removed": None}],
        4: [{"current": _cur("CLASS", "5XZY", "Fiktive Klasse"),
             "removed": None}]})
    day = {"date": "2026-09-16", "resourceType": "STUDENT",
           "resource": {"id": 999, "shortName": "MusterEri",
                        "longName": "Muster"},
           "status": "REGULAR", "dayEntries": [], "gridEntries": [e],
           "backEntries": []}
    entries = parse_timetable_entries({"days": [day]})
    assert entries[0]["class"] == "5XZY"
    assert entries[0]["subject"] == "WMC_1"


def test_group_lessons_same_lesson_across_week():
    entries = parse_timetable_entries(
        {"days": _class_plan_days(), "errors": []})
    groups = group_timetable_lessons(entries)
    assert [g["subject"] for g in groups] == ["POS1", "WMC_1"]
    pos = groups[0]
    assert pos["dates"] == ["2026-09-14", "2026-09-16"]
    assert len(pos["entries"]) == 2  # 2 Termine/Woche
    assert pos["teachers"] == ["MUS", "ZWE"]
    assert pos["rooms"] == ["A1.01", "B2.02"]


def test_group_lessons_splits_groups_by_subject():
    e1 = _grid("2026-09-14", "08:00", "08:50", [1], {
        2: [{"current": _cur("SUBJECT", "POS1x", "F"), "removed": None}]})
    e2 = _grid("2026-09-14", "09:55", "10:45", [2], {
        2: [{"current": _cur("SUBJECT", "POS1y", "F"), "removed": None}]})
    day = {"date": "2026-09-14", "resourceType": "CLASS",
           "resource": {"id": 1, "shortName": "5XZY", "longName": "K"},
           "status": "REGULAR", "dayEntries": [], "gridEntries": [e1, e2],
           "backEntries": []}
    groups = group_timetable_lessons(
        parse_timetable_entries({"days": [day]}))
    assert [g["subject"] for g in groups] == ["POS1x", "POS1y"]


def test_group_lessons_splits_parallel_groups_same_subject():
    # Parallele Gruppen desselben Fachs (verschiedene Lehrer = verschiedene
    # Lessons), während Ko-Lehrer-Variation innerhalb EINER Gruppe
    # zusammenbleibt (Primary-Matching)
    e1 = _grid("2026-09-14", "08:00", "08:50", [1], {  # Gruppe MUS
        1: [{"current": _cur("TEACHER", "MUS"), "removed": None}],
        2: [{"current": _cur("SUBJECT", "POS1", "F"), "removed": None}]})
    e2 = _grid("2026-09-15", "09:55", "10:45", [2], {  # MUS+WES -> Gruppe MUS
        1: [{"current": _cur("TEACHER", "MUS", "A"), "removed": None},
            {"current": _cur("TEACHER", "WES", "B"), "removed": None}],
        2: [{"current": _cur("SUBJECT", "POS1", "F"), "removed": None}]})
    e3 = _grid("2026-09-16", "08:00", "08:50", [3], {  # Gruppe EDJ
        1: [{"current": _cur("TEACHER", "EDJ", "C"), "removed": None}],
        2: [{"current": _cur("SUBJECT", "POS1", "F"), "removed": None}]})
    day = lambda d, es: {"date": d, "resourceType": "CLASS",
                         "resource": {"id": 1, "shortName": "5XZY",
                                      "longName": "K"},
                         "status": "REGULAR", "dayEntries": [],
                         "gridEntries": es, "backEntries": []}
    groups = group_timetable_lessons(parse_timetable_entries(
        {"days": [day("2026-09-14", [e1]), day("2026-09-15", [e2]),
                  day("2026-09-16", [e3])]}))
    pos_groups = [g for g in groups if g["subject"] == "POS1"]
    assert len(pos_groups) == 2
    assert {g["primaryTeacher"] for g in pos_groups} == {"MUS", "EDJ"}
    assert all(g["parallel"] for g in pos_groups)
    mus = next(g for g in pos_groups if g["primaryTeacher"] == "MUS")
    assert mus["dates"] == ["2026-09-14", "2026-09-15"]
    assert set(mus["teachers"]) == {"MUS", "WES"}


def test_parse_dojo_viewmodel_unescapes_and_reads_one_object():
    import json
    vm = {"period": {"id": 123456, "date": 20260925},
          "absenceRows": [], "lessonId": 218000}
    escaped = (json.dumps(vm).replace("&", "&amp;")
                       .replace('"', "&quot;"))
    html = f'<form data-dojo-props="id: &quot;classregPageForm&quot;, ' \
           f'viewModel: {escaped}&quot;" action="/x"></form>'
    assert parse_dojo_viewmodel(html) == vm


def test_parse_dojo_viewmodel_missing_raises():
    import pytest
    with pytest.raises(RuntimeError, match="viewModel nicht gefunden"):
        parse_dojo_viewmodel("<html>nothing here</html>")

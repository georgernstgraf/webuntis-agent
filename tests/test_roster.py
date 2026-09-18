"""`students roster` helpers and wiring (no network, fictitious data only)."""

import argparse
from datetime import date

import pytest

from webuntis_agent import cli_students


def _matrix():
    return {
        "lessonPeriods": [
            {"id": 1, "date": 20260918, "studentCount": 2},
            {"id": 2, "date": 20260925, "studentCount": 1},
        ],
        "allKlassen": [{"id": 10, "name": "3AAIF"},
                       {"id": 20, "name": "3BAIF"}],
        "allStudents": [
            {"id": 1, "name": "Muster Eri",
             "klasse": 10, "attendedPeriods": [20260918, 20260925]},
            {"id": 2, "name": "Beispiel Max",
             "klasse": 20, "attendedPeriods": [20260918]},
            {"id": 3, "name": "Auslauf Lin",
             "klasse": 10, "attendedPeriods": []},
            {"id": 4, "name": "Fremd Tom",
             "klasse": -1, "attendedPeriods": [20260918]},
        ],
    }


def _overview():
    return {1: {"firstName": "Erika", "lastName": "Muster",
                "classInfo": {"id": 10, "name": "3AAIF"}},
            2: {"firstName": "Max", "lastName": "Beispiel",
                "classInfo": {"id": 20, "name": "3BAIF"}},
            3: {"firstName": "Lina", "lastName": "Auslauf",
                "classInfo": {"id": 10, "name": "3AAIF"}}}


def test_resolve_roster_date():
    assert cli_students._resolve_roster_date("2026-09-18") == "2026-09-18"
    assert cli_students._resolve_roster_date("now") == date.today().isoformat()
    assert cli_students._resolve_roster_date("NOW") == date.today().isoformat()
    with pytest.raises(ValueError):
        cli_students._resolve_roster_date("gestern")


def test_tsv_cell_sanitizes():
    assert cli_students._tsv_cell("a\tb\nc") == "a b c"
    assert cli_students._tsv_cell(None) == ""
    assert cli_students._tsv_cell(10) == "10"


def test_roster_rows_filters_sorts_and_joins():
    rows, unmatched = cli_students._roster_rows(
        _matrix(), _overview(), 20260918)
    # Auslauf (id 3) has no attendance on the day -> excluded
    assert rows == [("Beispiel Max", "3BAIF"),
                    ("Fremd Tom", "-1"),
                    ("Muster Erika", "3AAIF")]
    # Fremd (id 4) not in overview -> short matrix name fallback
    assert unmatched == ["Fremd Tom"]


def test_roster_rows_other_date():
    rows, _ = cli_students._roster_rows(_matrix(), _overview(), 20260925)
    assert rows == [("Muster Erika", "3AAIF")]


class _FakeClient:
    def __init__(self, matrix):
        self._matrix = matrix

    def resolve_schoolyear_id(self, override=None):
        return 24

    def get_student_lesson_period_matrix(self, lsid, school_year_id=None):
        assert lsid == 218839
        return {"result": self._matrix}

    def get_students_overview(self):
        return {"students": [
            {"id": 1, "firstName": "Erika", "lastName": "Muster",
             "classInfo": {"id": 10, "name": "3AAIF"}},
            {"id": 2, "firstName": "Max", "lastName": "Beispiel",
             "classInfo": {"id": 20, "name": "3BAIF"}},
        ]}


def _args(**kw):
    base = dict(lsid=218839, class_name=None, subject=None,
                date="2026-09-18", no_header=False, json=False,
                school_year_id=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_cmd_roster_tsv(monkeypatch, capsys):
    monkeypatch.setattr(cli_students, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    rc = cli_students.cmd_students_roster(_args())
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Name\tKlasse"
    assert out[1:] == ["Beispiel Max\t3BAIF",
                       "Fremd Tom\t-1",
                       "Muster Erika\t3AAIF"]


def test_cmd_roster_no_header_and_mismatch_warn(monkeypatch, capsys):
    m = _matrix()
    m["lessonPeriods"][0]["studentCount"] = 99  # force mismatch
    monkeypatch.setattr(cli_students, "_make_client",
                        lambda args: _FakeClient(m))
    rc = cli_students.cmd_students_roster(_args(no_header=True))
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines()[0].startswith("Beispiel Max\t")
    assert "studentCount=99 but 3 rows" in captured.err


def test_cmd_roster_fallback_uses_nearest_future(monkeypatch, capsys):
    import json
    monkeypatch.setattr(cli_students, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    # 2026-09-20 has no unit: future 2026-09-25 wins over nearer past
    rc = cli_students.cmd_students_roster(_args(json=True, date="2026-09-20"))
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["date"] == "2026-09-25"
    assert payload["requestedDate"] == "2026-09-20"
    assert [s["name"] for s in payload["students"]] == ["Muster Erika"]
    assert "using nearest unit 2026-09-25" in captured.err


def test_cmd_roster_fallback_last_held(monkeypatch, capsys):
    import json
    monkeypatch.setattr(cli_students, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    # beyond all units: last held unit wins
    rc = cli_students.cmd_students_roster(_args(json=True, date="2027-05-01"))
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["date"] == "2026-09-25"
    assert payload["requestedDate"] == "2027-05-01"


def test_cmd_roster_no_units_at_all(monkeypatch, capsys):
    m = _matrix()
    m["lessonPeriods"] = []
    monkeypatch.setattr(cli_students, "_make_client",
                        lambda args: _FakeClient(m))
    rc = cli_students.cmd_students_roster(_args(date="2026-09-20"))
    assert rc == 2
    assert "no lesson units at all" in capsys.readouterr().err


def test_cmd_roster_json(monkeypatch, capsys):
    import json
    monkeypatch.setattr(cli_students, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    rc = cli_students.cmd_students_roster(_args(json=True))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["lsId"] == 218839
    assert payload["date"] == "2026-09-18"
    assert [s["name"] for s in payload["students"]] == [
        "Beispiel Max", "Fremd Tom", "Muster Erika"]


def test_pick_closest_lesson():
    pick = cli_students._pick_closest_lesson
    matches = {10: ["2026-09-15", "2026-09-22"],
               20: ["2026-09-11", "2026-09-18"]}
    # exact date hit wins
    assert pick(matches, "2026-09-18") == 20
    assert pick(matches, "2026-09-22") == 10
    # otherwise smallest day distance (09-19: 20 is 1 away, 10 is 3 away)
    assert pick(matches, "2026-09-19") == 20
    # tie -> smallest lsId (09-16: both 2 and 1... 10:{15,22}->1, 20:{11,18}->2 => 10)
    assert pick(matches, "2026-09-16") == 10
    # single match returned as-is
    assert pick({7: ["2026-01-01"]}, "2026-09-18") == 7


def _open_entries():
    # enriched entries as _open_period_entries returns them (fake data)
    return [
        {"periodId": 1, "class": "4AHWIT", "classId": 1,
         "subject": "PMM1x", "date": "2026-09-15", "lsId": 215910},
        {"periodId": 2, "class": "4AHWIT", "classId": 1,
         "subject": "PMM1y", "date": "2026-09-11", "lsId": 215916},
        {"periodId": 3, "class": "4AHWIT", "classId": 1,
         "subject": "PMM1y", "date": "2026-09-18", "lsId": 215916},
    ]


class _FakeResolverClient:
    def resolve_schoolyear_id(self, override=None):
        return 24


def test_resolve_lesson_picks_closest_and_warns(monkeypatch, capsys):
    monkeypatch.setattr(cli_students, "_open_period_entries",
                        lambda c, sy, s, e: _open_entries())
    lesson = cli_students._resolve_lesson_from_class_subject(
        _FakeResolverClient(), 24, "4ahwit", "pmm",
        ref_date="2026-09-18")
    assert lesson["lsId"] == 215916
    assert lesson["class"] == "4AHWIT"
    assert lesson["subject"] == "PMM1y"
    assert lesson["candidates"] == [215910, 215916]
    err = capsys.readouterr().err.splitlines()
    assert err[0] == ("warning: ambiguous lesson for 4ahwit/pmm: "
                      "2 candidates, picked lsId=215916 closest to "
                      "2026-09-18")
    assert err[1:] == ["4AHWIT/PMM1x (2026-09-15)",
                       "4AHWIT/PMM1y (2026-09-18)"]


def test_nearest_date():
    near = cli_students._nearest_date
    assert near(["2026-09-15", "2026-09-22", "2026-09-29"],
                "2026-09-18") == "2026-09-15"
    assert near(["2026-09-11", "2026-09-18"], "2026-09-18") == "2026-09-18"
    # tie (09-16 between 09-15 and 09-17) -> earlier date
    assert near(["2026-09-15", "2026-09-17"], "2026-09-16") == "2026-09-15"


def test_resolve_lesson_single_no_warning(monkeypatch, capsys):
    monkeypatch.setattr(cli_students, "_open_period_entries",
                        lambda c, sy, s, e: _open_entries())
    lesson = cli_students._resolve_lesson_from_class_subject(
        _FakeResolverClient(), 24, "4AHWIT", "PMM1x")
    assert lesson["lsId"] == 215910
    assert capsys.readouterr().err == ""


def test_cmd_roster_class_subject_prints_exact_label(monkeypatch, capsys):
    monkeypatch.setattr(cli_students, "_open_period_entries",
                        lambda c, sy, s, e: _open_entries())
    monkeypatch.setattr(cli_students, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    # matrix only spans 20260918/20260925; resolve against that date
    args = _args(lsid=None, class_name="4ahwit", subject="PMM",
                 date="2026-09-18")
    # fake matrix lsIds differ from resolver lsIds — bypass resolver pick:
    # point the fake entries at the matrix lsId for this end-to-end check
    monkeypatch.setattr(cli_students, "_open_period_entries",
                        lambda c, sy, s, e:
                        [{**en, "lsId": 218839} for en in _open_entries()])
    rc = cli_students.cmd_students_roster(args)
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "4AHWIT/PMM1y"
    assert out[1] == "Name\tKlasse"


def test_resolve_lesson_no_match_raises(monkeypatch):
    monkeypatch.setattr(cli_students, "_open_period_entries",
                        lambda c, sy, s, e: _open_entries())
    with pytest.raises(RuntimeError, match="no lesson found"):
        cli_students._resolve_lesson_from_class_subject(
            _FakeResolverClient(), 24, "9ZZZ", "PMM")

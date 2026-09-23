"""student --id: Direktzugriff per Schüler-ID (Alternative zum Namen).

No network, fictitious data only (anonymized — no real ids/names).
"""

import argparse
import json

import pytest

from webuntis_agent import cli_student


def _ov_student(sid=4711, klasse="5XZY"):
    return {"id": sid, "firstName": "Erika", "lastName": "Muster",
            "shortName": "MusterEri",
            "classInfo": {"id": 111, "name": klasse}}


class _IdFakeClient:
    def __init__(self, students):
        self._students = students

    def resolve_schoolyear_id(self, override=None):
        return 24

    def schoolyear_label(self, sy):
        return "2026/2027"

    def get_students_overview(self):
        return {"students": self._students}


def _args(**kw):
    base = dict(name=None, student_id=None, klasse=None, wortteile=False,
                alle_jahre=False, absenzen=False, pause=1.0, json=False,
                school_year_id=None)
    base.update(kw)
    return argparse.Namespace(**base)


def _patch_detail(monkeypatch):
    monkeypatch.setattr(cli_student, "_kv_info",
                        lambda c, sy, klass: {"teachers": {1: "KV X"}})
    monkeypatch.setattr(cli_student, "_faecher_aus_plaenen",
                        lambda c, sy, sid, klass: {
                            "belegt": [{"subject": "POS1",
                                        "teachers": ["MUS"], "termine": 2}],
                            "klassenfremd": [], "nichtBelegt": [],
                            "woche": {"start": "2026-09-21",
                                      "end": "2026-09-26"},
                            "quelle": "stundenplan"})


def test_suchen_per_id_hit():
    fake = _IdFakeClient([_ov_student()])
    hits = cli_student._suchen_per_id(fake, 24, 4711)
    assert len(hits) == 1
    assert hits[0]["id"] == 4711
    assert hits[0]["class"] == "5XZY"
    assert hits[0]["firstName"] == "Erika"
    assert hits[0]["current"] is True
    assert hits[0]["searchNote"] == "id-match"


def test_suchen_per_id_miss():
    hits = cli_student._suchen_per_id(_IdFakeClient([_ov_student()]), 24,
                                      9999)
    assert hits == []


def test_cmd_student_id_text_detail(monkeypatch, capsys):
    monkeypatch.setattr(cli_student, "_make_client",
                        lambda args: _IdFakeClient([_ov_student()]))
    _patch_detail(monkeypatch)
    rc = cli_student.cmd_student(_args(student_id=4711))
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 Treffer für 4711" in out
    assert "Erika Muster" in out
    assert "Belegte Fächer" in out


def test_cmd_student_id_json(monkeypatch, capsys):
    monkeypatch.setattr(cli_student, "_make_client",
                        lambda args: _IdFakeClient([_ov_student()]))
    _patch_detail(monkeypatch)
    rc = cli_student.cmd_student(_args(student_id=4711, json=True))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == 4711
    assert [s["id"] for s in payload["students"]] == [4711]
    assert payload["details"][0]["id"] == 4711
    assert payload["details"][0]["absenzen"] is None


def test_cmd_student_id_miss(monkeypatch, capsys):
    monkeypatch.setattr(cli_student, "_make_client",
                        lambda args: _IdFakeClient([_ov_student()]))
    rc = cli_student.cmd_student(_args(student_id=9999))
    assert rc == 0
    assert "kein Schüler mit ID 9999" in capsys.readouterr().out


def test_cmd_student_id_without_class_no_detail(monkeypatch, capsys):
    s = _ov_student()
    s["classInfo"] = {}
    monkeypatch.setattr(cli_student, "_make_client",
                        lambda args: _IdFakeClient([s]))
    _patch_detail(monkeypatch)
    rc = cli_student.cmd_student(_args(student_id=4711, json=True))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "details" not in payload


def test_cmd_student_name_and_id_rejected(capsys):
    from webuntis_agent.errors import UsageError
    with pytest.raises(UsageError, match="genau eins"):
        cli_student.cmd_student(_args(name="Muster", student_id=4711))


def test_cmd_student_neither_rejected(capsys):
    from webuntis_agent.errors import UsageError
    with pytest.raises(UsageError, match="genau eins"):
        cli_student.cmd_student(_args())

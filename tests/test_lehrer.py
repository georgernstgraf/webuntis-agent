"""lehrer-Befehl: Treffer, Steckbrief, KV-Klassen, Jahr-Fallback."""

import argparse
import json

from webuntis_agent import cli_lehrer


def _hit(id_=9001, short="MK", display="Muster, Klaus"):
    return {"type": "TEACHER",
            "resource": {"id": id_, "shortName": short,
                         "longName": "", "displayName": display}}


class _FakeLehrerClient:
    def __init__(self, by_year=None, klassen=None):
        self._by_year = by_year or {}
        self._klassen = klassen if klassen is not None else [
            {"name": "5XZY", "teacher1": 9001, "teacher2": None,
             "teacher3": None}]

    def resolve_schoolyear_id(self, override=None):
        return 24 if override is None else override

    def schoolyear_label(self, sy):
        return {24: "2026/2027", 21: "2023/2024"}.get(sy, str(sy))

    def older_schoolyear_ids(self, current_id, max_years=3):
        return [21]

    def search_timetable(self, q, school_year_id=None):
        return self._by_year.get(school_year_id, [])

    def search_timetable_tokens(self, q, school_year_id=None):
        return self._by_year.get(school_year_id, [])

    def get_klassen(self, schoolyear_id=None):
        return {"result": self._klassen}


def _args(**kw):
    base = dict(name="MK", wortteile=False, alle_jahre=False, json=False,
                school_year_id=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_lehrer_text_shows_steckbrief_and_kv(monkeypatch, capsys):
    fake = _FakeLehrerClient({24: [_hit()]})
    monkeypatch.setattr(cli_lehrer, "_make_client", lambda args: fake)
    assert cli_lehrer.cmd_lehrer(_args()) == 0
    out = capsys.readouterr().out
    assert "1 Treffer" in out
    assert "MK" in out
    assert "KV in: 5XZY" in out


def test_lehrer_json_has_details(monkeypatch, capsys):
    fake = _FakeLehrerClient({24: [_hit()]})
    monkeypatch.setattr(cli_lehrer, "_make_client", lambda args: fake)
    assert cli_lehrer.cmd_lehrer(_args(json=True)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["lehrer"][0]["resource"]["id"] == 9001
    assert payload["details"][0]["kv"] == ["5XZY"]


def test_lehrer_no_hits(monkeypatch, capsys):
    fake = _FakeLehrerClient({24: []})
    monkeypatch.setattr(cli_lehrer, "_make_client", lambda args: fake)
    assert cli_lehrer.cmd_lehrer(_args()) == 0
    assert "(keine Treffer" in capsys.readouterr().out


def test_lehrer_older_year_marked_not_current(monkeypatch, capsys):
    fake = _FakeLehrerClient({24: [], 21: [_hit()]})
    monkeypatch.setattr(cli_lehrer, "_make_client", lambda args: fake)
    assert cli_lehrer.cmd_lehrer(_args(alle_jahre=True)) == 0
    out = capsys.readouterr().out
    assert "NICHT AKTUELL" in out

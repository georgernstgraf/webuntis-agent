"""Absence write-loop wiring (no network).

Regression test: `cmd_offen_pruefen` must pass `args.pause`
(not a bare `delay` name) into `_sleep_between`.
"""

import argparse
import json
import time

from webuntis_cli import cli_offen


class _FakeClient:
    def __init__(self):
        self.checked = []

    def check_absences(self, pid):
        self.checked.append(pid)
        return {"success": True, "periodId": pid}


def test_pruefen_datei_uses_args_pause(tmp_path, capsys, monkeypatch):
    items = [{"periodId": 11}, {"periodId": 22}]
    f = tmp_path / "batch.json"
    f.write_text(json.dumps(items), encoding="utf-8")
    fake = _FakeClient()
    monkeypatch.setattr(cli_offen, "_make_client", lambda args: fake)
    args = argparse.Namespace(datei=str(f), pause=1.0, start=None, end=None,
                              school_year_id=None, testlauf=False)
    # pause>0 with 2 items sleeps before the 2nd iteration — record it.
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    rc = cli_offen.cmd_offen_pruefen(args)
    assert rc == 0
    assert fake.checked == [11, 22]
    assert slept == [1.0]
    out = json.loads(capsys.readouterr().out)
    assert [e["periodId"] for e in out] == [11, 22]
    assert all(e["ok"] for e in out)


def test_pruefen_testlauf_writes_nothing(tmp_path, capsys, monkeypatch):
    """--testlauf (default) must not call check_absences."""
    items = [{"periodId": 11}, {"periodId": 22}]
    f = tmp_path / "batch.json"
    f.write_text(json.dumps(items), encoding="utf-8")
    fake = _FakeClient()
    monkeypatch.setattr(cli_offen, "_make_client", lambda args: fake)
    args = argparse.Namespace(datei=str(f), pause=1.0, start=None, end=None,
                              school_year_id=None, testlauf=True)
    rc = cli_offen.cmd_offen_pruefen(args)
    assert rc == 0
    assert fake.checked == []
    out = json.loads(capsys.readouterr().out)
    assert out == [{"periodId": 11}, {"periodId": 22}]

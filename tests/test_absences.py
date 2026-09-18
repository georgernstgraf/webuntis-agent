"""Absence write-loop wiring (no network).

Regression test: `cmd_batch_check_absences` must pass `args.delay`
(not a bare `delay` name) into `_sleep_between`.
"""

import argparse
import json
import time

from webuntis_agent import cli_absences


class _FakeClient:
    def __init__(self):
        self.checked = []

    def check_absences(self, pid):
        self.checked.append(pid)
        return {"success": True, "periodId": pid}


def test_batch_check_uses_args_delay(tmp_path, capsys, monkeypatch):
    items = [{"periodId": 11}, {"periodId": 22}]
    f = tmp_path / "batch.json"
    f.write_text(json.dumps(items), encoding="utf-8")
    fake = _FakeClient()
    monkeypatch.setattr(cli_absences, "_make_client", lambda args: fake)
    args = argparse.Namespace(file=str(f), delay=1.0)
    # delay>0 with 2 items sleeps before the 2nd iteration — record it.
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    rc = cli_absences.cmd_batch_check_absences(args)
    assert rc == 0
    assert fake.checked == [11, 22]
    assert slept == [1.0]
    out = json.loads(capsys.readouterr().out)
    assert [e["periodId"] for e in out] == [11, 22]
    assert all(e["ok"] for e in out)

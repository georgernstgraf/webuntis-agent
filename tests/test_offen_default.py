"""offen-Zeitraum-Default: Schuljahr-Start..heute aus open-periods/meta.

No network, fictitious data only (anonymized — no real ids/names).
"""

import argparse

import pytest

from webuntis_agent import cli_common


class _MetaFakeClient:
    def __init__(self, meta):
        self._meta = meta

    def get_open_periods_meta(self, school_year_id=None):
        assert school_year_id == 24
        return self._meta


def _meta(start="2026-09-07", end="2027-07-04"):
    return {"schoolYear": {"start": start, "end": end},
            "defaultFilter": "TOPIC_OR_ABSENCE_OPEN"}


def test_explizit_bleibt():
    c = _MetaFakeClient(_meta())
    args = argparse.Namespace(start="2026-09-01", end="2026-09-30")
    assert cli_common._resolve_von_bis(args, c, 24) == \
        ("2026-09-01", "2026-09-30")


def test_default_ist_schuljahr_start_bis_heute(capsys):
    from datetime import date
    c = _MetaFakeClient(_meta())
    args = argparse.Namespace(start=None, end=None)
    start, end = cli_common._resolve_von_bis(args, c, 24)
    assert start == "2026-09-07"
    assert end == date.today().isoformat()
    assert "Zeitraum-Default" in capsys.readouterr().err


def test_ende_wird_gedeckelt():
    c = _MetaFakeClient(_meta(end="2026-09-10"))
    args = argparse.Namespace(start=None, end=None)
    assert cli_common._resolve_von_bis(args, c, 24) == \
        ("2026-09-07", "2026-09-10")


def test_halb_angegeben_ist_usage_fehler(capsys):
    from webuntis_agent.errors import UsageError
    c = _MetaFakeClient(_meta())
    args = argparse.Namespace(start="2026-09-01", end=None)
    with pytest.raises(UsageError) as exc:
        cli_common._resolve_von_bis(args, c, 24)
    assert exc.value.exit_code == 2
    assert "--von und --bis gemeinsam" in str(exc.value)


def test_meta_ohne_range_wirft():
    c = _MetaFakeClient({"schoolYear": {}})
    args = argparse.Namespace(start=None, end=None)
    with pytest.raises(RuntimeError, match="schoolYear-Range"):
        cli_common._resolve_von_bis(args, c, 24)

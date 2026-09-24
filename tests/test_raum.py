"""raum suchen/groesse Stubs: Exit 7 + klare not-implemented-Meldung."""

import argparse

import pytest

from webuntis_cli import cli_raum
from webuntis_cli.errors import NotImplementedYet


def test_raum_suchen_stub_exit7():
    args = argparse.Namespace(datum="2026-09-25", stunde=7, min_plaetze=36,
                              max_plaetze=None, nur_freie=False, json=False,
                              school_year_id=None)
    with pytest.raises(NotImplementedYet) as exc:
        cli_raum.cmd_raum_suchen(args)
    assert exc.value.exit_code == 7
    assert "noch nicht implementiert" in str(exc.value)


def test_raum_groesse_stub_exit7():
    args = argparse.Namespace(raum="B3.07", json=False,
                              school_year_id=None)
    with pytest.raises(NotImplementedYet) as exc:
        cli_raum.cmd_raum_groesse(args)
    assert exc.value.exit_code == 7
    assert "noch nicht implementiert" in str(exc.value)
    assert "B3.07" in str(exc.value)

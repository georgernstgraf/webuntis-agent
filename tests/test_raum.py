"""raum suchen/groesse Stubs: Exit 3 + klare not-implemented-Meldung."""

import argparse

from webuntis_agent import cli_raum


def test_raum_suchen_stub_exit3(capsys):
    args = argparse.Namespace(datum="2026-09-25", stunde=7, min_plaetze=36,
                              max_plaetze=None, nur_freie=False, json=False,
                              school_year_id=None)
    assert cli_raum.cmd_raum_suchen(args) == 3
    err = capsys.readouterr().err
    assert "noch nicht implementiert" in err


def test_raum_groesse_stub_exit3(capsys):
    args = argparse.Namespace(raum="B3.07", json=False,
                              school_year_id=None)
    assert cli_raum.cmd_raum_groesse(args) == 3
    err = capsys.readouterr().err
    assert "noch nicht implementiert" in err
    assert "B3.07" in err

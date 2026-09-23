"""Usage errors print the full matching help, then the error line last."""

import sys

from webuntis_agent import cli


def _run(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["wu", *argv])
    return cli.main()


def test_no_command_prints_help_exit_1(monkeypatch, capsys):
    rc = _run(monkeypatch, [])
    assert rc == 1
    out = capsys.readouterr()
    assert "Domain-Objekte" in out.out
    assert "Beispiele:" in out.out


def test_unknown_command_help_then_error_exit_2(monkeypatch, capsys):
    rc = _run(monkeypatch, ["bogus"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "usage: wu" in err
    assert "Beispiele:" in err
    assert "Fehler:" in err
    # Consistency: help first, error line last.
    assert err.rfind("Fehler:") > err.rfind("Beispiele:")


def test_missing_subcommand_shows_that_subcommands_help(monkeypatch, capsys):
    rc = _run(monkeypatch, ["offen"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "wu offen" in err
    assert "Arbeitsvorrat" in err
    assert "Fehler:" in err


def test_hand_rolled_usage_error_shows_subcommand_help(monkeypatch, capsys):
    rc = _run(monkeypatch, ["student"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "wu student" in err
    assert "Fehler:" in err
    # The error line comes after the help.
    assert err.rfind("Fehler:") > err.find("usage:")

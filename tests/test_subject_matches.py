"""Fach-Match im Lesson-Resolver (fiktive Daten, kein Netz).

Regression: `pmmx` darf NICHT die Sammel-Lesson `PMM` treffen.
`_subject_matches` erlaubt nur die Richtung "Query ist Kürzung".
"""

from webuntis_cli import cli_lesson


def test_exact_match_case_insensitive():
    assert cli_lesson._subject_matches("PMMx", "pmmx")
    assert cli_lesson._subject_matches("pmmx", "PMMx")


def test_longer_query_does_not_match_shorter_subject():
    # der eigentliche Bug: pmmx ist präziser als PMM
    assert not cli_lesson._subject_matches("PMM", "pmmx")
    assert not cli_lesson._subject_matches("PMM", "PMMxy")


def test_abbreviation_matches_longer_subject():
    assert cli_lesson._subject_matches("PMMx", "pmm")
    assert cli_lesson._subject_matches("WMC_1", "wmc")
    assert cli_lesson._subject_matches("PMM1y", "pmm1")


def test_no_false_prefix():
    assert not cli_lesson._subject_matches("PMMx", "pmmz")
    assert not cli_lesson._subject_matches("PMMx", "pmmxy")


def test_missing_subject_never_matches():
    assert not cli_lesson._subject_matches(None, "pmm")
    assert not cli_lesson._subject_matches("", "pmm")


class _FakeClient:
    def resolve_schoolyear_id(self, override=None):
        return 24


def _entries():
    return [
        {"periodId": 1, "class": "4AHWIT", "classId": 1,
         "subject": "PMM", "date": "2026-09-23", "lsId": 215900},
        {"periodId": 2, "class": "4AHWIT", "classId": 1,
         "subject": "PMMx", "date": "2026-09-22", "lsId": 215910},
    ]


def test_resolver_pmmx_picks_only_pmmx(monkeypatch, capsys):
    monkeypatch.setattr(cli_lesson, "_open_period_entries",
                        lambda c, sy, s, e: _entries())
    lesson = cli_lesson._resolve_lesson_from_open_periods(
        _FakeClient(), 24, "4AHWIT", "pmmx")
    assert lesson["lsId"] == 215910
    assert lesson["subject"] == "PMMx"
    assert lesson["candidates"] == [215910]
    assert capsys.readouterr().err == ""


def test_resolver_pmm_stays_ambiguous(monkeypatch, capsys):
    # Abkürzung pmm trifft weiterhin beide -> Warnung, eigene/nahe wählen
    monkeypatch.setattr(cli_lesson, "_open_period_entries",
                        lambda c, sy, s, e: _entries())
    lesson = cli_lesson._resolve_lesson_from_open_periods(
        _FakeClient(), 24, "4AHWIT", "pmm", ref_date="2026-09-22")
    assert lesson["lsId"] == 215910
    assert sorted(lesson["candidates"]) == [215900, 215910]
    assert "mehrdeutige Lesson" in capsys.readouterr().err

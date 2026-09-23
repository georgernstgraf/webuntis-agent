"""klasse-Lookup: exakt per Name/ID, sonst Kandidaten ("meinst du ...?")."""

import pytest

from webuntis_agent.cli_common import _find_klasse
from webuntis_agent.errors import NotFoundError


class _Fake:
    def __init__(self, klassen, hits=None):
        self._klassen = klassen
        self._hits = hits or []

    def get_klassen(self, schoolyear_id=None):
        return {"result": self._klassen}

    def search_timetable_tokens(self, q, school_year_id=None):
        return self._hits


def test_exact_name_case_insensitive():
    c = _Fake([{"id": 7, "name": "3AHWII"}])
    assert _find_klasse(c, 24, "3ahwii")["id"] == 7


def test_by_id():
    c = _Fake([{"id": 7, "name": "3AHWII"}])
    assert _find_klasse(c, 24, 7)["id"] == 7


def test_string_miss_lists_candidates():
    hits = [{"type": "CLASS",
             "resource": {"id": 8, "shortName": "3BHWII", "longName": ""}}]
    c = _Fake([{"id": 7, "name": "3AHWII"}], hits)
    with pytest.raises(NotFoundError) as exc:
        _find_klasse(c, 24, "3CHWII")
    assert "nicht gefunden" in str(exc.value)
    assert "3BHWII" in str(exc.value)


def test_int_miss_has_no_candidates():
    hits = [{"type": "CLASS",
             "resource": {"id": 8, "shortName": "3BHWII", "longName": ""}}]
    c = _Fake([{"id": 7, "name": "3AHWII"}], hits)
    with pytest.raises(NotFoundError) as exc:
        _find_klasse(c, 24, 99)
    assert "3BHWII" not in str(exc.value)

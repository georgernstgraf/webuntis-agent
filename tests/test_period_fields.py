"""Null-safe raw open-period parsing.

Regression: WebUntis liefert für manche offenen Perioden `subject: null`
(z.B. reine Absenzenprüfung ohne Fach). `dict.get(key, default)` greift
nur bei fehlendem Key, nicht bei vorhandenem `null` — vorher stürzte
`PeriodFields.from_raw` mit AttributeError ab. Fiktive Daten, kein Netz.
"""

from webuntis_cli.cli_common import (
    PeriodFields,
    _open_period_entries,
    _period_summary,
)


def _raw_period(**overrides) -> dict:
    per = {
        "id": 1,
        "lsId": 42,
        "hr": 2,
        "classes": [{"el": {"id": 10, "name": "3AAIF"}}],
        "subject": {"el": {"id": 5, "nameShort": "SWP1x",
                           "name": "Sofwareentwicklung X"}},
        "dtRange": {"start": "2026-09-15T08:00", "end": "2026-09-15T08:50"},
        "teachers": [{"el": {"name": "Musterlehrer", "nameShort": "MUS"}}],
        "rooms": [{"el": {"name": "B3.07"}}],
    }
    entry = {"period": per, "topicId": 11, "topicNeeded": True,
             "absCheckNeeded": False}
    entry.update(overrides)
    return entry


def test_from_raw_parses_valid_period():
    f = PeriodFields.from_raw(_raw_period()["period"], 11)
    assert f.class_name == "3AAIF" and f.class_id == 10
    assert f.subject == "SWP1x" and f.subject_long == "Sofwareentwicklung X"
    assert f.date == "2026-09-15" and f.time == "08:00"


def test_from_raw_subject_none():
    f = PeriodFields.from_raw(_raw_period()["period"] | {"subject": None}, None)
    assert f.subject is None and f.subject_long is None
    assert f.class_name == "3AAIF"


def test_from_raw_classes_none_or_empty():
    for classes in (None, []):
        f = PeriodFields.from_raw(
            _raw_period()["period"] | {"classes": classes}, None)
        assert f.class_name is None and f.class_id is None
        assert f.subject == "SWP1x"


def test_from_raw_dtrange_none():
    f = PeriodFields.from_raw(
        _raw_period()["period"] | {"dtRange": None}, None)
    assert f.date == "" and f.time == ""


class _FakeClient:
    host = "https://example.test"

    def __init__(self, periods):
        self._periods = periods

    def get_open_periods(self, start, end, filter_="TOPIC_OR_ABSENCE_OPEN",
                         school_year_id=None):
        return {"periods": self._periods}


def test_open_period_entries_tolerates_nulls():
    subject_less = _raw_period()
    subject_less["period"]["subject"] = None
    subject_less["period"]["classes"] = None
    subject_less["period"]["teachers"] = None
    subject_less["period"]["rooms"] = None
    c = _FakeClient([subject_less, _raw_period()])

    entries = _open_period_entries(c, 24, "2026-09-15", "2026-09-15")

    assert len(entries) == 2
    assert entries[0]["subject"] is None
    assert entries[0]["class"] is None
    # ohne classId keine Lesson-Details-URL (statt "None" im String)
    assert entries[0]["lessonDetailsUrl"] is None
    assert entries[0]["teachers"] == [] and entries[0]["rooms"] == []
    assert entries[1]["subject"] == "SWP1x"
    assert entries[1]["lessonDetailsUrl"].endswith(
        "/lessonDetails/1/10/1/2026-09-15T08:00/2026-09-15T08:50/"
        "true?date=2026-09-15&entityId=10")


def test_open_period_entries_empty_and_null_list():
    assert _open_period_entries(_FakeClient([]), 24, "x", "y") == []

    class _NullClient:
        host = "https://example.test"

        def get_open_periods(self, *a, **kw):
            return {"periods": None}

    assert _open_period_entries(_NullClient(), 24, "x", "y") == []


def test_period_summary_subject_none():
    subject_less = _raw_period()
    subject_less["period"]["subject"] = None
    s = _period_summary(subject_less)
    assert s["subject"] is None
    assert s["periodId"] == 1 and s["lsId"] == 42

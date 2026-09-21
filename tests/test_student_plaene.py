"""student-Detail aus Stundenplänen: Join belegt/nicht belegt/klassenfremd.

No network, fictitious data only (anonymized — no real ids/names).
"""

from webuntis_agent import cli_student


def _cur(typ, short, long_=None):
    return {"type": typ, "status": "REGULAR", "shortName": short,
            "longName": long_ or short}


def _grid(day, start, end, ids, subject, klasse=None):
    positions = {
        1: [{"current": _cur("TEACHER", "MUS"), "removed": None}],
        2: [{"current": _cur("SUBJECT", subject, f"Fach {subject}"),
             "removed": None}],
        3: [{"current": _cur("ROOM", "A1.01"), "removed": None}],
    }
    if klasse:
        positions[4] = [{"current": _cur("CLASS", klasse, "Klasse"),
                         "removed": None}]
    return {"ids": ids, "duration": {"start": f"{day}T{start}",
                                     "end": f"{day}T{end}"},
            "type": "NORMAL_TEACHING_PERIOD", "status": "REGULAR",
            **{f"position{i}": a for i, a in positions.items()}}


def _day(day, res_type, res, entries):
    return {"date": day, "resourceType": res_type, "resource": res,
            "status": "REGULAR", "dayEntries": [], "gridEntries": entries,
            "backEntries": []}


class _JoinFakeClient:
    """Klassen-Plan (2 Lessons) + Schüler-Plan (POS1 eigen + ITA fremd)."""

    def get_klassen(self, schoolyear_id=None):
        return {"result": [{"id": 111, "name": "5XZY",
                            "longName": "Fiktive Klasse"}]}

    def get_timetable_entries(self, resource_type, resource_id, start, end,
                              timetable_type="STANDARD",
                              school_year_id=None):
        if resource_type == "CLASS":
            days = [
                _day("2026-09-14", "CLASS",
                     {"id": 111, "shortName": "5XZY", "longName": "K"},
                     [_grid("2026-09-14", "08:00", "08:50", [11], "POS1")]),
                _day("2026-09-16", "CLASS",
                     {"id": 111, "shortName": "5XZY", "longName": "K"},
                     [_grid("2026-09-16", "09:55", "10:45", [12], "WMC_1"),
                      _grid("2026-09-16", "11:45", "12:35", [13], "REL")]),
            ]
            return {"format": 1, "days": days, "errors": []}
        assert resource_type == "STUDENT" and resource_id == 21000
        days = [
            _day("2026-09-14", "STUDENT",
                 {"id": 21000, "shortName": "MusterEri", "longName": "M"},
                 [_grid("2026-09-14", "08:00", "08:50", [11], "POS1",
                        klasse="5XZY")]),
            _day("2026-09-16", "STUDENT",
                 {"id": 21000, "shortName": "MusterEri", "longName": "M"},
                 [_grid("2026-09-16", "08:00", "08:50", [14], "ITA3",
                        klasse="5XZW")]),
        ]
        return {"format": 1, "days": days, "errors": []}


def test_faecher_aus_plaenen(monkeypatch):
    # echter Aufruf mit FakeClient (Klassen-Lookup via _find_klasse)
    fa = cli_student._faecher_aus_plaenen(_JoinFakeClient(), 24, 21000,
                                          "5XZY")
    assert [e["subject"] for e in fa["belegt"]] == ["POS1"]
    assert [e["subject"] for e in fa["nichtBelegt"]] == ["REL", "WMC_1"]
    assert fa["klassenfremd"][0]["subject"] == "ITA3"


def test_belegt_ignores_attendance():
    # „belegt" = eingeschrieben: kein Matrix-/Anwesenheits-Check —
    # _faecher_aus_plaenen ruft NUR get_klassen + 2x entries (kein
    # get_student_lesson_period_matrix). Der Fake hat keine Matrix-
    # Methode: würde er aufgerufen, crasht der Test.
    fa = cli_student._faecher_aus_plaenen(_JoinFakeClient(), 24, 21000,
                                          "5XZY")
    assert fa["belegt"]

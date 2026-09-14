"""Pure grouping logic of the `lessons` command (no network)."""

from webuntis_agent.cli import _group_lesson_entries

E1 = {
    "periodId": 1, "topicId": 11, "class": "3BAIF", "classId": 4107,
    "subject": "SWP1x",
    "subjectLong": "Sofwareentwicklung und Projektmanagement X-Gruppe",
    "date": "2026-09-08", "time": "08:50", "lsId": 218231, "hr": 2,
    "teachers": ["Graf (GRG)"], "teacherShorts": ["GRG"],
    "rooms": ["B3.07 (org A1.06)"],
}
E2 = dict(E1, periodId=2, topicId=12, hr=3, date="2026-09-08",
          time="09:55", rooms=["B3.07 (org A1.06)"])
E3 = dict(E1, periodId=3, topicId=13, date="2026-09-15", time="08:00",
          rooms=["A1.06"])
E4 = {
    "periodId": 4, "topicId": 14, "class": "3BAIF", "classId": 4107,
    "subject": "WMC_1",
    "subjectLong": "Webprogrammierung und Mobile Computing",
    "date": "2026-09-08", "time": "17:10", "lsId": 218839, "hr": 11,
    "teachers": ["Graf (GRG)", "Lehrer B (LEA)"],
    "teacherShorts": ["GRG", "LEA"], "rooms": ["B4.14MF"],
}


def test_groups_by_lsid_and_sorts_by_first_date():
    groups = _group_lesson_entries([E1, E2, E3, E4])
    assert [g["lsId"] for g in groups] == [218231, 218839]
    swp = groups[0]
    assert swp["periods"] == 3
    assert swp["firstDate"] == "2026-09-08"
    assert swp["lastDate"] == "2026-09-15"
    assert swp["openTopicIds"] == [11, 12, 13]
    assert swp["teachers"] == ["Graf (GRG)"]
    assert swp["rooms"] == ["B3.07 (org A1.06)", "A1.06"]
    wmc = groups[1]
    assert wmc["teachers"] == ["Graf (GRG)", "Lehrer B (LEA)"]
    assert wmc["teacherShorts"] == ["GRG", "LEA"]


def test_groups_dedupe_rooms_and_keep_order():
    groups = _group_lesson_entries([E3, E2, E1])
    swp = groups[0]
    # rooms dedupe in first-seen order of the date-sorted entries (E1 first)
    assert swp["rooms"] == ["B3.07 (org A1.06)", "A1.06"]
    assert swp["firstDate"] == "2026-09-08"
    assert [e["periodId"] for e in swp["entries"]] == [1, 2, 3]


def test_entries_without_lsid_group_together():
    e = dict(E1, lsId=None, periodId=9)
    groups = _group_lesson_entries([e])
    assert len(groups) == 1
    assert groups[0]["lsId"] is None

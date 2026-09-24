"""Pure search-fallback helpers (no network)."""

from webuntis_cli.client import (
    is_shortname_hint,
    merge_search_results,
    student_matches_overview,
    tokenize_search_query,
)


def _hit(type_, id_, short="", long="", display=""):
    return {"type": type_,
            "resource": {"id": id_, "shortName": short,
                         "longName": long, "displayName": display}}


def test_tokenize_splits_and_dedupes():
    assert tokenize_search_query("Erika Muster") == ["Erika", "Muster"]
    assert tokenize_search_query("Muster, Erika") == ["Muster", "Erika"]
    assert tokenize_search_query("  Muster   muster ") == ["Muster"]
    assert tokenize_search_query("MK") == ["MK"]
    assert tokenize_search_query("") == []


def test_merge_dedupes_and_ranks_and_match_first():
    both = _hit("STUDENT", 1, short="MusterEri", display="Muster")
    single = _hit("TEACHER", 2, short="MK", display="Muster, Klaus (MK)")
    merged = merge_search_results(
        {"Erika": [both], "Muster": [both, single]},
        ["Erika", "Muster"],
    )
    assert [h["resource"]["id"] for h in merged] == [1, 2]
    assert all(h["searchNote"].startswith("token-fallback")
               for h in merged)


def test_shortname_hint_fires_for_lastname_first3():
    hit = _hit("STUDENT", 12345, short="MusterEri", display="Muster")
    assert is_shortname_hint(hit, ["Erika", "Muster"])
    merged = merge_search_results({"Muster": [hit]}, ["Erika", "Muster"])
    assert merged[0]["searchNote"] == "token-fallback+shortname-hint"


def test_shortname_hint_negative():
    assert not is_shortname_hint(
        _hit("TEACHER", 990, short="MK", display="Muster, Klaus (MK)"),
        ["Erika", "Muster"])
    assert not is_shortname_hint(
        _hit("STUDENT", 1, short="MusterEri", display="Muster"),
        ["Muster"])
    assert not is_shortname_hint(_hit("CLASS", 5, short="5BAIF"), ["5BAIF"])


def test_student_matches_overview_needs_all_tokens():
    s = {"firstName": "Erika", "lastName": "Muster",
         "shortName": "MusterEri"}
    assert student_matches_overview(s, ["Erika", "Muster"])
    assert student_matches_overview(s, ["muster"])
    assert student_matches_overview(s, ["Eri"])
    assert not student_matches_overview(s, ["Erika", "Marek"])
    assert not student_matches_overview(
        {"firstName": "Klaus", "lastName": "Muster", "shortName": "MK"},
        ["Erika", "Muster"])

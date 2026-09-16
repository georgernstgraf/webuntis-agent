"""Pure search-fallback helpers (no network)."""

from webuntis_agent.client import (
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
    assert tokenize_search_query("Clemens Unger") == ["Clemens", "Unger"]
    assert tokenize_search_query("Unger, Clemens") == ["Unger", "Clemens"]
    assert tokenize_search_query("  Unger   unger ") == ["Unger"]
    assert tokenize_search_query("UK") == ["UK"]
    assert tokenize_search_query("") == []


def test_merge_dedupes_and_ranks_and_match_first():
    both = _hit("STUDENT", 1, short="UngerCle", display="Unger")
    single = _hit("TEACHER", 2, short="UK", display="Unger, Klaus (UK)")
    merged = merge_search_results(
        {"Clemens": [both], "Unger": [both, single]},
        ["Clemens", "Unger"],
    )
    assert [h["resource"]["id"] for h in merged] == [1, 2]
    assert all(h["searchNote"].startswith("token-fallback")
               for h in merged)


def test_shortname_hint_fires_for_lastname_first3():
    hit = _hit("STUDENT", 12097, short="UngerCle", display="Unger")
    assert is_shortname_hint(hit, ["Clemens", "Unger"])
    merged = merge_search_results({"Unger": [hit]}, ["Clemens", "Unger"])
    assert merged[0]["searchNote"] == "token-fallback+shortname-hint"


def test_shortname_hint_negative():
    assert not is_shortname_hint(
        _hit("TEACHER", 190, short="UK", display="Unger, Klaus (UK)"),
        ["Clemens", "Unger"])
    assert not is_shortname_hint(
        _hit("STUDENT", 1, short="UngerCle", display="Unger"), ["Unger"])
    assert not is_shortname_hint(_hit("CLASS", 5, short="5BAIF"), ["5BAIF"])


def test_student_matches_overview_needs_all_tokens():
    s = {"firstName": "Clemens", "lastName": "Unger",
         "shortName": "UngerCle"}
    assert student_matches_overview(s, ["Clemens", "Unger"])
    assert student_matches_overview(s, ["unger"])
    assert student_matches_overview(s, ["Cle"])
    assert not student_matches_overview(s, ["Clemens", "Marek"])
    assert not student_matches_overview(
        {"firstName": "Klaus", "lastName": "Unger", "shortName": "UK"},
        ["Clemens", "Unger"])

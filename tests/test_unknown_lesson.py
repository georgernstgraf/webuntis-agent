"""Unknown lsId handling: server `code 0` maps to UnknownLessonError.

No network, fictitious ids only.
"""

import sys

from webuntis_agent import cli as cli_module
from webuntis_agent import cli_lesson
from webuntis_agent.client import Client, UnknownLessonError

_SERVER_SIG = ("JSON-RPC getStudentLessonPeriodMatrix failed (code 0): "
               "Internal server error.")


class _UnknownStub:
    def _jsonrpc_web(self, *args, **kwargs):
        raise RuntimeError(_SERVER_SIG)

    def resolve_schoolyear_id(self, override=None):
        return 24 if override is None else override

    def schoolyear_label(self, schoolyear_id):
        return "2026/2027" if schoolyear_id == 24 else str(schoolyear_id)


class _OtherErrorStub(_UnknownStub):
    def _jsonrpc_web(self, *args, **kwargs):
        raise RuntimeError("JSON-RPC getStudentLessonPeriodMatrix failed "
                           "(code -32000): something else broke")


def test_unknown_lsid_maps_to_typed_error():
    try:
        Client.get_student_lesson_period_matrix(_UnknownStub(), 22288)
    except UnknownLessonError as e:
        assert e.lsid == 22288
        assert e.schoolyear_id == 24
        assert "22288" in str(e)
        assert "2026/2027" in str(e)
        assert "Internal server error" in str(e)
    else:
        raise AssertionError("expected UnknownLessonError")


def test_explicit_school_year_override_used_in_message():
    class _Stub(_UnknownStub):
        def _jsonrpc_web(self, *args, **kwargs):
            raise RuntimeError(_SERVER_SIG)

    try:
        Client.get_student_lesson_period_matrix(_Stub(), 22288,
                                                school_year_id=21)
    except UnknownLessonError as e:
        assert e.schoolyear_id == 21
        assert "21" in str(e)
    else:
        raise AssertionError("expected UnknownLessonError")


def test_other_server_errors_pass_through_unwrapped():
    try:
        Client.get_student_lesson_period_matrix(_OtherErrorStub(), 22288)
    except UnknownLessonError:
        raise AssertionError("must NOT wrap non-signature errors")
    except RuntimeError as e:
        assert "something else broke" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_cli_main_reports_unknown_lsid_without_traceback(
        monkeypatch, capsys):
    class _CliStub:
        def resolve_schoolyear_id(self, override=None):
            return 24

        def get_student_lesson_period_matrix(self, lsid, school_year_id=None):
            raise UnknownLessonError(22288, 24, "2026/2027")

    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _CliStub())
    monkeypatch.setattr(sys, "argv",
                        ["wu", "lesson", "--lsid", "22288", "matrix"])
    rc = cli_module.main()
    assert rc == 3
    captured = capsys.readouterr()
    assert "22288" in captured.err
    assert "gibt es" in captured.err
    assert "Traceback" not in captured.err

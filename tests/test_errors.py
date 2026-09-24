"""Exit-code taxonomy: classify_exit + parser/usage helpers (no network)."""

import argparse

import httpx
import pytest

from webuntis_cli.cli_common import _HelpfulParser, usage_error
from webuntis_cli.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    NotImplementedYet,
    ServerError,
    UnexpectedError,
    UnknownLessonError,
    UsageError,
    WuError,
    classify_exit,
)


def _status_error(code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://example.invalid/x")
    resp = httpx.Response(code, request=req)
    return httpx.HTTPStatusError("boom", request=req, response=resp)


def test_typed_errors_carry_exit_codes():
    assert UsageError.exit_code == 2
    assert NotFoundError.exit_code == 3
    assert AuthError.exit_code == 4
    assert NetworkError.exit_code == 5
    assert ServerError.exit_code == 6
    assert NotImplementedYet.exit_code == 7
    assert ConfigError.exit_code == 8
    assert UnexpectedError.exit_code == 9


def test_wu_error_is_runtime_error_for_compat():
    assert isinstance(NotFoundError("x"), RuntimeError)


def test_unknown_lesson_is_not_found():
    e = UnknownLessonError(22288, 24, "2026/2027")
    assert isinstance(e, NotFoundError)
    assert e.exit_code == 3
    assert e.lsid == 22288


def test_classify_typed():
    assert classify_exit(UsageError("x")) == 2
    assert classify_exit(UnknownLessonError(1, 24, "2026/2027")) == 3
    assert classify_exit(AuthError("x")) == 4
    assert classify_exit(NetworkError("x")) == 5
    assert classify_exit(ServerError("x")) == 6
    assert classify_exit(NotImplementedYet("x")) == 7
    assert classify_exit(ConfigError("x")) == 8


def test_classify_walks_cause_chain():
    try:
        try:
            raise NetworkError("net")
        except NetworkError as e:
            raise RuntimeError("wrapped") from e
    except RuntimeError as e:
        assert classify_exit(e) == 5


def test_classify_httpx_status_and_transport():
    assert classify_exit(_status_error(401)) == 4
    assert classify_exit(_status_error(403)) == 4
    assert classify_exit(_status_error(404)) == 3
    assert classify_exit(_status_error(500)) == 6
    assert classify_exit(_status_error(503)) == 6
    assert classify_exit(httpx.ConnectError("no route")) == 5


def test_classify_unknown_is_unexpected():
    assert classify_exit(RuntimeError("plain bug")) == 9
    assert classify_exit(ValueError("nope")) == 9


def test_helpful_parser_raises_usage_with_itself():
    p = _HelpfulParser(prog="wu test")
    with pytest.raises(UsageError) as exc:
        p.error("kaputt")
    assert exc.value.parser is p
    assert "kaputt" in str(exc.value)


def test_usage_error_attaches_parser():
    p = _HelpfulParser(prog="wu test")
    args = argparse.Namespace(_parser=p)
    with pytest.raises(UsageError) as exc:
        usage_error(args, "meldung")
    assert exc.value.parser is p
    assert str(exc.value) == "meldung"


def test_usage_error_without_parser_falls_back():
    args = argparse.Namespace()
    with pytest.raises(UsageError) as exc:
        usage_error(args, "meldung")
    assert exc.value.parser is None
    assert isinstance(exc.value, WuError)

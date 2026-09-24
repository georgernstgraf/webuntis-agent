"""Typed error hierarchy + exit-code taxonomy for the CLI.

Every failure class maps to a distinct process exit code so scripts can
tell a user-input problem (2) from a missing resource (3), a dead
session (4), a network problem (5), a server problem (6), an
unimplemented command (7), a broken setup (8) or a bug (9).

`classify_exit()` walks the exception cause/context chain: command code
often re-wraps the underlying error into a message string, so the root
cause (a typed `WuError`, an `httpx` error, ...) decides the code.
"""

from __future__ import annotations

import httpx


class WuError(RuntimeError):
    """Base class for all expected CLI failures.

    Subclasses `RuntimeError` so existing soft-failure handlers
    (`except RuntimeError: print(...)`) keep working while the central
    handler still gets the precise `exit_code`.

    `exit_code` is the process status the CLI returns; `hint` is an
    optional actionable follow-up printed after the message.
    """

    exit_code: int = 9

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class UsageError(WuError):
    """Bad arguments: the user must change how the command is called.

    Carries the offending `parser` so `main()` can print the matching
    subcommand help before the error line.
    """

    exit_code = 2

    def __init__(self, message: str, *, parser=None,
                 hint: str | None = None) -> None:
        super().__init__(message, hint=hint)
        self.parser = parser


class NotFoundError(WuError):
    """A referenced resource does not exist (class, lesson, absence...)."""

    exit_code = 3


class AuthError(WuError):
    """Authentication/session failure (bad login, dead session, 401/403)."""

    exit_code = 4


class NetworkError(WuError):
    """Transport failure: connect/read/timeout/DNS/TLS."""

    exit_code = 5


class ServerError(WuError):
    """Server-side failure (HTTP 5xx, JSON-RPC error, broken payload)."""

    exit_code = 6


class NotImplementedYet(WuError):
    """Command is a documented stub (e.g. `raum`)."""

    exit_code = 7


class ConfigError(WuError):
    """Missing/invalid setup: absent Python module, missing .env."""

    exit_code = 8


class UnexpectedError(WuError):
    """Catch-all for a bug; `main()` prints a traceback."""

    exit_code = 9


class UnknownLessonError(NotFoundError):
    """A lesson id (lsId) unknown to the server in the active schoolyear.

    The server answers getStudentLessonPeriodMatrix for bogus ids with a
    generic `code 0: Internal server error` instead of "not found"
    (verified with ids 1, 22288, 999999999 in every schoolyear) — so we
    map that signature to a message the user can act on. Carries `lsid`
    and `schoolyear_id` for programmatic use.
    """

    def __init__(self, lsid: int, schoolyear_id: int,
                 schoolyear_label: str) -> None:
        self.lsid = lsid
        self.schoolyear_id = schoolyear_id
        super().__init__(
            f"lsId {lsid} gibt es im Schuljahr {schoolyear_label} "
            f"(id {schoolyear_id}) nicht "
            "(Server meldet: Internal server error — Hinweis: die Matrix "
            "ist rechte-beschränkt, fremde Lessons sind nicht lesbar). "
            "Gültige eigene lsIds z.B. via "
            "'wu offen liste --von <von> --bis <bis>' oder "
            "'wu student <Name> --absenzen --json'."
        )


def classify_exit(exc: BaseException) -> int:
    """Best-effort exit code for an exception and its cause chain.

    Prefers the first typed `WuError` (outermost first), then falls
    through to `httpx` errors. Returns the generic `UnexpectedError`
    code when nothing matches.
    """
    for e in _chain(exc):
        if isinstance(e, WuError):
            return e.exit_code
    for e in _chain(exc):
        if isinstance(e, httpx.HTTPStatusError):
            return _status_exit(e.response.status_code)
        if isinstance(e, httpx.TransportError):
            return NetworkError.exit_code
    return UnexpectedError.exit_code


def _status_exit(status_code: int) -> int:
    if status_code in (401, 403):
        return AuthError.exit_code
    if status_code == 404:
        return NotFoundError.exit_code
    if status_code >= 500:
        return ServerError.exit_code
    return ServerError.exit_code


def _chain(exc: BaseException):
    """Yield exc, then its cause/context chain (cycle-safe)."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        yield cur
        cur = cur.__cause__ or cur.__context__

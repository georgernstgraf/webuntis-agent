"""CLI absences commands (split from cli.py, see #15)."""

from __future__ import annotations

import argparse
import json
import sys

from typing import TYPE_CHECKING

from webuntis_agent.cli_common import (
    _fetch_open_periods,
    _make_client,
    _sleep_between,
)

if TYPE_CHECKING:
    from webuntis_agent.client import Client


def cmd_check_absences(args: argparse.Namespace) -> int:
    """Check absences for a single period."""
    c = _make_client(args)
    res = c.check_absences(args.period)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_batch_check_absences(args: argparse.Namespace) -> int:
    """Check absences for multiple periods from a JSON file.

    JSON format: [{"periodId": 123}, ...] (only periodId needed).
    """
    from pathlib import Path
    items = json.loads(Path(args.file).read_text(encoding="utf-8"))
    c = _make_client(args)
    results: list[dict] = []
    for i, it in enumerate(items):
        _sleep_between(i, args.delay)
        pid = it["periodId"]
        entry: dict = {"periodId": pid}
        try:
            res = c.check_absences(pid)
            entry["ok"] = res.get("success", False)
            entry["result"] = res
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)
        results.append(entry)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(results)} absences checked", file=sys.stderr)
    return 0 if ok == len(results) else 1


def cmd_check_all_absences(args: argparse.Namespace) -> int:
    """Fetch all open periods and check absences for every one that needs it."""
    c, sy, periods = _fetch_open_periods(args)
    need_check = [p for p in periods if p.get("absCheckNeeded")]
    print(f"open periods: {len(periods)}, needing absence check: {len(need_check)}",
          file=sys.stderr)
    results: list[dict] = []
    for i, p in enumerate(need_check):
        _sleep_between(i, args.delay)
        pid = p.get("period", {}).get("id")
        entry: dict = {"periodId": pid}
        try:
            res = c.check_absences(pid)
            entry["ok"] = res.get("success", False)
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)
        results.append(entry)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(need_check)} absences checked", file=sys.stderr)
    return 0 if ok == len(need_check) else 1



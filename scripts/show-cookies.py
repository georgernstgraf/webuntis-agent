#!/usr/bin/env python
"""Load a cookies.json file (from recordings/*_cookies.json) and print the
JSESSIONID + schoolname values for use in manual debugging.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cookies_json", type=Path)
    args = p.parse_args()
    cookies = json.loads(args.cookies_json.read_text(encoding="utf-8"))
    for c in cookies:
        if c.get("name") in ("JSESSIONID", "schoolname"):
            print(f"{c['name']}={c['value']}  (domain={c.get('domain')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

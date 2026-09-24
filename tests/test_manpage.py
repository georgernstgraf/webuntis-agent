"""Man page drift test: man/wu.1 must document the full CLI surface.

No network, no live data. The test derives the command/option inventory
straight from the argparse wiring in src/webuntis_cli/cli*.py
(every add_parser/add_argument literal) and asserts each appears in
man/wu.1. Adding a command or flag without documenting it fails the
suite. A groff render check (skipped when groff is missing) guards the
markup itself.
"""

import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAN = REPO / "man" / "wu.1"
SRC = REPO / "src" / "webuntis_cli"


def _cli_sources() -> str:
    return "\n".join(
        (SRC / name).read_text(encoding="utf-8")
        for name in ("cli.py", "cli_common.py")
    )


def _subcommands() -> set[str]:
    src = _cli_sources()
    names = set(re.findall(r'add_parser\(\s*"([a-z][a-z-]*)"', src))
    # top-level commands must all be present (guards renames, too)
    assert {"klasse", "lesson", "student", "lehrer", "offen",
            "raum", "intern"} <= names
    return names


def _long_options() -> set[str]:
    src = _cli_sources()
    flags = set(re.findall(r'add_argument\(\s*"(--[a-z0-9-]+)"', src))
    assert {"--json", "--testlauf", "--ausfuehren",
            "--schuljahr-id"} <= flags
    return flags


def _man_text() -> str:
    text = MAN.read_text(encoding="utf-8")
    # groff escapes every literal dash as \- : normalize back
    return text.replace("\\-", "-")


def test_manpage_exists():
    assert MAN.is_file(), "man/wu.1 fehlt"


def test_manpage_covers_all_subcommands():
    text = _man_text()
    missing = [c for c in sorted(_subcommands())
               if not re.search(rf"\b{re.escape(c)}\b", text)]
    assert not missing, f"nicht in man/wu.1 dokumentiert: {missing}"


def test_manpage_covers_all_options():
    text = _man_text()
    missing = [f for f in sorted(_long_options())
               if f not in text]
    assert not missing, f"nicht in man/wu.1 dokumentiert: {missing}"


def test_manpage_renders_with_groff():
    if shutil.which("groff") is None:
        import pytest
        pytest.skip("groff nicht installiert")
    proc = subprocess.run(
        ["groff", "-man", "-Tutf8", str(MAN)],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"groff rc={proc.returncode}: {proc.stderr}"
    assert not proc.stderr.strip(), f"groff-Warnungen: {proc.stderr}"
    assert "wu" in proc.stdout.lower()

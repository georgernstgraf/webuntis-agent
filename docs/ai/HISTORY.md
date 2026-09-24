# History

Chronological archive of superseded decisions and pruned entries.
Entries here are no longer active truth. Never delete from this file.

## 2026-09-24 (origin: project rename): webuntis-agent → webuntis-cli
- Project renamed `webuntis-agent` → `webuntis-cli` (repo, GitHub project,
  entry point, branding/docs).
- Python package renamed `webuntis_agent` → `webuntis_cli` (directory
  `src/webuntis_cli/`, all imports, `webuntis-cli = "webuntis_cli.cli:main"`).
- `wu` remains the CLI shortcut. Local clone moved to
  `~/repos/georgernstgraf/webuntis-cli`; private-repo symlink
  (`~/svn/georg/EDV/Toolset/wu`) and man symlink re-pointed.
- Old name: `webuntis-agent` / `webuntis_agent`.

## 2026-09-18 (SUPERSEDED 2026-09-21, origin: cli.py, reason: domain CLI replaces endpoint modules): cli.py split into cli_* endpoint modules
- Original: `cli.py` thin (argparse wiring + re-exports); logic in `cli_common`, `cli_lehrstoff`, `cli_students`, `cli_absences`, `cli_misc` with backward-compat re-exports (`from webuntis_cli.cli import …`).
- **Origin**: review #15 (Divergent Change in ~2000-line cli.py)
- **Reason**: Domain-CLI (2026-09-21, harter Schnitt) reorganizes into domain modules (`cli_klasse`, `cli_lesson`, `cli_student`, `cli_offen`, `cli_suche`, `cli_intern`) without re-export layer; dataclass wire-format rule (`PeriodFields`/`LessonGroup`/`SubmitItem` → dicts, key order kept) remains in force via cli_common.

## 2025-08-21 (SUPERSEDED 2025-08-21, origin: client.py, reason: prefix matching replaces exact match): Exact subject mapping
- Original `SUBJECT_REPO_MAP` used exact keys: "POS1", "SWP1y", "WMC1", etc.
- **Origin**: client.py
- **Reason**: WebUntis subject short names vary (SWP1x, SWP1y, WMC_1, INFIx) — prefix matching is more robust

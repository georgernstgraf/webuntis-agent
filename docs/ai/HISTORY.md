# History

Chronological archive of superseded decisions and pruned entries.
Entries here are no longer active truth. Never delete from this file.

## 2025-08-21 (SUPERSEDED 2025-08-21, origin: client.py, reason: prefix matching replaces exact match): Exact subject mapping
- Original `SUBJECT_REPO_MAP` used exact keys: "POS1", "SWP1y", "WMC1", etc.
- **Origin**: client.py
- **Reason**: WebUntis subject short names vary (SWP1x, SWP1y, WMC_1, INFIx) — prefix matching is more robust

"""Tests for gitlog.py against the known example cases."""

from __future__ import annotations

from datetime import date

from webuntis_agent.gitlog import (
    CommitInfo,
    _advance_year,
    _is_abteilungsklasse,
    get_commits_for_class,
    resolve_class_folders,
    resolve_class_folders_for_date,
)


def test_abteilungsklasse_detection():
    assert _is_abteilungsklasse("3aaif") is True
    assert _is_abteilungsklasse("4bkif") is True
    assert _is_abteilungsklasse("6acif") is True
    assert _is_abteilungsklasse("3ahwii") is False
    assert _is_abteilungsklasse("5hwit") is False


def test_advance_year():
    assert _advance_year("3aaif") == "4aaif"
    assert _advance_year("3bkif") == "4bkif"
    assert _advance_year("3ahwii") is None
    assert _advance_year("5hwit") is None


def test_resolve_class_folders_split():
    folders = resolve_class_folders("5ahwii")
    assert "5ahwii/" in folders
    assert "5ahwii_X/" in folders
    assert "5ahwii_Y/" in folders
    assert "5ahwii_Z/" in folders
    assert "5AHWII/" in folders
    assert "5AHWII_X/" in folders


def test_resolve_class_folders_for_date_abteilung():
    folders = resolve_class_folders_for_date("3aaif", date(2026, 3, 18))
    assert "3aaif/" in folders
    assert "4aaif/" in folders
    assert "4aaif_X/" in folders
    assert "3AAIF/" in folders
    assert "4AAIF/" in folders


def test_resolve_class_folders_for_date_tagesklasse():
    folders = resolve_class_folders_for_date("3ahwii", date(2026, 3, 18))
    assert "3ahwii/" in folders
    assert "4ahwii/" not in folders
    assert "3AHWII/" in folders


def test_5ahwii_18_march_2026():
    commits = get_commits_for_class("5ahwii", date(2026, 3, 18))
    assert len(commits) > 0, "expected commits for 5ahwii on 18.3.2026"
    repos = {c.repo for c in commits}
    assert "GRG-SWP" in repos
    prisma = [c for c in commits if "prisma" in c.message.lower()
              or "prisma" in " ".join(c.files).lower()]
    assert len(prisma) > 0, f"expected Prisma-related commits, got: {commits}"


def test_3bkif_2_oct_2025():
    commits = get_commits_for_class("3bkif", date(2025, 10, 2))
    assert len(commits) > 0, "expected commits for 3bkif on 2.10.2025"
    repos = {c.repo for c in commits}
    assert "GRG-WMC" in repos


def test_2ahwii_2_oct_2025_fallback():
    # 2ahwii has no commits within ±10 days of 2.10.2025, but the ±30
    # fallback finds commits from 6.10.2025 in GRG-SWP (referencing
    # 2025-09-29_bruch material).
    commits = get_commits_for_class("2ahwii", date(2025, 10, 2))
    assert len(commits) > 0, "expected fallback commits for 2ahwii"
    repos = {c.repo for c in commits}
    assert "GRG-SWP" in repos
    bruch = [c for c in commits
             if "bruch" in " ".join(c.files).lower()]
    assert len(bruch) > 0, "expected bruch-related commits"

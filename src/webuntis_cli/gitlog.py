"""Git-Log analysis for GRG-* teaching repositories.

Derives the lesson topic (Lehrstoff) for a given class and date from the
Git history of the GRG-* repositories under ~/repos/georgernstgraf/.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

REPOS_ROOT = Path(os.environ.get(
    "GRG_REPOS_ROOT",
    os.path.expanduser("~/repos/georgernstgraf"),
))

STABLE_SUFFIXES = ("hwii", "hwit", "hwiia", "hwita")


@dataclass
class CommitInfo:
    repo: str
    hash: str
    date: str
    message: str
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_year(class_name: str) -> int | None:
    try:
        return int(class_name[0])
    except (ValueError, IndexError):
        return None


def _extract_suffix(class_name: str) -> str:
    if not class_name:
        return ""
    if class_name[0].isdigit():
        return class_name[1:]
    return class_name


def _is_abteilungsklasse(class_name: str) -> bool:
    suffix = _extract_suffix(class_name)
    return not any(suffix.endswith(s) for s in STABLE_SUFFIXES)


def _advance_year(class_name: str) -> str | None:
    if not _is_abteilungsklasse(class_name):
        return None
    y = _extract_year(class_name)
    if y is None:
        return None
    return f"{y + 1}{_extract_suffix(class_name)}"


def resolve_class_folders(class_name: str) -> list[str]:
    """Return all folder variants to search for a class.

    Includes the bare name plus _X/_Y/_Z split-group suffixes.
    Generates lowercase base (most repos, e.g. '5ahwii_Y/') and
    uppercase base (GRG-POSTHEORIE, e.g. '6ACIF/'). Group suffix
    is always uppercase.
    """
    variants: list[str] = []
    for base in (class_name.lower(), class_name.upper()):
        variants.append(base + "/")
        for grp in ("_X", "_Y", "_Z"):
            variants.append(base + grp + "/")
    return variants


def resolve_class_folders_for_date(class_name: str, when: date) -> list[str]:
    folders = list(resolve_class_folders(class_name))
    advanced = _advance_year(class_name)
    if advanced:
        folders.extend(resolve_class_folders(advanced))
    return folders


def pull_all_repos(root: Path = REPOS_ROOT) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for repo_path in sorted(root.glob("GRG-*")):
        if not repo_path.is_dir():
            continue
        name = repo_path.name
        try:
            r = subprocess.run(
                ["git", "-C", str(repo_path), "pull", "--ff-only"],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                statuses[name] = "ok"
            else:
                statuses[name] = f"skip: {r.stderr.strip()[:80]}"
        except subprocess.TimeoutExpired:
            statuses[name] = "timeout"
        except Exception as e:
            statuses[name] = f"error: {e}"
    return statuses


def _git_log(repo_path: Path, folders: list[str], since: str, until: str) -> list[CommitInfo]:
    args = ["git", "-C", str(repo_path), "log", "--all",
            f"--since={since}", f"--until={until}",
            "--pretty=format:%H%x1f%ad%x1f%s", "--date=short",
            "--name-only", "--"]
    args.extend(folders)
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return []
    commits: list[CommitInfo] = []
    cur_hash = ""
    cur_date = ""
    cur_msg = ""
    cur_files: list[str] = []
    for line in r.stdout.splitlines():
        if "\x1f" in line:
            if cur_hash:
                commits.append(CommitInfo(
                    repo=repo_path.name, hash=cur_hash,
                    date=cur_date, message=cur_msg, files=cur_files,
                ))
            h, d, m = line.split("\x1f", 2)
            cur_hash, cur_date, cur_msg = h, d, m
            cur_files = []
        elif line.strip():
            cur_files.append(line.strip())
    if cur_hash:
        commits.append(CommitInfo(
            repo=repo_path.name, hash=cur_hash,
            date=cur_date, message=cur_msg, files=cur_files,
        ))
    return commits


def get_commits_for_class(
    class_name: str,
    when: date,
    window_days: int = 10,
    fallback_days: int = 30,
    root: Path = REPOS_ROOT,
    repo_filter: list[str] | None = None,
) -> list[CommitInfo]:
    folders = resolve_class_folders_for_date(class_name, when)

    def _collect_window(days: int) -> list[CommitInfo]:
        start = when - timedelta(days=days)
        end = when + timedelta(days=days)
        found: list[CommitInfo] = []
        for repo_path in sorted(root.glob("GRG-*")):
            if not repo_path.is_dir():
                continue
            if repo_filter is not None and repo_path.name not in repo_filter:
                continue
            found.extend(_git_log(
                repo_path, folders,
                start.strftime("%Y-%m-%d"),
                end.strftime("%Y-%m-%d"),
            ))
        return found

    all_commits = _collect_window(window_days)
    if not all_commits and fallback_days > window_days:
        all_commits = _collect_window(fallback_days)
    return all_commits


def get_commit_diff(repo_path: Path, commit_hash: str,
                    max_bytes: int = 4000) -> str:
    """Return the full diff (git show) of a commit, truncated to max_bytes."""
    r = subprocess.run(
        ["git", "-C", str(repo_path), "show", "--no-color",
         "--pretty=format:%H%n%an%n%ad%n%s%n", "--date=short",
         commit_hash],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return ""
    out = r.stdout
    if len(out) > max_bytes:
        out = out[:max_bytes] + "\n... (truncated)"
    return out


def get_commit_diff_by_name(repo_name: str, commit_hash: str,
                            max_bytes: int = 4000,
                            root: Path = REPOS_ROOT) -> str:
    """Convenience wrapper to fetch a diff by repo name + hash."""
    return get_commit_diff(root / repo_name, commit_hash, max_bytes)


def format_commits(commits: list[CommitInfo]) -> str:
    if not commits:
        return "(keine Commits gefunden)"
    out: list[str] = []
    for c in commits:
        out.append(f"[{c.repo}] {c.date} {c.hash[:8]} {c.message}")
        for f in c.files[:5]:
            out.append(f"    {f}")
    return "\n".join(out)

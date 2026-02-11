"""Helpers for resolving changed files from git and CLI inputs."""

import subprocess


def _git_diff_names(root, staged=False, commit_range=None):
    cmd = ["git", "diff", "--name-only"]
    if commit_range:
        cmd.append(commit_range)
    elif staged:
        cmd.append("--cached")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    return [
        p.replace("\\", "/")
        for p in result.stdout.strip().splitlines()
        if p.strip()
    ]


def resolve_changed_files(root, against_paths=None, staged=False, use_pr=False, base_ref="main"):
    """Return (paths, label) from one change source.

    Sources (mutually exclusive):
    - explicit against paths
    - staged git diff
    - PR range: <base_ref>..HEAD
    """
    against_paths = tuple(against_paths or ())

    if against_paths:
        return [p.replace("\\", "/") for p in against_paths], "explicit"

    if use_pr:
        commit_range = f"{base_ref}..HEAD"
        return _git_diff_names(root, commit_range=commit_range), commit_range

    if staged:
        return _git_diff_names(root, staged=True), "staged"

    return [], ""

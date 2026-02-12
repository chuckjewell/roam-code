"""Parity tests for diff mode labels and messaging."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


_REPO_SRC = str(Path(__file__).resolve().parents[1] / "src")


def _roam(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = _REPO_SRC + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result = subprocess.run(
        [sys.executable, "-m", "roam"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=env,
    )
    return result.stdout + result.stderr, result.returncode


def _git(path: Path, *args: str):
    return subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, timeout=30)


@pytest.fixture
def diff_project(tmp_path):
    root = tmp_path / "diff_project"
    root.mkdir()
    (root / "main.py").write_text(
        "from helper import add\n\n"
        "def main():\n"
        "    return add(1, 2)\n"
    )
    (root / "helper.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
    )

    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")

    out, rc = _roam("index", "--force", cwd=root)
    assert rc == 0, out
    return root


def _run_json(cwd, *args):
    out, rc = _roam("--json", *args, cwd=cwd)
    assert rc == 0, out
    return json.loads(out)


def test_diff_json_unstaged_label(diff_project):
    with open(diff_project / "helper.py", "a", encoding="utf-8") as f:
        f.write("\n# unstaged\n")

    data = _run_json(diff_project, "diff")
    assert data["label"] == "unstaged"


def test_diff_json_staged_label(diff_project):
    with open(diff_project / "helper.py", "a", encoding="utf-8") as f:
        f.write("\n# staged\n")
    _git(diff_project, "add", "helper.py")

    data = _run_json(diff_project, "diff", "--staged")
    assert data["label"] == "staged"


def test_diff_json_range_label(diff_project):
    with open(diff_project / "helper.py", "a", encoding="utf-8") as f:
        f.write("\n# commit-range\n")
    _git(diff_project, "add", "helper.py")
    _git(diff_project, "commit", "-m", "change")

    data = _run_json(diff_project, "diff", "HEAD~1..HEAD")
    assert data["label"] == "HEAD~1..HEAD"


def test_diff_no_changes_range(diff_project):
    out, rc = _roam("--json", "diff", "HEAD..HEAD", cwd=diff_project)
    assert rc == 0, out
    # Upstream outputs text (not JSON) when no changes found.
    assert "No changes" in out or "changed_files" in out

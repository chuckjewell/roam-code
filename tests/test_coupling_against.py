"""Tests for targeted coupling checks against a change set."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


_REPO_SRC = str(Path(__file__).resolve().parents[1] / "src")


def _run_roam(*args, cwd=None):
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
def coupling_project(tmp_path):
    root = tmp_path / "coupling_project"
    root.mkdir()

    for name in ("a.py", "b.py", "c.py", "d.py"):
        (root / name).write_text(f"def {name[0]}():\n    return 1\n")

    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")

    # Strong co-change between a.py and b.py.
    for i in range(2):
        with open(root / "a.py", "a", encoding="utf-8") as f:
            f.write(f"\n# ab {i}\n")
        with open(root / "b.py", "a", encoding="utf-8") as f:
            f.write(f"\n# ab {i}\n")
        _git(root, "add", "a.py", "b.py")
        _git(root, "commit", "-m", f"ab-{i}")

    # Weaker co-change between a.py and c.py.
    with open(root / "a.py", "a", encoding="utf-8") as f:
        f.write("\n# ac\n")
    with open(root / "c.py", "a", encoding="utf-8") as f:
        f.write("\n# ac\n")
    _git(root, "add", "a.py", "c.py")
    _git(root, "commit", "-m", "ac-0")

    out, rc = _run_roam("index", "--force", cwd=root)
    assert rc == 0, out
    return root


def test_coupling_against_reports_missing(coupling_project):
    out, rc = _run_roam(
        "--json",
        "coupling",
        "--against",
        "a.py",
        "--min-strength",
        "0.8",
        "--min-cochanges",
        "2",
        cwd=coupling_project,
    )
    assert rc == 0, out

    data = json.loads(out)
    assert data["command"] == "coupling"
    assert data["summary"]["mode"] == "against"
    assert any(item["path"] == "b.py" for item in data["missing"])


def test_coupling_against_marks_included(coupling_project):
    out, rc = _run_roam(
        "--json",
        "coupling",
        "--against",
        "a.py",
        "--against",
        "b.py",
        "--min-strength",
        "0.8",
        "--min-cochanges",
        "2",
        cwd=coupling_project,
    )
    assert rc == 0, out

    data = json.loads(out)
    assert not any(item["path"] == "b.py" for item in data["missing"])
    assert any(item["path"] == "b.py" for item in data["included"])


def test_coupling_staged_uses_indexed_changes(coupling_project):
    with open(coupling_project / "a.py", "a", encoding="utf-8") as f:
        f.write("\n# staged\n")
    _git(coupling_project, "add", "a.py")

    out, rc = _run_roam(
        "--json",
        "coupling",
        "--staged",
        "--min-strength",
        "0.8",
        "--min-cochanges",
        "2",
        cwd=coupling_project,
    )
    assert rc == 0, out

    data = json.loads(out)
    assert data["summary"]["mode"] == "against"
    assert any(item["path"] == "b.py" for item in data["missing"])


def test_coupling_pr_range(coupling_project):
    with open(coupling_project / "a.py", "a", encoding="utf-8") as f:
        f.write("\n# pr-commit\n")
    _git(coupling_project, "add", "a.py")
    _git(coupling_project, "commit", "-m", "pr change")

    out, rc = _run_roam(
        "--json",
        "coupling",
        "--pr",
        "--base",
        "HEAD~1",
        "--min-strength",
        "0.8",
        "--min-cochanges",
        "2",
        cwd=coupling_project,
    )
    assert rc == 0, out

    data = json.loads(out)
    assert any(item["path"] == "b.py" for item in data["missing"])

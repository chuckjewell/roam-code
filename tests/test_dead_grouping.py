"""Tests for grouped dead-code views."""

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
def dead_project(tmp_path):
    root = tmp_path / "dead_group_project"
    root.mkdir()
    (root / "app").mkdir()
    (root / "app" / "actions").mkdir(parents=True)
    (root / "app" / "components").mkdir(parents=True)

    (root / "app" / "actions" / "a.py").write_text(
        "def dead_action_one():\n"
        "    return 1\n\n"
        "def dead_action_two():\n"
        "    return 2\n"
    )
    (root / "app" / "components" / "b.py").write_text(
        "def dead_component_fn():\n"
        "    return 3\n"
    )

    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")

    out, rc = _roam("index", "--force", cwd=root)
    assert rc == 0, out
    return root


def test_dead_by_directory_json(dead_project):
    out, rc = _roam("--json", "dead", "--by-directory", cwd=dead_project)
    assert rc == 0, out
    data = json.loads(out)
    assert "groups" in data
    dirs = {g["key"] for g in data["groups"]}
    assert "app/actions" in dirs
    assert "app/components" in dirs


def test_dead_by_kind_json(dead_project):
    out, rc = _roam("--json", "dead", "--by-kind", cwd=dead_project)
    assert rc == 0, out
    data = json.loads(out)
    assert "groups" in data
    kinds = {g["key"] for g in data["groups"]}
    assert "function" in kinds


def test_dead_summary_only_text(dead_project):
    out, rc = _roam("dead", "--summary", cwd=dead_project)
    assert rc == 0, out
    assert "Dead exports:" in out or "dead" in out.lower()

"""Tests for structural snapshot/trend history."""

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
def trend_project(tmp_path):
    root = tmp_path / "trend_project"
    root.mkdir()

    (root / "a.py").write_text(
        "def one():\n"
        "    return 1\n"
    )

    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")

    out, rc = _roam("index", "--force", cwd=root)
    assert rc == 0, out
    return root


def test_snapshot_stores_data(trend_project):
    out, rc = _roam("--json", "snapshot", "--tag", "baseline", cwd=trend_project)
    assert rc == 0, out

    data = json.loads(out)
    assert data["command"] == "snapshot"
    assert data["summary"]["tag"] == "baseline"
    assert "health_score" in data["summary"] or "health_score" in data


def test_trend_outputs_rows(trend_project):
    _roam("snapshot", "--tag", "before", cwd=trend_project)

    (trend_project / "a.py").write_text(
        "def one():\n"
        "    return 1\n\n"
        "def two():\n"
        "    return 2\n"
    )
    _git(trend_project, "add", "a.py")
    _git(trend_project, "commit", "-m", "expand")
    _roam("index", "--force", cwd=trend_project)
    _roam("snapshot", "--tag", "after", cwd=trend_project)

    out, rc = _roam("trend", "--range", "5", cwd=trend_project)
    assert rc == 0, out
    assert "Health Trend" in out
    assert "after" in out


def test_trend_assertions_pass_and_fail(trend_project):
    _roam("snapshot", "--tag", "check", cwd=trend_project)

    out, rc = _roam("trend", "--assert", "files>=1", cwd=trend_project)
    assert rc == 0, out

    out, rc = _roam("trend", "--assert", "files<1", cwd=trend_project)
    assert rc != 0
    assert "ASSERTION" in out.upper() or "failed" in out.lower()

"""Tests for built-in compound report presets."""

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
        timeout=180,
        env=env,
    )
    return result.stdout + result.stderr, result.returncode


def _git(path: Path, *args: str):
    return subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, timeout=30)


@pytest.fixture
def report_project(tmp_path):
    root = tmp_path / "report_project"
    root.mkdir()
    (root / "app.py").write_text(
        "def main():\n"
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


def test_report_first_contact_json(report_project):
    out, rc = _roam("--json", "report", "first-contact", cwd=report_project)
    assert rc == 0, out
    data = json.loads(out)

    assert data["command"] == "report"
    assert data["preset"] == "first-contact"
    assert data["summary"]["sections"] >= 1
    assert isinstance(data["sections"], list)


def test_report_security_text(report_project):
    out, rc = _roam("report", "security", cwd=report_project)
    assert rc == 0, out
    assert "Report: security" in out
    assert "Sections:" in out

"""Tests for custom report definitions loaded from config."""

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
def custom_report_project(tmp_path):
    root = tmp_path / "custom_report_project"
    root.mkdir()
    (root / "mod.py").write_text("def f():\n    return 1\n")

    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")

    out, rc = _roam("index", "--force", cwd=root)
    assert rc == 0, out

    cfg = {
        "mini": {
            "description": "Minimal report",
            "sections": [
                {"title": "Overview", "command": ["map"]},
                {"title": "Health", "command": ["health"]}
            ]
        }
    }
    (root / "reports.json").write_text(json.dumps(cfg))
    return root


def test_custom_report_from_config(custom_report_project):
    out, rc = _roam(
        "--json",
        "report",
        "mini",
        "--config",
        "reports.json",
        cwd=custom_report_project,
    )
    assert rc == 0, out
    data = json.loads(out)

    assert data["preset"] == "mini"
    titles = {s["title"] for s in data["sections"]}
    assert "Overview" in titles
    assert "Health" in titles

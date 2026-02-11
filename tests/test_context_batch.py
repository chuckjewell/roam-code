"""Tests for multi-symbol context mode."""

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
def context_project(tmp_path):
    root = tmp_path / "context_batch_project"
    root.mkdir()

    (root / "core.py").write_text(
        "def b():\n"
        "    return 1\n\n"
        "def c():\n"
        "    return 2\n\n"
        "def a():\n"
        "    return b() + c()\n"
    )

    (root / "feature.py").write_text(
        "from core import a\n\n"
        "def entry():\n"
        "    return a()\n"
    )

    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")

    out, rc = _roam("index", "--force", cwd=root)
    assert rc == 0, out
    return root


def test_context_batch_text(context_project):
    out, rc = _roam("context", "a", "b", "c", cwd=context_project)
    assert rc == 0, out
    assert "Batch Context" in out
    assert "a" in out and "b" in out and "c" in out


def test_context_batch_json(context_project):
    out, rc = _roam("--json", "context", "a", "b", "c", cwd=context_project)
    assert rc == 0, out
    data = json.loads(out)
    assert "symbols" in data
    assert len(data["symbols"]) == 3
    assert "shared_callers" in data

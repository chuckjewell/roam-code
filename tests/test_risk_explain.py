"""Tests for risk explain-chain output."""

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
def risk_project(tmp_path):
    root = tmp_path / "risk_explain_project"
    root.mkdir()

    (root / "session.py").write_text(
        "def session_store():\n"
        "    return True\n\n"
        "def get_session():\n"
        "    return session_store()\n\n"
        "def require_user():\n"
        "    return get_session()\n"
    )

    (root / "route.py").write_text(
        "from session import require_user\n\n"
        "def loader():\n"
        "    return require_user()\n"
    )

    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")

    out, rc = _roam("index", "--force", cwd=root)
    assert rc == 0, out
    return root


def test_risk_explain_text_includes_chain(risk_project):
    out, rc = _roam("risk", "--domain", "session", "--explain", "-n", "10", cwd=risk_project)
    assert rc == 0, out
    assert "Chain:" in out


def test_risk_explain_json_includes_chain(risk_project):
    out, rc = _roam("--json", "risk", "--domain", "session", "--explain", "-n", "10", cwd=risk_project)
    assert rc == 0, out
    data = json.loads(out)
    assert "items" in data
    assert any(item.get("chain") for item in data["items"])

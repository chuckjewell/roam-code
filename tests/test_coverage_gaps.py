"""Tests for auth/logging/validation gate coverage via call-chain reachability."""

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
def app_project(tmp_path):
    root = tmp_path / "coverage_gaps_project"
    root.mkdir()
    (root / "app").mkdir()
    (root / "app" / "routes").mkdir(parents=True)

    (root / "app" / "session.py").write_text(
        "def require_user():\n"
        "    return True\n\n"
        "def helper_gate():\n"
        "    return require_user()\n"
    )

    (root / "app" / "routes" / "private.py").write_text(
        "from app.session import require_user\n\n"
        "def loader():\n"
        "    return require_user()\n"
    )

    (root / "app" / "routes" / "nested.py").write_text(
        "from app.session import helper_gate\n\n"
        "def action():\n"
        "    return helper_gate()\n"
    )

    (root / "app" / "routes" / "public.py").write_text(
        "def loader():\n"
        "    return 'ok'\n"
    )

    (root / "app" / "routes" / "webhook.py").write_text(
        "def action():\n"
        "    return 'ok'\n"
    )

    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")

    out, rc = _roam("index", "--force", cwd=root)
    assert rc == 0, out
    return root


def test_coverage_gaps_json_split(app_project):
    out, rc = _roam(
        "--json",
        "coverage-gaps",
        "--gate",
        "require_user",
        "--scope",
        "app/routes/**",
        cwd=app_project,
    )
    assert rc == 0, out

    data = json.loads(out)
    assert data["command"] == "coverage-gaps"
    assert data["summary"]["total_entry_points"] == 4
    assert data["summary"]["covered"] == 2
    assert data["summary"]["uncovered"] == 2

    uncovered_names = {item["name"] for item in data["uncovered"]}
    covered_names = {item["name"] for item in data["covered"]}

    assert "loader" in uncovered_names
    assert "action" in uncovered_names
    assert "loader" in covered_names
    assert "action" in covered_names


def test_coverage_gaps_scope_filter(app_project):
    out, rc = _roam(
        "--json",
        "coverage-gaps",
        "--gate",
        "require_user",
        "--scope",
        "app/routes/private.py",
        cwd=app_project,
    )
    assert rc == 0, out

    data = json.loads(out)
    assert data["summary"]["total_entry_points"] == 1
    assert data["summary"]["covered"] == 1
    assert data["summary"]["uncovered"] == 0


def test_coverage_gaps_text_has_sections(app_project):
    out, rc = _roam(
        "coverage-gaps",
        "--gate",
        "require_user",
        "--scope",
        "app/routes/**",
        cwd=app_project,
    )
    assert rc == 0, out
    assert "Uncovered Entry Points" in out
    assert "Covered Entry Points" in out

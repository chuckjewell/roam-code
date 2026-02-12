"""JSON contract tests for high-traffic commands."""

import json
import os
import subprocess
import sys
from datetime import datetime
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


def _git_init(path: Path):
    subprocess.run(["git", "init"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True)


@pytest.fixture
def indexed_project(tmp_path):
    """Create and index a tiny project, then leave one unstaged change."""
    root = tmp_path / "json_contract_project"
    root.mkdir()

    (root / "main.py").write_text(
        "from helper import add\n\n"
        "def main():\n"
        "    return add(1, 2)\n"
    )
    (root / "helper.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n\n"
        "def multiply(a, b):\n"
        "    return a * b\n"
    )

    _git_init(root)

    out, rc = _roam("index", cwd=root)
    assert rc == 0, out

    # Ensure diff/pr-risk have pending changes to analyze.
    (root / "helper.py").write_text(
        "def add(a, b):\n"
        "    return a + b + 1\n\n"
        "def multiply(a, b):\n"
        "    return a * b\n"
    )
    return root


def _run_json(cwd: Path, *args):
    out, rc = _roam("--json", *args, cwd=cwd)
    assert rc == 0, out
    return json.loads(out)


@pytest.mark.parametrize(
    "args, expected_command, payload_keys",
    [
        (("dead",), "dead", ("high_confidence", "low_confidence")),
        (("risk",), "risk", ("items",)),
        (("coupling",), "coupling", ("pairs",)),
        (("health",), "health", ("cycles", "god_components", "bottlenecks")),
        (("diff",), "diff", ("changed_files", "per_file", "blast_radius")),
        (("pr-risk",), "pr-risk", ("risk_score", "per_file", "dead_code")),
    ],
)
def test_json_envelope_and_payload(indexed_project, args, expected_command, payload_keys):
    data = _run_json(indexed_project, *args)

    assert data["command"] == expected_command
    assert isinstance(data["summary"], dict)
    datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    for key in payload_keys:
        assert key in data

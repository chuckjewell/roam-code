"""Tests for grep source-only and explicit exclude filters."""

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
def grep_project(tmp_path):
    root = tmp_path / "grep_source_only_project"
    root.mkdir()
    (root / "docs").mkdir()

    (root / "app.py").write_text(
        "def load_secret():\n"
        "    return 'secret_token'\n"
    )
    (root / "README.md").write_text("Never commit secret_token to source files.\n")
    (root / "docs" / "notes.txt").write_text("secret_token appears in docs only.\n")
    (root / "sample.example").write_text("SECRET=secret_token\n")

    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")

    out, rc = _roam("index", "--force", cwd=root)
    assert rc == 0, out
    return root


def test_grep_source_only_filters_docs_and_examples(grep_project):
    out, rc = _roam("--json", "grep", "secret_token", "--source-only", cwd=grep_project)
    assert rc == 0, out
    data = json.loads(out)

    paths = {m["path"] for m in data["matches"]}
    assert "app.py" in paths
    assert "README.md" not in paths
    assert "sample.example" not in paths
    assert "docs/notes.txt" not in paths


def test_grep_exclude_overrides_paths(grep_project):
    out, rc = _roam(
        "--json",
        "grep",
        "secret_token",
        "--exclude",
        "*.md,*.example,docs/**",
        cwd=grep_project,
    )
    assert rc == 0, out
    data = json.loads(out)

    paths = {m["path"] for m in data["matches"]}
    assert paths == {"app.py"}

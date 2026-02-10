"""A/B benchmark helpers for hypergraph coupling changes."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import date
from itertools import combinations
from pathlib import Path


DEFAULT_COMMANDS = {
    "map_json": ["--json", "map"],
    "health_json": ["--json", "health"],
    "coupling_json": ["--json", "coupling", "--mode", "pair", "-n", "20"],
    "pr_risk_json": ["--json", "pr-risk", "HEAD~5..HEAD"],
    "trace_json": ["--json", "trace", "Indexer", "compute_cochange"],
    "coupling_set_json": ["--json", "coupling", "--mode", "set", "-n", "20"],
}


def _run(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=merged_env,
        check=False,
    )


def _time_roam(
    args: list[str],
    repo_root: Path,
    python_exe: str | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    if python_exe is None:
        python_exe = sys.executable
    t0 = time.perf_counter()
    proc = _run([python_exe, "-m", "roam"] + args, cwd=repo_root, env=env)
    ms = (time.perf_counter() - t0) * 1000
    entry = {"ms": round(ms, 2), "rc": proc.returncode}
    try:
        parsed = json.loads(proc.stdout)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        entry["keys"] = sorted(parsed.keys())
    return entry


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def collect_index_counts(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        out = {
            "files": conn.execute("SELECT COUNT(*) c FROM files").fetchone()["c"],
            "symbols": conn.execute("SELECT COUNT(*) c FROM symbols").fetchone()["c"],
            "edges": conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"],
            "file_edges": conn.execute("SELECT COUNT(*) c FROM file_edges").fetchone()["c"],
            "cochange_pairs": conn.execute("SELECT COUNT(*) c FROM git_cochange").fetchone()["c"],
        }
        if _table_exists(conn, "git_hyperedges"):
            out["hyperedges"] = conn.execute(
                "SELECT COUNT(*) c FROM git_hyperedges"
            ).fetchone()["c"]
        if _table_exists(conn, "git_hyperedge_members"):
            out["hyperedge_members"] = conn.execute(
                "SELECT COUNT(*) c FROM git_hyperedge_members"
            ).fetchone()["c"]
        return out
    finally:
        conn.close()


def recurring_set_count_ge2(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "git_hyperedges") or not _table_exists(conn, "git_hyperedge_members"):
            return 0
        rows = conn.execute(
            "SELECT gh.id as hid, gm.file_id "
            "FROM git_hyperedges gh "
            "JOIN git_hyperedge_members gm ON gh.id = gm.hyperedge_id "
            "WHERE gh.file_count >= 3 "
            "ORDER BY gh.id, gm.ordinal, gm.file_id"
        ).fetchall()
    finally:
        conn.close()

    grouped: dict[int, list[int]] = {}
    for r in rows:
        grouped.setdefault(r["hid"], []).append(r["file_id"])

    patterns: dict[tuple[int, ...], int] = {}
    for members in grouped.values():
        key = tuple(sorted(members))
        patterns[key] = patterns.get(key, 0) + 1
    return sum(1 for n in patterns.values() if n >= 2)


def compute_timing_delta(baseline: dict, current: dict) -> dict:
    """Compute command timing deltas as percent changes."""
    out = {}
    for name in sorted(set(baseline) | set(current)):
        b = baseline.get(name, {}).get("ms")
        c = current.get(name, {}).get("ms")
        delta = None
        if b and c is not None:
            delta = round((c - b) / b * 100, 1)
        out[name] = {
            "baseline_ms": b,
            "current_ms": c,
            "delta_pct": delta,
        }
    return out


def run_synthetic_recurring_set_benchmark(
    python_exe: str | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """Build a tiny repo with recurring 3-file commits and measure detection."""
    if python_exe is None:
        python_exe = sys.executable

    root = Path(tempfile.mkdtemp(prefix="roam-hyperbench-"))
    (root / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (root / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    (root / "c.py").write_text("def c():\n    return 3\n", encoding="utf-8")
    (root / "d.py").write_text("def d():\n    return 4\n", encoding="utf-8")

    _run(["git", "init"], cwd=root, env=env)
    _run(["git", "config", "user.email", "t@t.com"], cwd=root, env=env)
    _run(["git", "config", "user.name", "T"], cwd=root, env=env)
    _run(["git", "add", "."], cwd=root, env=env)
    _run(["git", "commit", "-m", "init"], cwd=root, env=env)

    change_sets = [
        ("a.py", "b.py", "c.py"),
        ("a.py", "b.py", "c.py"),
        ("a.py", "b.py", "d.py"),
    ]
    for i, names in enumerate(change_sets):
        for name in names:
            with open(root / name, "a", encoding="utf-8") as f:
                f.write(f"\n# change {i}\n")
        _run(["git", "add", "."], cwd=root, env=env)
        _run(["git", "commit", "-m", f"c{i}"], cwd=root, env=env)

    _run([python_exe, "-m", "roam", "index", "--force"], cwd=root, env=env)
    pair = _run([python_exe, "-m", "roam", "--json", "coupling", "--mode", "pair", "-n", "10"], cwd=root, env=env)
    set_mode = _run([python_exe, "-m", "roam", "--json", "coupling", "--mode", "set", "-n", "10"], cwd=root, env=env)

    pair_j = json.loads(pair.stdout) if pair.stdout.strip() else {}
    set_j = json.loads(set_mode.stdout) if set_mode.stdout.strip() else {}

    abc = None
    for item in set_j.get("sets", []):
        if set(item.get("files", [])) == {"a.py", "b.py", "c.py"}:
            abc = item
            break

    return {
        "repo": str(root),
        "pair_top3": pair_j.get("pairs", [])[:3],
        "set_mode_count": len(set_j.get("sets", [])),
        "abc_set": abc,
    }


def run_comparison(
    repo_root: Path,
    baseline_path: Path | None = None,
    python_exe: str | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """Run the hypergraph benchmark report for a repository checkout."""
    if python_exe is None:
        python_exe = sys.executable

    repo_root = repo_root.resolve()
    _run([python_exe, "-m", "roam", "index", "--force"], cwd=repo_root, env=env)

    db_path = repo_root / ".roam" / "index.db"
    index_counts = collect_index_counts(db_path)
    recurring_sets = recurring_set_count_ge2(db_path)

    current_timings = {
        name: _time_roam(args, repo_root, python_exe=python_exe, env=env)
        for name, args in DEFAULT_COMMANDS.items()
    }

    baseline = None
    timing_delta = None
    if baseline_path and baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        timing_delta = compute_timing_delta(
            baseline.get("command_timings_ms", {}),
            current_timings,
        )

    synthetic = run_synthetic_recurring_set_benchmark(python_exe=python_exe, env=env)

    return {
        "date": str(date.today()),
        "repo_root": str(repo_root),
        "index": index_counts,
        "command_timings_ms": current_timings,
        "timing_delta": timing_delta,
        "new_signal": {
            "recurring_sets_ge2": recurring_sets,
            "has_hyperedges": index_counts.get("hyperedges", 0) > 0,
        },
        "synthetic_check": synthetic,
    }


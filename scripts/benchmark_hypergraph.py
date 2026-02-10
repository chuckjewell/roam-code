#!/usr/bin/env python3
"""Run hypergraph A/B benchmark and emit JSON report."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from roam.benchmarks.hypergraph import run_comparison


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark hypergraph coupling improvements")
    p.add_argument(
        "--repo",
        default=".",
        help="Repository root to benchmark (default: current directory)",
    )
    p.add_argument(
        "--baseline",
        default="docs/benchmarks/2026-02-10-baseline.json",
        help="Baseline JSON file for timing deltas",
    )
    p.add_argument(
        "--output",
        default="",
        help="Optional output path for JSON report",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo).resolve()
    baseline = Path(args.baseline)
    if not baseline.is_absolute():
        baseline = repo_root / baseline

    report = run_comparison(
        repo_root=repo_root,
        baseline_path=baseline if baseline.exists() else None,
        python_exe=sys.executable,
        env={"PYTHONPATH": os.environ.get("PYTHONPATH", "")},
    )

    payload = json.dumps(report, indent=2)
    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = repo_root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {out_path}")

    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


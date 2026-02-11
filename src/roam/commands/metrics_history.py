"""Helpers for collecting and persisting structural health history."""

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


def _history_path(root: Path) -> Path:
    return root / ".roam" / "history.json"


def load_history(root: Path) -> list[dict]:
    path = _history_path(root)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _git_meta(root: Path) -> tuple[str, str]:
    branch = ""
    commit = ""
    try:
        b = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if b.returncode == 0:
            branch = b.stdout.strip()
    except Exception:
        pass
    try:
        c = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if c.returncode == 0:
            commit = c.stdout.strip()
    except Exception:
        pass
    return branch, commit


def collect_metrics(conn) -> dict:
    """Collect a compact set of structural metrics from the current index."""
    files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    symbols = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    god_components = conn.execute(
        "SELECT COUNT(*) "
        "FROM graph_metrics gm "
        "JOIN symbols s ON gm.symbol_id = s.id "
        "WHERE s.kind IN ('function', 'class', 'method', 'interface', 'struct') "
        "AND (gm.in_degree + gm.out_degree) > 20"
    ).fetchone()[0]

    bottlenecks = conn.execute(
        "SELECT COUNT(*) "
        "FROM graph_metrics gm "
        "JOIN symbols s ON gm.symbol_id = s.id "
        "WHERE s.kind IN ('function', 'class', 'method', 'interface', 'struct') "
        "AND gm.betweenness > 0.5"
    ).fetchone()[0]

    dead_exports = conn.execute(
        "SELECT COUNT(*) FROM symbols s "
        "WHERE s.is_exported = 1 AND s.id NOT IN (SELECT target_id FROM edges)"
    ).fetchone()[0]

    weather_top_score = conn.execute(
        "SELECT COALESCE(MAX(total_churn * complexity), 0) FROM file_stats"
    ).fetchone()[0]

    cycles = 0
    layer_violations = 0
    try:
        from roam.graph.builder import build_symbol_graph
        from roam.graph.cycles import find_cycles
        from roam.graph.layers import detect_layers, find_violations

        g = build_symbol_graph(conn)
        cycles = len(find_cycles(g))
        layer_map = detect_layers(g)
        layer_violations = len(find_violations(g, layer_map)) if layer_map else 0
    except Exception:
        pass

    return {
        "files": files,
        "symbols": symbols,
        "edges": edges,
        "cycles": cycles,
        "god_components": god_components,
        "bottlenecks": bottlenecks,
        "dead_exports": dead_exports,
        "layer_violations": layer_violations,
        "weather_top_score": int(weather_top_score or 0),
    }


def append_history(root: Path, conn, tag: str = "", source: str = "snapshot") -> dict:
    """Append one history row to .roam/history.json and return the row."""
    history = load_history(root)
    branch, commit = _git_meta(root)
    entry = {
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "commit": commit,
        "branch": branch,
        "source": source,
        "tag": tag or "",
        "metrics": collect_metrics(conn),
    }
    history.append(entry)
    path = _history_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return entry

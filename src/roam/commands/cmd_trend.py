"""Show structural metric trends from .roam/history.json."""

import re

import click

from roam.commands.metrics_history import load_history
from roam.db.connection import find_project_root
from roam.output.formatter import format_table, json_envelope, to_json


_ASSERT_RE = re.compile(r"^([a-z_]+)\s*(<=|>=|==|<|>)\s*([0-9]+(?:\.[0-9]+)?)$")


def _evaluate_assertion(latest_metrics: dict, assertion: str) -> tuple[bool, str]:
    m = _ASSERT_RE.match(assertion.strip())
    if not m:
        return False, f"Invalid assertion format: {assertion}"
    metric, op, rhs_s = m.groups()
    if metric not in latest_metrics:
        return False, f"Unknown metric: {metric}"
    lhs = float(latest_metrics[metric])
    rhs = float(rhs_s)
    ok = False
    if op == "<=":
        ok = lhs <= rhs
    elif op == ">=":
        ok = lhs >= rhs
    elif op == "<":
        ok = lhs < rhs
    elif op == ">":
        ok = lhs > rhs
    elif op == "==":
        ok = lhs == rhs
    return ok, f"{metric} {lhs:g} {op} {rhs:g}"


@click.command("trend")
@click.option("--range", "range_n", default=5, show_default=True, type=int,
              help="Number of most recent history entries to show")
@click.option("--assert", "assertions", multiple=True,
              help="Constraint on latest metrics (e.g. cycles<=8)")
@click.pass_context
def trend(ctx, range_n, assertions):
    """Show structural trend rows from snapshot/index history."""
    json_mode = ctx.obj.get("json") if ctx.obj else False
    root = find_project_root()
    history = load_history(root)
    if not history:
        msg = "No history found. Run `roam snapshot` or `roam index` first."
        if json_mode:
            click.echo(to_json(json_envelope("trend", summary={"count": 0}, rows=[], message=msg)))
        else:
            click.echo(msg)
        return

    rows = history[-range_n:]
    latest = rows[-1]
    latest_metrics = latest.get("metrics", {})

    assertion_results = []
    failed = False
    for a in assertions:
        ok, detail = _evaluate_assertion(latest_metrics, a)
        assertion_results.append({"assertion": a, "ok": ok, "detail": detail})
        if not ok:
            failed = True

    if json_mode:
        click.echo(to_json(json_envelope(
            "trend",
            summary={"count": len(rows)},
            rows=rows,
            assertions=assertion_results,
        )))
        if failed:
            raise SystemExit(1)
        return

    click.echo(f"=== Health Trend (last {len(rows)} snapshots) ===")
    table_rows = []
    for e in rows:
        m = e.get("metrics", {})
        tag = e.get("tag") or e.get("source") or ""
        table_rows.append([
            e.get("timestamp", "")[:10],
            tag,
            str(m.get("cycles", 0)),
            str(m.get("god_components", 0)),
            str(m.get("bottlenecks", 0)),
            str(m.get("dead_exports", 0)),
            str(m.get("weather_top_score", 0)),
        ])
    click.echo(format_table(
        ["Date", "Tag", "Cycles", "Gods", "Bottlenecks", "Dead", "Weather-Top"],
        table_rows,
    ))

    if assertion_results:
        click.echo()
        for item in assertion_results:
            if item["ok"]:
                click.echo(f"Assertion passed: {item['detail']}")
            else:
                click.echo(f"Assertion failed: {item['detail']}")
        if failed:
            raise SystemExit(1)

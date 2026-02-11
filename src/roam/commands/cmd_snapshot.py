"""Persist a structural health snapshot to .roam/history.json."""

import click

from roam.commands.metrics_history import append_history
from roam.commands.resolve import ensure_index
from roam.db.connection import find_project_root, open_db
from roam.output.formatter import json_envelope, to_json


@click.command("snapshot")
@click.option("--tag", default="", help="Optional snapshot tag (e.g. v2.1-release)")
@click.pass_context
def snapshot(ctx, tag):
    """Save a structural snapshot to history."""
    json_mode = ctx.obj.get("json") if ctx.obj else False
    ensure_index()
    root = find_project_root()

    with open_db(readonly=True) as conn:
        entry = append_history(root, conn, tag=tag, source="snapshot")

    if json_mode:
        click.echo(to_json(json_envelope(
            "snapshot",
            summary={"tag": entry.get("tag", ""), "files": entry["metrics"]["files"]},
            entry=entry,
        )))
        return

    click.echo("Snapshot saved.")
    click.echo(f"  tag: {entry.get('tag') or '(none)'}")
    click.echo(f"  commit: {entry.get('commit') or '(none)'}  branch: {entry.get('branch') or '(none)'}")
    click.echo(f"  files: {entry['metrics']['files']}  symbols: {entry['metrics']['symbols']}  edges: {entry['metrics']['edges']}")

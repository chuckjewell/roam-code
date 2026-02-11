"""Run built-in or custom compound workflows as a single report."""

import json

import click

from roam.commands.report_presets import PRESETS
from roam.commands.report_runner import run_section
from roam.db.connection import find_project_root
from roam.output.formatter import json_envelope, to_json


def _load_custom_presets(config_path: str) -> dict:
    if not config_path:
        return {}
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for name, sections in data.items():
        if not isinstance(sections, list):
            continue
        cleaned = []
        for s in sections:
            if not isinstance(s, dict):
                continue
            title = s.get("title")
            command = s.get("command")
            if isinstance(title, str) and isinstance(command, list) and all(isinstance(x, str) for x in command):
                cleaned.append({"title": title, "command": command})
        if cleaned:
            out[str(name)] = cleaned
    return out


@click.command("report")
@click.argument("preset", required=False)
@click.option("--config", "config_path", default="", help="JSON file with custom report presets")
@click.option("--list", "list_presets", is_flag=True, help="List available report presets")
@click.option("--strict", is_flag=True, help="Fail if any section fails")
@click.pass_context
def report(ctx, preset, config_path, list_presets, strict):
    """Run a compound report preset and summarize section results."""
    json_mode = ctx.obj.get("json") if ctx.obj else False
    root = find_project_root()
    custom = _load_custom_presets(config_path)
    presets = dict(PRESETS)
    presets.update(custom)

    if list_presets:
        names = sorted(presets.keys())
        if json_mode:
            click.echo(to_json(json_envelope("report", summary={"count": len(names)}, presets=names)))
        else:
            click.echo("Available report presets:")
            for n in names:
                click.echo(f"  {n}")
        return

    if not preset:
        raise click.UsageError("Provide a preset name or use --list.")

    if preset not in presets:
        raise click.UsageError(f"Unknown preset: {preset}")

    sections = presets[preset]
    results = []
    failed = 0
    for sec in sections:
        run = run_section(sec["command"], str(root))
        status = "ok" if run["ok"] else "failed"
        if status == "failed":
            failed += 1
        results.append({
            "title": sec["title"],
            "command": sec["command"],
            "status": status,
            "error": (run["stderr"] or "").strip() if status == "failed" else "",
            "data": run["payload"] if run["ok"] else None,
        })

    summary = {
        "sections": len(results),
        "failed": failed,
        "ok": len(results) - failed,
    }

    if json_mode:
        click.echo(to_json(json_envelope(
            "report",
            summary=summary,
            preset=preset,
            sections=results,
        )))
        if strict and failed:
            raise SystemExit(1)
        return

    click.echo(f"Report: {preset}")
    click.echo(f"Sections: {len(results)}  OK: {summary['ok']}  Failed: {summary['failed']}")
    for r in results:
        click.echo(f"  [{r['status']}] {r['title']}  ({' '.join(r['command'])})")
        if r["status"] == "failed" and r["error"]:
            click.echo(f"    {r['error'].splitlines()[0]}")
    if strict and failed:
        raise SystemExit(1)

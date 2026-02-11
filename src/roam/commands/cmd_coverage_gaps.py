"""Find entry points that do not transitively pass through gate symbols."""

from collections import deque
import fnmatch

import click

from roam.commands.resolve import ensure_index
from roam.db.connection import open_db
from roam.output.formatter import abbrev_kind, loc, to_json, json_envelope


def _parse_csv(text: str) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def _in_scope(path: str, patterns: list[str]) -> bool:
    p = path.replace("\\", "/")
    return any(fnmatch.fnmatch(p, pat) for pat in patterns)


def _find_path_to_gate(entry_id: int, gate_ids: set[int], adj: dict[int, list[int]], max_depth: int) -> list[int] | None:
    """Return shortest path (symbol IDs) from entry to any gate, if found."""
    if entry_id in gate_ids:
        return [entry_id]

    q = deque([(entry_id, [entry_id])])
    visited = {entry_id}

    while q:
        cur, path = q.popleft()
        depth = len(path) - 1
        if depth >= max_depth:
            continue
        for nxt in adj.get(cur, []):
            if nxt in visited:
                continue
            visited.add(nxt)
            nxt_path = path + [nxt]
            if nxt in gate_ids:
                return nxt_path
            q.append((nxt, nxt_path))
    return None


@click.command("coverage-gaps")
@click.option("--gate", "gates_csv", required=True,
              help="Comma-separated gate symbol names (e.g. requireUser,requireAuth)")
@click.option("--scope", default="**", show_default=True,
              help="File scope glob(s), comma-separated (e.g. app/routes/**)")
@click.option("--max-depth", default=8, show_default=True, type=int,
              help="Maximum call-chain depth when searching for gate reachability")
@click.pass_context
def coverage_gaps(ctx, gates_csv, scope, max_depth):
    """Find uncovered entry points: exported functions with no gate in call chain."""
    json_mode = ctx.obj.get("json") if ctx.obj else False
    ensure_index()

    gate_names = _parse_csv(gates_csv)
    scope_patterns = _parse_csv(scope) or ["**"]

    with open_db(readonly=True) as conn:
        # Find gate symbols by name.
        ph = ",".join("?" for _ in gate_names) or "''"
        gate_rows = conn.execute(
            f"SELECT id, name FROM symbols WHERE name IN ({ph})",
            gate_names,
        ).fetchall()
        gate_ids = {r["id"] for r in gate_rows}
        gate_name_by_id = {r["id"]: r["name"] for r in gate_rows}

        # Exported top-level functions in scope are treated as entry points.
        entry_rows = conn.execute(
            "SELECT s.id, s.name, s.kind, s.line_start, f.path AS file_path "
            "FROM symbols s "
            "JOIN files f ON s.file_id = f.id "
            "WHERE s.is_exported = 1 "
            "AND s.parent_id IS NULL "
            "AND s.kind = 'function' "
            "ORDER BY f.path, s.line_start"
        ).fetchall()
        entries = [r for r in entry_rows if _in_scope(r["file_path"], scope_patterns)]

        # Build call/uses adjacency graph.
        adj: dict[int, list[int]] = {}
        for r in conn.execute(
            "SELECT source_id, target_id FROM edges WHERE kind IN ('call', 'uses')"
        ).fetchall():
            adj.setdefault(r["source_id"], []).append(r["target_id"])

        # Symbol names for chain rendering.
        symbol_names = {
            r["id"]: r["name"]
            for r in conn.execute("SELECT id, name FROM symbols").fetchall()
        }

        covered = []
        uncovered = []

        for e in entries:
            path_ids = _find_path_to_gate(e["id"], gate_ids, adj, max_depth) if gate_ids else None
            base = {
                "name": e["name"],
                "kind": e["kind"],
                "file": e["file_path"],
                "line": e["line_start"],
                "location": loc(e["file_path"], e["line_start"]),
            }
            if path_ids:
                gate_id = path_ids[-1]
                depth = len(path_ids) - 1
                chain = [symbol_names.get(sid, "?") for sid in path_ids]
                covered.append({
                    **base,
                    "gate": gate_name_by_id.get(gate_id, "?"),
                    "depth": depth,
                    "via": chain[-2] if len(chain) > 1 else chain[-1],
                    "chain": chain,
                })
            else:
                uncovered.append({
                    **base,
                    "reason": (
                        "no gate symbol found"
                        if not gate_ids
                        else "no auth gate in call chain"
                    ),
                })

        covered.sort(key=lambda x: (x["file"], x["line"], x["name"]))
        uncovered.sort(key=lambda x: (x["file"], x["line"], x["name"]))

        total = len(entries)
        summary = {
            "total_entry_points": total,
            "covered": len(covered),
            "uncovered": len(uncovered),
            "gate_symbols_found": len(gate_ids),
            "coverage_pct": round((len(covered) * 100 / total), 1) if total else 0.0,
        }

        if json_mode:
            click.echo(to_json(json_envelope(
                "coverage-gaps",
                summary=summary,
                gates=gate_names,
                scope=scope_patterns,
                max_depth=max_depth,
                covered=covered,
                uncovered=uncovered,
            )))
            return

        click.echo("=== Uncovered Entry Points ===")
        if uncovered:
            for item in uncovered:
                click.echo(
                    f"  {abbrev_kind(item['kind'])}  {item['name']:<20s}  "
                    f"{item['location']:<40s}  ({item['reason']})"
                )
        else:
            click.echo("  (none)")

        click.echo(f"\n=== Covered Entry Points ({len(covered)}/{total}) ===")
        if covered:
            for item in covered:
                click.echo(
                    f"  {abbrev_kind(item['kind'])}  {item['name']:<20s}  "
                    f"{item['location']:<40s}  via {item['gate']} (depth {item['depth']})"
                )
        else:
            click.echo("  (none)")

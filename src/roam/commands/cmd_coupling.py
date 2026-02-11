"""Show temporal coupling: files that change together."""

from collections import defaultdict
from itertools import combinations
import sqlite3

import click

from roam.db.connection import open_db
from roam.output.formatter import format_table, to_json, json_envelope
from roam.commands.resolve import ensure_index


def _load_structural_edges(conn):
    """Return undirected file-edge pairs used as structural evidence."""
    structural = set()
    rows = conn.execute(
        "SELECT source_file_id, target_file_id FROM file_edges WHERE symbol_count >= 2"
    ).fetchall()
    for r in rows:
        a, b = r["source_file_id"], r["target_file_id"]
        structural.add((min(a, b), max(a, b)))
    return structural


def _run_pair_mode(conn, count, json_mode):
    rows = conn.execute("""
        SELECT fa.path as path_a, fb.path as path_b,
               gc.cochange_count
        FROM git_cochange gc
        JOIN files fa ON gc.file_id_a = fa.id
        JOIN files fb ON gc.file_id_b = fb.id
        ORDER BY gc.cochange_count DESC
        LIMIT ?
    """, (count,)).fetchall()

    if not rows:
        if json_mode:
            click.echo(to_json(json_envelope(
                "coupling",
                summary={"mode": "pair", "count": 0},
                pairs=[],
            )))
        else:
            click.echo("No co-change data available. Run `roam index` on a git repository.")
        return

    # Check which pairs have structural connections (file_edges)
    structural_edges = _load_structural_edges(conn)

    # Build file path -> id lookup and commit counts for normalization
    path_to_id = {}
    file_commits = {}
    for f in conn.execute("SELECT id, path FROM files").fetchall():
        path_to_id[f["path"]] = f["id"]
    for fs in conn.execute("SELECT file_id, commit_count FROM file_stats").fetchall():
        file_commits[fs["file_id"]] = fs["commit_count"] or 1

    table_rows = []
    for r in rows:
        path_a = r["path_a"]
        path_b = r["path_b"]
        cochange = r["cochange_count"]
        fid_a = path_to_id.get(path_a)
        fid_b = path_to_id.get(path_b)

        has_edge = ""
        if fid_a and fid_b:
            key = (min(fid_a, fid_b), max(fid_a, fid_b))
            has_edge = "yes" if key in structural_edges else "HIDDEN"

        # Temporal coupling strength: normalized by avg commits
        strength = ""
        if fid_a and fid_b:
            avg_commits = (file_commits.get(fid_a, 1) + file_commits.get(fid_b, 1)) / 2
            if avg_commits > 0:
                ratio = cochange / avg_commits
                strength = f"{ratio:.0%}"

        table_rows.append([str(cochange), strength, has_edge, path_a, path_b])

    if json_mode:
        pairs = []
        for r in rows:
            pa, pb = r["path_a"], r["path_b"]
            fid_a, fid_b = path_to_id.get(pa), path_to_id.get(pb)
            has_struct = False
            if fid_a and fid_b:
                has_struct = (min(fid_a, fid_b), max(fid_a, fid_b)) in structural_edges
            strength_val = None
            if fid_a and fid_b:
                avg = (file_commits.get(fid_a, 1) + file_commits.get(fid_b, 1)) / 2
                if avg > 0:
                    strength_val = round(r["cochange_count"] / avg, 2)
            pairs.append({
                "file_a": pa, "file_b": pb,
                "cochange_count": r["cochange_count"],
                "strength": strength_val,
                "has_structural_edge": has_struct,
            })
        click.echo(to_json(json_envelope(
            "coupling",
            summary={"mode": "pair", "count": len(pairs)},
            pairs=pairs,
        )))
        return

    click.echo("=== Temporal coupling (co-change frequency) ===")
    click.echo(format_table(
        ["co-changes", "strength", "structural?", "file A", "file B"],
        table_rows,
    ))

    hidden_count = sum(1 for r in table_rows if r[2] == "HIDDEN")
    total_pairs = len(table_rows)
    if hidden_count:
        pct = hidden_count * 100 / total_pairs if total_pairs else 0
        click.echo(f"\n{hidden_count}/{total_pairs} pairs ({pct:.0f}%) have NO import edge but co-change frequently (hidden coupling).")


def _run_set_mode(conn, count, json_mode):
    """Show recurring 3+ file change-sets from commit hyperedges."""
    try:
        rows = conn.execute("""
            SELECT gh.id as hyperedge_id, gm.file_id, f.path
            FROM git_hyperedges gh
            JOIN git_hyperedge_members gm ON gh.id = gm.hyperedge_id
            JOIN files f ON gm.file_id = f.id
            WHERE gh.file_count >= 3
            ORDER BY gh.id, gm.ordinal, gm.file_id
        """).fetchall()
    except sqlite3.OperationalError:
        if json_mode:
            click.echo(to_json(json_envelope(
                "coupling",
                summary={"mode": "set", "count": 0},
                sets=[],
            )))
        else:
            click.echo("No change-set data available. Run `roam index` to refresh the index.")
        return

    if not rows:
        if json_mode:
            click.echo(to_json(json_envelope(
                "coupling",
                summary={"mode": "set", "count": 0},
                sets=[],
            )))
        else:
            click.echo("No change-set data available. Run `roam index` on a git repository.")
        return

    # Group members by hyperedge, then count recurring sets.
    edge_members = defaultdict(list)
    for r in rows:
        edge_members[r["hyperedge_id"]].append((r["file_id"], r["path"]))

    recurring = {}
    for members in edge_members.values():
        ordered = sorted(members, key=lambda m: m[0])
        file_ids = tuple(m[0] for m in ordered)
        paths = [m[1] for m in ordered]
        entry = recurring.get(file_ids)
        if entry is None:
            recurring[file_ids] = {
                "file_ids": file_ids,
                "files": paths,
                "occurrences": 1,
            }
        else:
            entry["occurrences"] += 1

    structural_edges = _load_structural_edges(conn)
    sets = []
    for item in recurring.values():
        fids = item["file_ids"]
        size = len(fids)
        max_pairs = size * (size - 1) // 2
        structural_pairs = sum(
            1 for a, b in combinations(fids, 2)
            if (min(a, b), max(a, b)) in structural_edges
        )
        structural_pct = round((structural_pairs * 100 / max_pairs), 1) if max_pairs else 0.0
        sets.append({
            "files": item["files"],
            "size": size,
            "occurrences": item["occurrences"],
            "structural_coupling_pct": structural_pct,
        })

    sets.sort(key=lambda x: (-x["occurrences"], -x["size"], -x["structural_coupling_pct"], x["files"]))
    sets = sets[:count]

    if json_mode:
        click.echo(to_json(json_envelope(
            "coupling",
            summary={"mode": "set", "count": len(sets)},
            sets=sets,
        )))
        return

    click.echo("=== Temporal coupling (recurring change sets) ===")
    table_rows = []
    for s in sets:
        files = ", ".join(s["files"][:4])
        if len(s["files"]) > 4:
            files += f" (+{len(s['files']) - 4})"
        table_rows.append([
            str(s["occurrences"]),
            str(s["size"]),
            f"{s['structural_coupling_pct']:.0f}%",
            files,
        ])
    click.echo(format_table(
        ["occurs", "size", "structural", "files"],
        table_rows,
    ))


@click.command()
@click.option('-n', 'count', default=20, help='Number of pairs to show')
@click.option(
    '--mode',
    type=click.Choice(['pair', 'set']),
    default='pair',
    show_default=True,
    help='pair=co-change pairs, set=recurring 3+ file change sets',
)
@click.pass_context
def coupling(ctx, count, mode):
    """Show temporal coupling: file pairs that change together."""
    json_mode = ctx.obj.get('json') if ctx.obj else False
    ensure_index()

    with open_db(readonly=True) as conn:
        if mode == "set":
            _run_set_mode(conn, count, json_mode)
            return
        _run_pair_mode(conn, count, json_mode)

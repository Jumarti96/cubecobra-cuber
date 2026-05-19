"""Typer CLI — all cuber commands."""

from __future__ import annotations

import json
import os
import sys
from typing import List, Optional

import typer

from . import scryfall, stats as stats_mod, exporter, tagger, cubecobra
from .cube import CUBES_DIR, find_cube_dir, load_cube_from_mainboard_csv, load_enriched, load_meta, save_enriched
from .cube_manager import fetch_and_disassemble, add_cards, remove_cards, dedup_mainboard, cube_status, assemble_export, backfill_tags_to_mainboard

app = typer.Typer(
    name="cuber",
    help="Local cube management toolkit for CubeCobra.",
    no_args_is_help=True,
)


@app.command()
def fetch(
    short_id: str = typer.Argument(..., help="CubeCobra short ID (e.g. obc)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print URL without fetching"),
):
    """Download a public cube from CubeCobra."""
    meta = fetch_and_disassemble(short_id, dry_run=dry_run)
    if not dry_run and meta:
        typer.echo(f"\nNext steps:")
        typer.echo(f"  cuber enrich {short_id}")
        typer.echo(f"  cuber stats {short_id}")


@app.command()
def enrich(
    id_or_slug: str = typer.Argument(..., help="CubeCobra short ID or cube slug"),
    refresh: bool = typer.Option(False, "--refresh", help="Bypass Scryfall cache"),
):
    """Enrich cube cards with Scryfall metadata. Auto-fetches if not found."""
    try:
        cube_folder = find_cube_dir(id_or_slug)
        has_cards = any(
            os.path.exists(os.path.join(cube_folder, fn))
            for fn in ("mainboard.csv", "raw.csv")
        )
    except FileNotFoundError:
        has_cards = False

    if not has_cards:
        typer.echo("Card list not found — running fetch first...")
        fetch_and_disassemble(id_or_slug)

    cube = scryfall.enrich_cube(id_or_slug, refresh=refresh)
    try:
        folder = find_cube_dir(id_or_slug)
        typer.echo(f"Full output: {os.path.join(folder, 'enriched.json')}")
    except FileNotFoundError:
        pass


@app.command()
def stats(
    id_or_slug: str = typer.Argument(..., help="CubeCobra short ID or cube slug"),
):
    """Print color/type/rarity/CMC distributions and write analysis.json."""
    try:
        cube = load_cube_from_mainboard_csv(id_or_slug)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    s = stats_mod.compute_stats(cube)
    tag_data = stats_mod.compute_tag_density(cube)

    typer.echo(stats_mod.format_stats_report(s))
    typer.echo(stats_mod.format_tag_density_report(tag_data))

    path = stats_mod.write_analysis_json({**s, "tag_density": tag_data}, id_or_slug)
    typer.echo(f"Full output: {path}")


@app.command()
def tag(
    id_or_slug: str = typer.Argument(..., help="CubeCobra short ID or cube slug"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace existing tags"),
):
    """AI-tag all cards using oracle text. Backfills tags to mainboard.csv."""
    try:
        cube = load_enriched(id_or_slug)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    cube = tagger.tag_cards(cube, overwrite=overwrite)
    save_enriched(cube, id_or_slug)

    updated = backfill_tags_to_mainboard(cube, id_or_slug)
    typer.echo(f"Tags backfilled to mainboard.csv ({updated} card(s) updated).")

    path = exporter.write_tagged_csv(cube, id_or_slug)
    typer.echo(f"Audit log: {path}")
    typer.echo("Run `cuber export <id>` to assemble import-ready.csv.")


@app.command("add-card")
def add_card(
    id_or_slug: str = typer.Argument(..., help="CubeCobra short ID or cube slug"),
    names: Optional[List[str]] = typer.Argument(None, help="Card name(s) to add"),
    from_file: Optional[str] = typer.Option(None, "--from-file", help="Text file with one card name per line"),
    stdin: bool = typer.Option(False, "--stdin", help="Read card names from stdin"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Add to maybeboard instead of mainboard"),
    count: Optional[int] = typer.Option(None, "--count", help="Add this many copies of each card (default: 1 per name supplied)"),
):
    """Add one or more cards to the cube mainboard (or maybeboard).

    Always adds exactly what you request — no deduplication against existing cards.
    Passing a name twice adds two copies. Use --count N to add N copies of each card.
    """
    all_names: List[str] = list(names or [])

    if from_file:
        try:
            with open(from_file, encoding="utf-8") as f:
                all_names.extend(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            typer.echo(f"File not found: {from_file}", err=True)
            raise typer.Exit(1)

    if stdin:
        all_names.extend(line.strip() for line in sys.stdin if line.strip())

    if not all_names:
        typer.echo(
            "No card names provided. Use positional args, --from-file, or --stdin.",
            err=True,
        )
        raise typer.Exit(1)

    # Expand --count: repeat each name N times
    if count is not None:
        if count < 1:
            typer.echo("--count must be at least 1.", err=True)
            raise typer.Exit(1)
        all_names = [name for name in all_names for _ in range(count)]

    board = "maybeboard" if maybeboard else "mainboard"
    try:
        result = add_cards(id_or_slug, all_names, board=board)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if result["added"]:
        typer.echo(f"Added to {board} ({len(result['added'])}):")
        for name in result["added"]:
            typer.echo(f"  + {name}")
        typer.echo(f"\nRun `cuber enrich {id_or_slug}` to hydrate new cards with Scryfall data.")


@app.command("remove-card")
def remove_card(
    id_or_slug: str = typer.Argument(..., help="CubeCobra short ID or cube slug"),
    names: Optional[List[str]] = typer.Argument(None, help="Card name(s) to remove"),
    from_file: Optional[str] = typer.Option(None, "--from-file", help="Text file with one card name per line"),
    stdin: bool = typer.Option(False, "--stdin", help="Read card names from stdin"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Remove from maybeboard instead of mainboard"),
    count: Optional[int] = typer.Option(None, "--count", help="Remove only this many copies (default: all copies)"),
):
    """Remove one or more cards from the cube mainboard (or maybeboard)."""
    all_names: List[str] = list(names or [])

    if from_file:
        try:
            with open(from_file, encoding="utf-8") as f:
                all_names.extend(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            typer.echo(f"File not found: {from_file}", err=True)
            raise typer.Exit(1)

    if stdin:
        all_names.extend(line.strip() for line in sys.stdin if line.strip())

    if not all_names:
        typer.echo(
            "No card names provided. Use positional args, --from-file, or --stdin.",
            err=True,
        )
        raise typer.Exit(1)

    board = "maybeboard" if maybeboard else "mainboard"
    try:
        result = remove_cards(id_or_slug, all_names, board=board, count=count)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if result["removed"]:
        label = f"(each: {count} cop{'y' if count == 1 else 'ies'})" if count else "(all copies)"
        typer.echo(f"Removed from {board} {label} ({len(result['removed'])}):")
        for name in result["removed"]:
            n = result["removed_counts"].get(name.strip().lower(), 1)
            typer.echo(f"  - {name}" + (f" x{n}" if n > 1 else ""))
    if result["not_found"]:
        typer.echo(f"Not found ({len(result['not_found'])}):")
        for name in result["not_found"]:
            typer.echo(f"  ? {name}")


@app.command()
def dedup(
    id_or_slug: str = typer.Argument(..., help="CubeCobra short ID or cube slug"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Dedup maybeboard instead of mainboard"),
):
    """Remove duplicate card rows, keeping the first copy of each card."""
    board = "maybeboard" if maybeboard else "mainboard"
    try:
        result = dedup_mainboard(id_or_slug, board=board)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    removed = result["duplicates_removed"]
    if removed == 0:
        typer.echo(f"No duplicates found in {board} ({result['total_before']} cards).")
        return

    typer.echo(f"Removed {removed} duplicate row(s) ({result['total_before']} -> {result['total_after']} cards):")
    for name, total_copies in sorted(result["affected_cards"].items()):
        typer.echo(f"  - {name} ({total_copies} copies -> 1 kept)")


@app.command()
def status(
    id_or_slug: str = typer.Argument(..., help="CubeCobra short ID or cube slug"),
):
    """Show cards added, removed, or retagged since last fetch."""
    try:
        diff = cube_status(id_or_slug)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    has_changes = bool(diff["added"] or diff["removed"] or diff["tag_changed"])

    if diff["added"]:
        typer.echo(f"\nAdded ({len(diff['added'])}):")
        for name in diff["added"]:
            typer.echo(f"  + {name}")

    if diff["removed"]:
        typer.echo(f"\nRemoved ({len(diff['removed'])}):")
        for name in diff["removed"]:
            typer.echo(f"  - {name}")

    if diff["tag_changed"]:
        typer.echo(f"\nTag changes ({len(diff['tag_changed'])}):")
        for entry in diff["tag_changed"]:
            typer.echo(f"  ~ {entry['name']}")
            typer.echo(f"      remote: {entry['remote_tags'] or '(none)'}")
            typer.echo(f"      local:  {entry['local_tags'] or '(none)'}")

    typer.echo(f"\nUnchanged: {diff['unchanged_count']} cards")

    if has_changes:
        typer.echo("\nRun `cuber export <id>` to assemble import-ready.csv.")
    else:
        typer.echo("\nNo local changes — nothing to export.")


@app.command()
def export(
    id_or_slug: str = typer.Argument(..., help="CubeCobra short ID or cube slug"),
):
    """Validate mainboard and assemble exports/import-ready.csv."""
    try:
        result = assemble_export(id_or_slug)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if result["errors"]:
        typer.echo("\nExport blocked — fix the following errors first:", err=True)
        for err in result["errors"]:
            typer.echo(f"  ERROR: {err}", err=True)
        raise typer.Exit(1)

    diff = result["diff"]
    has_changes = diff["added"] or diff["removed"] or diff["tag_changed"]

    if has_changes:
        if diff["added"]:
            names = diff["added"]
            typer.echo(f"\nAdded ({len(names)}):")
            for name in names[:10]:
                typer.echo(f"  + {name}")
            if len(names) > 10:
                typer.echo(f"  ... and {len(names) - 10} more")
        if diff["removed"]:
            names = diff["removed"]
            typer.echo(f"\nRemoved ({len(names)}):")
            for name in names[:10]:
                typer.echo(f"  - {name}")
            if len(names) > 10:
                typer.echo(f"  ... and {len(names) - 10} more")
        if diff["tag_changed"]:
            typer.echo(f"\n~ {len(diff['tag_changed'])} tag change(s)")
    else:
        typer.echo("\nNo changes vs remote.")

    if result["warnings"]:
        typer.echo("\nWarnings:")
        for w in result["warnings"]:
            typer.echo(f"  ! {w}")

    typer.echo(f"\n{result['card_count']} cards -> {result['path']}")
    typer.echo(f"Export log: {result['log_path']}")
    typer.echo("\nTo import into CubeCobra:")
    typer.echo("  1. Go to your cube on CubeCobra")
    typer.echo("  2. Click List -> Export -> Replace with CSV Import")
    typer.echo("  3. Upload the file above")


@app.command("fetch-set")
def fetch_set(
    set_code: str = typer.Argument(..., help="Scryfall set code (e.g. eoe, dmu)"),
    include_basics: bool = typer.Option(False, "--include-basics", help="Include basic lands"),
    include_tokens: bool = typer.Option(False, "--include-tokens", help="Include tokens"),
):
    """Fetch all cards from a retail MTG set and save as a local cube project."""
    meta = cubecobra.fetch_set(
        set_code,
        exclude_basics=not include_basics,
        exclude_tokens=not include_tokens,
    )
    if meta:
        sc = meta.get("short_id", set_code)
        typer.echo(f"\nNext steps:")
        typer.echo(f"  cuber enrich {sc}")
        typer.echo(f"  cuber tag {sc}")
        typer.echo(f"  cuber export {sc}")


@app.command("list")
def list_cubes():
    """List all locally cached cubes."""
    if not os.path.isdir(CUBES_DIR):
        typer.echo("No cubes directory found. Run `cuber fetch <id>` first.")
        return

    rows = []
    for entry in sorted(os.scandir(CUBES_DIR), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        meta_path = os.path.join(entry.path, "meta.json")
        if not os.path.exists(meta_path):
            continue
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        rows.append({
            "slug": entry.name,
            "short_id": meta.get("short_id", entry.name),
            "title": meta.get("title", "?"),
            "card_count": meta.get("card_count", "?"),
            "fetched_at": (meta.get("fetched_at") or "?")[:10],
        })

    if not rows:
        typer.echo("No cubes found.")
        return

    col_w = [26, 14, 28, 7, 12]
    header = (
        f"{'Slug':<{col_w[0]}}  "
        f"{'Short ID':<{col_w[1]}}  "
        f"{'Title':<{col_w[2]}}  "
        f"{'Cards':<{col_w[3]}}  "
        f"{'Fetched':<{col_w[4]}}"
    )
    typer.echo(header)
    typer.echo("-" * (sum(col_w) + 8))
    for r in rows:
        typer.echo(
            f"{str(r['slug'])[:col_w[0]]:<{col_w[0]}}  "
            f"{str(r['short_id'])[:col_w[1]]:<{col_w[1]}}  "
            f"{str(r['title'])[:col_w[2]]:<{col_w[2]}}  "
            f"{str(r['card_count']):<{col_w[3]}}  "
            f"{str(r['fetched_at']):<{col_w[4]}}"
        )


@app.command()
def diff(
    id1: str = typer.Argument(..., help="First cube short ID or slug"),
    id2: str = typer.Argument(..., help="Second cube short ID or slug"),
):
    """Compare two cubes — shared cards, unique to each, and stat deltas."""
    try:
        cube1 = load_enriched(id1)
        cube2 = load_enriched(id2)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    names1 = {c.name for c in cube1.cards}
    names2 = {c.name for c in cube2.cards}
    shared = sorted(names1 & names2)
    only1 = sorted(names1 - names2)
    only2 = sorted(names2 - names1)

    typer.echo(f"\nDiff: {id1} vs {id2}")
    typer.echo(f"  Shared cards:      {len(shared)}")
    typer.echo(f"  Only in {id1:<12}: {len(only1)}")
    typer.echo(f"  Only in {id2:<12}: {len(only2)}")

    if only1:
        typer.echo(f"\nOnly in {id1} ({len(only1)}):")
        for name in only1[:20]:
            typer.echo(f"  - {name}")
        if len(only1) > 20:
            typer.echo(f"  ... and {len(only1) - 20} more")

    if only2:
        typer.echo(f"\nOnly in {id2} ({len(only2)}):")
        for name in only2[:20]:
            typer.echo(f"  - {name}")
        if len(only2) > 20:
            typer.echo(f"  ... and {len(only2) - 20} more")

    s1 = stats_mod.compute_stats(cube1)
    s2 = stats_mod.compute_stats(cube2)

    result = {
        "cube1": id1,
        "cube2": id2,
        "shared": shared,
        "only_in_1": only1,
        "only_in_2": only2,
        "stats_1": s1,
        "stats_2": s2,
    }

    out_path = os.path.join(os.environ.get("TEMP", "/tmp"), "cube-diff.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    typer.echo(f"\nFull output: {out_path}")

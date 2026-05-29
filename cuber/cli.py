"""Typer CLI — all cuber commands."""

from __future__ import annotations

import csv
import json
import os
import re
import shlex
import sys
from typing import Dict, List, Optional, Tuple

import typer

from . import scryfall, stats as stats_mod, exporter, tagger, cubecobra
from .cube import CUBES_DIR, find_cube_dir, load_cube_from_mainboard_csv, load_enriched, load_meta, save_enriched
from .cube_manager import (
    CONFIG_PATH,
    fetch_and_disassemble,
    add_cards,
    remove_cards,
    dedup_mainboard,
    cube_status,
    assemble_export,
    backfill_tags_to_mainboard,
    swap_card,
    add_cards_from_package,
    resolve_cube_id,
    scale_cards,
)
from .cube_search import load_merged_pool, search_pool, format_search_results, fuzzy_name_search, format_search_card_results

app = typer.Typer(
    name="cuber",
    help="Local cube management toolkit for CubeCobra.",
    no_args_is_help=True,
)

packages_app = typer.Typer(name="packages", help="Browse and import CubeCobra packages.", no_args_is_help=True)
app.add_typer(packages_app, name="packages")


@app.command()
def use(
    cube_id: Optional[str] = typer.Argument(None, help="CubeCobra short ID or slug to set as current"),
    clear: bool = typer.Option(False, "--clear", help="Remove the current cube config"),
):
    """Set the current working cube so you can omit <id> from other commands."""
    if clear:
        if os.path.exists(CONFIG_PATH):
            os.remove(CONFIG_PATH)
            typer.echo("Current cube cleared.")
        else:
            typer.echo("No current cube set.")
        return

    if not cube_id:
        typer.echo("Provide a cube ID or use --clear.", err=True)
        raise typer.Exit(1)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"current": cube_id}, f)
    typer.echo(f"Current cube set to: {cube_id}")


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
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    refresh: bool = typer.Option(False, "--refresh", help="Bypass Scryfall cache"),
):
    """Enrich cube cards with Scryfall metadata. Auto-fetches if not found."""
    id_or_slug = resolve_cube_id(id_or_slug)
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
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    color: bool = typer.Option(False, "--color", help="Show color identity chart"),
    cmc: bool = typer.Option(False, "--cmc", help="Show CMC distribution chart"),
    rarity: bool = typer.Option(False, "--rarity", help="Show rarity chart"),
    types: bool = typer.Option(False, "--types", help="Show card type chart"),
    guild: bool = typer.Option(False, "--guild", help="Show guild breakdown chart"),
    show_all: bool = typer.Option(False, "--all", help="Show all charts (color, CMC, rarity, types, creature, guild)"),
    by: Optional[str] = typer.Option(None, "--by", help="Cross-breakdown dimension: color, color-category, rarity, type, creature, guild"),
    metric: Optional[str] = typer.Option(None, "--metric", help="Cross-breakdown metric: cmc, power, toughness"),
    json_out: bool = typer.Option(False, "--json", help="Write exports/analysis.json"),
    md: bool = typer.Option(False, "--md", help="Write exports/analysis.md with Markdown tables"),
):
    """Print cube stats with Unicode bar charts. Default shows 5 key charts."""
    id_or_slug = resolve_cube_id(id_or_slug)
    try:
        cube = load_cube_from_mainboard_csv(id_or_slug)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    s = stats_mod.compute_stats(cube)

    # Try to load enriched.json for CMC summary and cross-breakdown
    cmc_values = None
    enriched_cards = None
    try:
        enriched_cube = load_enriched(id_or_slug)
        enriched_cards = [c for c in enriched_cube.cards if c.board == "mainboard"]
        cmc_values = [float(c.cmc) for c in enriched_cards]
    except FileNotFoundError:
        pass

    # Cross-breakdown
    if by:
        if by not in stats_mod.CROSS_DIMENSIONS:
            typer.echo(
                f"Unknown --by value '{by}'. Choose from: {', '.join(sorted(stats_mod.CROSS_DIMENSIONS))}",
                err=True,
            )
            raise typer.Exit(1)
        if not metric:
            typer.echo("--metric is required with --by. Choose from: cmc, power, toughness", err=True)
            raise typer.Exit(1)
        if metric not in stats_mod.CROSS_METRICS:
            typer.echo(
                f"Unknown --metric value '{metric}'. Choose from: {', '.join(sorted(stats_mod.CROSS_METRICS))}",
                err=True,
            )
            raise typer.Exit(1)
        if enriched_cards is None:
            typer.echo(
                f"Cross-breakdown requires enriched data — run cuber enrich {id_or_slug} first",
                err=True,
            )
            raise typer.Exit(1)
        bd = stats_mod.compute_cross_breakdown(enriched_cards, by, metric)
        typer.echo(stats_mod.format_cross_breakdown(bd, by, metric))

    # Charts — always show unless --by used without any chart flags
    chart_flags_active = any([color, cmc, rarity, types, guild])
    show_charts = (not by) or chart_flags_active or show_all

    if show_charts:
        if show_all:
            chart_list: Optional[List[str]] = ["color", "cmc", "rarity", "types", "creature", "guild"]
        elif chart_flags_active:
            chart_list = (
                (["color"] if color else [])
                + (["cmc"] if cmc else [])
                + (["rarity"] if rarity else [])
                + (["types"] if types else [])
                + (["guild"] if guild else [])
            )
        else:
            chart_list = None  # default 5 charts

        typer.echo(stats_mod.format_stats_report(s, cmc_values=cmc_values, charts=chart_list))

        if chart_list is None and not by:
            tag_data = stats_mod.compute_tag_density(cube)
            typer.echo(stats_mod.format_tag_density_report(tag_data))
            archetype_data = stats_mod.compute_archetype_clusters(cube)
            if archetype_data.get("clusters"):
                typer.echo(stats_mod._format_archetype_clusters(archetype_data["clusters"], s["total_cards"]))

    if json_out:
        tag_data = stats_mod.compute_tag_density(cube)
        archetype_data = stats_mod.compute_archetype_clusters(cube)
        path = stats_mod.write_analysis_json({**s, "tag_density": tag_data, "archetype_clusters": archetype_data}, id_or_slug)
        typer.echo(f"Analysis JSON: {path}")

    if md:
        tag_data = stats_mod.compute_tag_density(cube)
        archetype_data = stats_mod.compute_archetype_clusters(cube)
        s_with_archetypes = {**s, "tag_density": tag_data, "archetype_clusters": archetype_data}
        path = stats_mod.write_analysis_md(s_with_archetypes, id_or_slug)
        typer.echo(f"Analysis Markdown: {path}")


@app.command()
def tag(
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace existing tags"),
):
    """AI-tag all cards using oracle text. Backfills tags to mainboard.csv."""
    id_or_slug = resolve_cube_id(id_or_slug)
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
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    names: Optional[List[str]] = typer.Argument(None, help="Card name(s) to add"),
    from_file: Optional[str] = typer.Option(None, "--from-file", help="Text file with one card name per line"),
    stdin: bool = typer.Option(False, "--stdin", help="Read card names from stdin"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Add to maybeboard instead of mainboard"),
    count: Optional[int] = typer.Option(None, "--count", help="Add this many copies of each card (default: 1 per name supplied)"),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip Scryfall verification (bulk imports with known-good names)"),
):
    """Add one or more cards to the cube mainboard (or maybeboard).

    Always adds exactly what you request — no deduplication against existing cards.
    Passing a name twice adds two copies. Use --count N to add N copies of each card.
    Cards are verified against Scryfall by default; use --no-verify to skip.
    """
    id_or_slug = resolve_cube_id(id_or_slug)
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
        result = add_cards(id_or_slug, all_names, board=board, verify=not no_verify)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if result["added"]:
        typer.echo(f"Added to {board} ({len(result['added'])}):")
        for name in result["added"]:
            typer.echo(f"  + {name}")

    for c in result.get("corrections", []):
        typer.echo(f'  "{c["input"]}" -> added as "{c["canonical"]}"')

    if result.get("not_found"):
        typer.echo(f"\nNot found on Scryfall ({len(result['not_found'])}) — not added:")
        for name in result["not_found"]:
            typer.echo(f"  ? {name}")
        typer.echo("  Re-run with the correct card name.")

    if result.get("unverified"):
        if no_verify:
            typer.echo(f"\n(unverified — run `cuber enrich {id_or_slug}` to hydrate)")
        else:
            for name in result["unverified"]:
                typer.echo(f'  ! "{name}" added unverified (Scryfall unreachable)')

    if result["added"] and not result.get("unverified"):
        typer.echo(f"\nRun `cuber enrich {id_or_slug}` to hydrate new cards with Scryfall data.")


@app.command()
def swap(
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    old_name: Optional[str] = typer.Argument(None, help="Card name to remove"),
    new_name: Optional[str] = typer.Argument(None, help="Card name to add (verified via Scryfall)"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Operate on maybeboard instead of mainboard"),
):
    """Atomically replace one card with another. New card is verified via Scryfall first."""
    # Shift args when current cube is set: swap <old> <new> (2 positional)
    if new_name is None and old_name is not None:
        new_name = old_name
        old_name = id_or_slug
        id_or_slug = None
    id_or_slug = resolve_cube_id(id_or_slug)
    if not old_name or not new_name:
        typer.echo("Provide old and new card names.", err=True)
        raise typer.Exit(1)
    board = "maybeboard" if maybeboard else "mainboard"
    try:
        result = swap_card(id_or_slug, old_name, new_name, board=board)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if "error" in result:
        typer.echo(f"Error: {result['error']}", err=True)
        raise typer.Exit(1)

    typer.echo(f"  - {result['removed']}")
    added_label = result["added"]
    if result.get("correction"):
        added_label = f'{result["added"]}  ("{new_name}" -> swapped in as "{result["added"]}")'
    typer.echo(f"  + {added_label}")
    typer.echo(f"\nRun `cuber enrich {id_or_slug}` to hydrate the new card with Scryfall data.")


@app.command("remove-card")
def remove_card(
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    names: Optional[List[str]] = typer.Argument(None, help="Card name(s) to remove"),
    from_file: Optional[str] = typer.Option(None, "--from-file", help="Text file with one card name per line"),
    stdin: bool = typer.Option(False, "--stdin", help="Read card names from stdin"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Remove from maybeboard instead of mainboard"),
    count: Optional[int] = typer.Option(None, "--count", help="Remove only this many copies (default: all copies)"),
):
    """Remove one or more cards from the cube mainboard (or maybeboard)."""
    id_or_slug = resolve_cube_id(id_or_slug)
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
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Dedup maybeboard instead of mainboard"),
):
    """Remove duplicate card rows, keeping the first copy of each card."""
    id_or_slug = resolve_cube_id(id_or_slug)
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
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
):
    """Show cards added, removed, or retagged since last fetch."""
    id_or_slug = resolve_cube_id(id_or_slug)
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
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    skip_scryfall: bool = typer.Option(False, "--skip-scryfall", help="Skip Scryfall validation (offline use)"),
):
    """Validate mainboard and assemble exports/import-ready.csv."""
    id_or_slug = resolve_cube_id(id_or_slug)
    try:
        result = assemble_export(id_or_slug, skip_scryfall=skip_scryfall)
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
    if result.get("primer_path"):
        typer.echo(f"primer.md   -> {result['primer_path']}")
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
def search(
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    color: Optional[str] = typer.Option(None, "--color", help="Color identity filter, e.g. W,U,B"),
    card_type: Optional[str] = typer.Option(None, "--type", help="Substring match on type line, e.g. creature"),
    cmc_min: Optional[float] = typer.Option(None, "--cmc-min", help="Minimum CMC (inclusive)"),
    cmc_max: Optional[float] = typer.Option(None, "--cmc-max", help="Maximum CMC (inclusive)"),
    oracle: Optional[str] = typer.Option(None, "--oracle", help="Regex pattern against oracle text"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Tag filter; comma-separated, all must match"),
    rarity: Optional[str] = typer.Option(None, "--rarity", help="Exact rarity match: common/uncommon/rare/mythic"),
    limit: int = typer.Option(25, "--limit", help="Maximum number of results to show"),
):
    """Search the local enriched card pool by any combination of criteria."""
    id_or_slug = resolve_cube_id(id_or_slug)
    try:
        pool = load_merged_pool(id_or_slug)
    except FileNotFoundError:
        typer.echo(f"enriched.json not found — run cuber enrich {id_or_slug} first", err=True)
        raise typer.Exit(1)

    color_identity = [c.strip().upper() for c in color.split(",")] if color else None
    tags = [t.strip() for t in tag.split(",")] if tag else None

    results = search_pool(
        pool,
        color_identity=color_identity,
        oracle_pattern=oracle,
        card_type=card_type,
        cmc_min=cmc_min,
        cmc_max=cmc_max,
        tags=tags,
        rarity=rarity,
    )
    typer.echo(format_search_results(results, limit=limit))


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


# ── Shorthand operators: + and rm ─────────────────────────────────────────────

def _parse_count_modifier(args: List[str]) -> Tuple[List[str], int]:
    """Detect trailing count modifier (x N, *N, xN) and return (card_names, count)."""
    if len(args) >= 2 and args[-1].isdigit() and args[-2].lower() in ("x", "*"):
        return args[:-2], int(args[-1])
    if args and re.match(r"^[xX*]\d+$", args[-1]):
        return args[:-1], int(args[-1][1:])
    return args, 1


@app.command("+")
def add_shorthand(
    names: Optional[List[str]] = typer.Argument(None, help="Card name(s) to add"),
    from_file: Optional[str] = typer.Option(None, "--from-file", help="Text file with one card name per line"),
    stdin: bool = typer.Option(False, "--stdin", help="Read card names from stdin"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Add to maybeboard instead of mainboard"),
    count: Optional[int] = typer.Option(None, "--count", help="Add this many copies of each card"),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip Scryfall verification"),
):
    """Shorthand for add-card using the current cube. Supports inline x N / *N count modifier."""
    id_or_slug = resolve_cube_id(None)
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
        typer.echo("No card names provided. Use positional args, --from-file, or --stdin.", err=True)
        raise typer.Exit(1)

    if count is None:
        all_names, count = _parse_count_modifier(all_names)
        if count < 1:
            count = 1
    else:
        all_names, _ = _parse_count_modifier(all_names)

    if count > 1:
        all_names = [name for name in all_names for _ in range(count)]

    board = "maybeboard" if maybeboard else "mainboard"
    try:
        result = add_cards(id_or_slug, all_names, board=board, verify=not no_verify)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if result["added"]:
        typer.echo(f"Added to {board} ({len(result['added'])}):")
        for name in result["added"]:
            typer.echo(f"  + {name}")
    for c in result.get("corrections", []):
        typer.echo(f'  "{c["input"]}" -> added as "{c["canonical"]}"')
    if result.get("not_found"):
        typer.echo(f"\nNot found on Scryfall ({len(result['not_found'])}) — not added:")
        for name in result["not_found"]:
            typer.echo(f"  ? {name}")
    if result["added"] and not result.get("unverified"):
        typer.echo(f"\nRun `cuber enrich {id_or_slug}` to hydrate new cards with Scryfall data.")


@app.command("rm")
def remove_shorthand(
    names: Optional[List[str]] = typer.Argument(None, help="Card name(s) to remove"),
    from_file: Optional[str] = typer.Option(None, "--from-file", help="Text file with one card name per line"),
    stdin: bool = typer.Option(False, "--stdin", help="Read card names from stdin"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Remove from maybeboard instead of mainboard"),
    count: Optional[int] = typer.Option(None, "--count", help="Remove only this many copies (default: all copies)"),
):
    """Shorthand for remove-card using the current cube. Supports inline x N / *N count modifier."""
    id_or_slug = resolve_cube_id(None)
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
        typer.echo("No card names provided. Use positional args, --from-file, or --stdin.", err=True)
        raise typer.Exit(1)

    if count is None:
        all_names, inline_count = _parse_count_modifier(all_names)
        count = inline_count if inline_count > 1 else None
    else:
        all_names, _ = _parse_count_modifier(all_names)

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


# ── Scale operators: x and div ─────────────────────────────────────────────────

@app.command("x")
def scale_multiply(
    factor: int = typer.Argument(..., help="Multiplication factor (≥ 2)"),
    names: Optional[List[str]] = typer.Argument(None, help="Card name(s) to scale"),
    id_or_slug: Optional[str] = typer.Option(None, "--cube", help="Cube ID (overrides current cube)"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Operate on maybeboard"),
):
    """Multiply existing copy counts by N. cuber x 2 'Serra Angel' doubles its copies."""
    if factor < 2:
        typer.echo("Factor must be at least 2.", err=True)
        raise typer.Exit(1)
    id_or_slug = resolve_cube_id(id_or_slug)
    if not names:
        typer.echo("Provide at least one card name.", err=True)
        raise typer.Exit(1)
    board = "maybeboard" if maybeboard else "mainboard"
    try:
        result = scale_cards(id_or_slug, list(names), factor, "multiply", board=board)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    for entry in result["scaled"]:
        typer.echo(f"  {entry['name']}: {entry['before']} → {entry['after']} copies")
    for name in result["not_found"]:
        typer.echo(f"  {name}: not in cube — skipped")


@app.command("div")
def scale_divide(
    factor: int = typer.Argument(..., help="Division factor (≥ 2)"),
    names: Optional[List[str]] = typer.Argument(None, help="Card name(s) to scale"),
    id_or_slug: Optional[str] = typer.Option(None, "--cube", help="Cube ID (overrides current cube)"),
    maybeboard: bool = typer.Option(False, "--maybeboard", help="Operate on maybeboard"),
):
    """Divide existing copy counts by N (floor). Prompts before removing last copy."""
    if factor < 2:
        typer.echo("Factor must be at least 2.", err=True)
        raise typer.Exit(1)
    id_or_slug = resolve_cube_id(id_or_slug)
    if not names:
        typer.echo("Provide at least one card name.", err=True)
        raise typer.Exit(1)
    board = "maybeboard" if maybeboard else "mainboard"

    # Pre-screen for zero-result cards and prompt before applying
    import math as _math
    cube_folder = find_cube_dir(id_or_slug)
    csv_path = os.path.join(cube_folder, "mainboard.csv" if board == "mainboard" else "maybeboard.csv")
    counts: Dict[str, int] = {}
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                n = row.get("name", "").strip()
                if n:
                    counts[n.lower()] = counts.get(n.lower(), 0) + 1

    confirmed_names: List[str] = []
    for name in names:
        key = name.strip().lower()
        current = counts.get(key, 0)
        if current == 0:
            continue  # scale_cards will report not_found
        new_count = _math.floor(current / factor)
        if new_count == 0:
            answer = typer.confirm(
                f"{name}: {current} → 0 copies (will remove from cube). Proceed?",
                default=False,
            )
            if not answer:
                typer.echo(f"  Skipped {name}.")
                continue
        confirmed_names.append(name)

    if not confirmed_names:
        typer.echo("No cards to scale.")
        return

    try:
        result = scale_cards(id_or_slug, confirmed_names, factor, "divide", board=board)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    for entry in result["scaled"]:
        typer.echo(f"  {entry['name']}: {entry['before']} → {entry['after']} copies")
    for name in result["not_found"]:
        typer.echo(f"  {name}: not in cube — skipped")


# ── search-card ────────────────────────────────────────────────────────────────

@app.command("search-card")
def search_card(
    query: str = typer.Argument(..., help="Card name to search for (substring match)"),
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    color: Optional[str] = typer.Option(None, "--color", help="Color identity filter, e.g. W,U"),
    card_type: Optional[str] = typer.Option(None, "--type", help="Substring match on type line"),
    cmc_min: Optional[float] = typer.Option(None, "--cmc-min", help="Minimum CMC (inclusive)"),
    cmc_max: Optional[float] = typer.Option(None, "--cmc-max", help="Maximum CMC (inclusive)"),
    rarity: Optional[str] = typer.Option(None, "--rarity", help="Exact rarity: common/uncommon/rare/mythic"),
    use_scryfall: bool = typer.Option(False, "--scryfall", help="Skip cube and search Scryfall directly"),
):
    """Fuzzy name search within the cube. Falls back to Scryfall when not found."""
    id_or_slug = resolve_cube_id(id_or_slug)

    if use_scryfall:
        cards = scryfall.name_search(query)
        if not cards:
            typer.echo("Not found on Scryfall.")
        else:
            typer.echo(format_search_card_results(cards))
        return

    try:
        pool = load_merged_pool(id_or_slug)
    except FileNotFoundError:
        typer.echo(f"enriched.json not found — run cuber enrich {id_or_slug} first", err=True)
        raise typer.Exit(1)

    results = fuzzy_name_search(pool, query)

    # Apply filters
    if color:
        ci_filter = {c.strip().upper() for c in color.split(",")}
        results = [c for c in results if set(c.get("color_identity") or []).issubset(ci_filter)]
    if card_type:
        results = [c for c in results if card_type.lower() in (c.get("type_line") or "").lower()]
    if rarity:
        results = [c for c in results if (c.get("rarity") or "").lower() == rarity.lower()]
    if cmc_min is not None:
        results = [c for c in results if float(c.get("cmc") or 0) >= cmc_min]
    if cmc_max is not None:
        results = [c for c in results if float(c.get("cmc") or 0) <= cmc_max]

    if results:
        typer.echo(format_search_card_results(results))
        return

    # Not found in cube — offer Scryfall fallback
    answer = typer.confirm("Not found in cube — search Scryfall?", default=False)
    if answer:
        cards = scryfall.name_search(query)
        if not cards:
            typer.echo("Not found on Scryfall either.")
        else:
            typer.echo(format_search_card_results(cards))


# ── ops REPL ───────────────────────────────────────────────────────────────────

def _ops_tokenize(line: str) -> Tuple[str, List[str], int]:
    """Parse a REPL input line. Returns (operator, card_names, modifier).

    operator: one of +, -, *, /, list, undo, reset, done, quit
    modifier: count for +/-, factor for *//, undo index for undo, else 0
    """
    try:
        tokens = shlex.split(line.strip())
    except ValueError:
        return ("error", [], 0)

    if not tokens:
        return ("empty", [], 0)

    raw_op = tokens[0]
    op = raw_op.lower()
    rest = tokens[1:]

    # Normalize aliases
    alias_map = {"ls": "list", "apply": "done", "exit": "quit"}
    op = alias_map.get(op, op)

    if op in ("quit", "list", "reset"):
        return (op, [], 0)

    if op == "done":
        return ("done", [], 0)

    if op == "undo":
        idx = int(rest[0]) if rest and rest[0].isdigit() else 0
        return ("undo", [], idx)

    # Scale operators: first rest token is the factor
    if raw_op in ("*", "/"):
        if not rest or not rest[0].isdigit():
            return ("error", [], 0)
        factor = int(rest[0])
        names = rest[1:]
        names, _ = _parse_count_modifier(names)
        return (raw_op, names, factor)

    if raw_op in ("+", "-"):
        names, count = _parse_count_modifier(rest)
        return (raw_op, names, count)

    return ("unknown", [], 0)


def _ops_validate_add(names: List[str], _id_or_slug: str) -> Tuple[List[str], List[str]]:
    """Scryfall-verify add candidates. Returns (valid_canonical, invalid)."""
    valid: List[str] = []
    invalid: List[str] = []
    for name in names:
        try:
            card = scryfall.fuzzy_lookup(name)
        except scryfall.ScryfallNetworkError:
            valid.append(name)
            continue
        if card is None:
            invalid.append(name)
        else:
            valid.append(card["name"])
    return valid, invalid


def _ops_validate_remove(names: List[str], id_or_slug: str) -> Tuple[List[str], List[str]]:
    """Check names against mainboard.csv. Returns (found, not_found)."""
    try:
        cube_folder = find_cube_dir(id_or_slug)
    except FileNotFoundError:
        return [], names[:]
    csv_path = os.path.join(cube_folder, "mainboard.csv")
    in_cube: set = set()
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                n = row.get("name", "").strip()
                if n:
                    in_cube.add(n.lower())
    found = [n for n in names if n.strip().lower() in in_cube]
    not_found = [n for n in names if n.strip().lower() not in in_cube]
    return found, not_found


def _ops_cube_counts(id_or_slug: str) -> Dict[str, int]:
    """Return {name_lower: copy_count} from mainboard.csv."""
    try:
        cube_folder = find_cube_dir(id_or_slug)
    except FileNotFoundError:
        return {}
    csv_path = os.path.join(cube_folder, "mainboard.csv")
    counts: Dict[str, int] = {}
    if not os.path.exists(csv_path):
        return counts
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n = row.get("name", "").strip()
            if n:
                counts[n.lower()] = counts.get(n.lower(), 0) + 1
    return counts


def _ops_print_staged(staging: List[Dict]) -> None:
    if not staging:
        typer.echo("No operations staged.")
        return
    for i, entry in enumerate(staging, 1):
        for line in entry["display_lines"]:
            typer.echo(f"  [{i}] {line}")


def _ops_net_delta(staging: List[Dict]) -> int:
    return sum(e.get("delta", 0) for e in staging)


@app.command("ops")
def ops(
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
):
    """Interactive REPL for staging and applying batch cube edits.

    Operators: + (add), - (remove), * N (scale up), / N (scale down)
    Control: list, undo [N], reset, done, quit
    Card names with spaces must be quoted: + "Serra Angel"
    """
    import math as _math

    id_or_slug = resolve_cube_id(id_or_slug)
    staging: List[Dict] = []

    typer.echo(f"ops ({id_or_slug})> type + - * / list undo reset done quit")
    typer.echo("  Card names with spaces must be quoted: + \"Serra Angel\"")

    while True:
        try:
            line = input("ops> ").strip()
        except (EOFError, KeyboardInterrupt):
            discarded = len(staging)
            if discarded:
                typer.echo(f"\nExited without applying. {discarded} operation(s) discarded.")
            else:
                typer.echo("")
            break

        if not line:
            continue

        op, names, modifier = _ops_tokenize(line)

        if op == "quit":
            discarded = len(staging)
            if discarded:
                typer.echo(f"Exited without applying. {discarded} operation(s) discarded.")
            break

        if op == "list":
            _ops_print_staged(staging)
            if staging:
                delta = _ops_net_delta(staging)
                sign = "+" if delta >= 0 else ""
                typer.echo(f"  Net: {sign}{delta} card(s)")
            continue

        if op == "reset":
            staging.clear()
            typer.echo("All staged operations cleared.")
            continue

        if op == "undo":
            if not staging:
                typer.echo("Nothing to undo.")
                continue
            idx = modifier if modifier else len(staging)
            if idx < 1 or idx > len(staging):
                typer.echo(f"Index {idx} out of range (1–{len(staging)}).")
                continue
            removed = staging.pop(idx - 1)
            typer.echo(f"Removed [{idx}]: {removed['display_lines'][0]}")
            continue

        if op == "done":
            if not staging:
                typer.echo("Nothing staged — nothing to apply.")
                break

            _ops_print_staged(staging)
            delta = _ops_net_delta(staging)
            sign = "+" if delta >= 0 else ""
            typer.echo(f"  Net: {sign}{delta} card(s)")
            if not typer.confirm("Apply?", default=False):
                typer.echo("Cancelled. Continuing...")
                continue

            applied = 0
            for entry in staging:
                eop = entry["op"]
                enames = entry["names"]
                ecount = entry.get("count")
                efactor = entry.get("factor")
                try:
                    if eop == "+":
                        add_count = ecount or 1
                        all_add = [n for n in enames for _ in range(add_count)]
                        add_cards(id_or_slug, all_add, board="mainboard", verify=False)
                    elif eop == "-":
                        remove_cards(id_or_slug, enames, board="mainboard", count=ecount)
                    elif eop == "*":
                        scale_cards(id_or_slug, enames, efactor, "multiply", board="mainboard")
                    elif eop == "/":
                        scale_cards(id_or_slug, enames, efactor, "divide", board="mainboard")
                    applied += 1
                except Exception as exc:
                    typer.echo(f"  Error applying {entry['display_lines'][0]}: {exc}", err=True)

            typer.echo(f"Applied {applied}/{len(staging)} operation(s).")
            break

        if op == "error" or op == "unknown":
            typer.echo("  Unknown command. Use + - * / list undo reset done quit.")
            continue

        if op == "empty":
            continue

        # Staging logic
        counts = _ops_cube_counts(id_or_slug)

        if op == "+":
            if not names:
                typer.echo("  Provide card name(s) after +.")
                continue
            valid, invalid = _ops_validate_add(names, id_or_slug)
            for bad in invalid:
                typer.echo(f'  ✗ "{bad}" — not found on Scryfall. Skipped.')
            if not valid:
                continue
            count = modifier if modifier > 1 else 1
            delta = len(valid) * count
            display_lines = [f"add {n} ×{count}" for n in valid]
            staging.append({"op": "+", "names": valid, "count": count, "factor": None,
                            "delta": delta, "display_lines": display_lines})
            for dl in display_lines:
                typer.echo(f"  ✓ Staged: {dl}")

        elif op == "-":
            if not names:
                typer.echo("  Provide card name(s) after -.")
                continue
            found, not_found = _ops_validate_remove(names, id_or_slug)
            for bad in not_found:
                typer.echo(f'  ✗ "{bad}" — not in cube. Skipped.')
            if not found:
                continue
            count = modifier if modifier > 1 else None
            delta = 0
            display_lines = []
            for n in found:
                if count:
                    display_lines.append(f"remove {n} ×{count}")
                    delta -= count
                else:
                    current = counts.get(n.lower(), 1)
                    display_lines.append(f"remove {n} (all copies)")
                    delta -= current
            staging.append({"op": "-", "names": found, "count": count, "factor": None,
                            "delta": delta, "display_lines": display_lines})
            for dl in display_lines:
                typer.echo(f"  ✓ Staged: {dl}")

        elif op in ("*", "/"):
            factor = modifier
            if factor < 2:
                typer.echo("  Factor must be at least 2.")
                continue
            if not names:
                typer.echo(f"  Provide card name(s) after {op} {factor}.")
                continue
            found, not_found = _ops_validate_remove(names, id_or_slug)
            for bad in not_found:
                typer.echo(f'  ✗ "{bad}" — not in cube. Skipped.')
            if not found:
                continue
            display_lines = []
            delta = 0
            for n in found:
                current = counts.get(n.lower(), 0)
                if op == "*":
                    new_count = current * factor
                else:
                    new_count = _math.floor(current / factor)
                    if new_count == 0:
                        typer.echo(f"  ⚠ {n}: {current} → 0 copies (will remove from cube)")
                d = new_count - current
                delta += d
                display_lines.append(f"scale {n} ×{factor} ({current} → {new_count})")
            staging.append({"op": op, "names": found, "count": None, "factor": factor,
                            "delta": delta, "display_lines": display_lines})
            for dl in display_lines:
                typer.echo(f"  ✓ Staged: {dl}")


# ── Packages ──────────────────────────────────────────────────────────────────

@packages_app.command("search")
def packages_search(
    keywords: str = typer.Argument("", help="Keywords to search for (leave empty for popular packages)"),
    show_cards: bool = typer.Option(False, "--show-cards", help="List card names under each package"),
):
    """List CubeCobra packages. Shows popular packages when no keywords given."""
    try:
        packages = cubecobra.fetch_packages(keywords=keywords)
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if not packages:
        if keywords:
            typer.echo(f'No packages found for "{keywords}".')
        else:
            typer.echo("No packages found.")
        return

    col_id = 8
    col_title = 34
    col_cards = 6
    col_votes = 6
    header = f"{'ID':<{col_id}}  {'Title':<{col_title}}  {'Cards':>{col_cards}}  {'Votes':>{col_votes}}"
    typer.echo(header)
    typer.echo("-" * (col_id + col_title + col_cards + col_votes + 6))

    for pkg in packages:
        pkg_id = (pkg.get("_id") or pkg.get("id") or "")[:col_id]
        title = (pkg.get("title") or pkg.get("name") or "")[:col_title]
        card_count = len(pkg.get("cards") or [])
        votes = pkg.get("votes") or pkg.get("voteCount") or 0
        typer.echo(f"{pkg_id:<{col_id}}  {title:<{col_title}}  {card_count:>{col_cards}}  {votes:>{col_votes}}")

        if show_cards:
            for card in (pkg.get("cards") or []):
                name = card.get("name") if isinstance(card, dict) else str(card)
                typer.echo(f"    {name}")


@app.command("add-package")
def add_package_cmd(
    id_or_slug: Optional[str] = typer.Argument(None, help="CubeCobra short ID or cube slug"),
    package_id: Optional[str] = typer.Argument(None, help="CubeCobra package ID"),
    allow_duplicates: bool = typer.Option(False, "--allow-duplicates", help="Add cards even if already in cube"),
):
    """Fetch a CubeCobra package and add all its cards to the cube."""
    # Shift args when current cube is set: add-package <pkg-id> (1 positional)
    if package_id is None and id_or_slug is not None:
        package_id = id_or_slug
        id_or_slug = None
    id_or_slug = resolve_cube_id(id_or_slug)
    if not package_id:
        typer.echo("Provide a package ID.", err=True)
        raise typer.Exit(1)
    try:
        pkg = cubecobra.fetch_package_by_id(package_id)
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if pkg is None:
        typer.echo(f"Package '{package_id}' not found on CubeCobra.", err=True)
        raise typer.Exit(1)

    title = pkg.get("title") or pkg.get("name") or package_id
    pkg_cards = pkg.get("cards") or []
    typer.echo(f"Package: {title} ({len(pkg_cards)} cards)")

    try:
        result = add_cards_from_package(id_or_slug, pkg_cards, allow_duplicates=allow_duplicates)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    if result["added"]:
        typer.echo(f"\nAdded ({len(result['added'])}):")
        for name in result["added"]:
            typer.echo(f"  + {name}")

    if result["skipped_existing"]:
        typer.echo(f"\nSkipped — already in cube ({len(result['skipped_existing'])}):")
        for name in result["skipped_existing"][:10]:
            typer.echo(f"  = {name}")
        if len(result["skipped_existing"]) > 10:
            typer.echo(f"  ... and {len(result['skipped_existing']) - 10} more")

    typer.echo(f"\nEnriched {result['enriched_count']} card(s) in enriched.json.")
    if result["added"]:
        typer.echo(f"Run `cuber export {id_or_slug}` to assemble import-ready.csv.")

"""Cube project lifecycle — fetch/disassemble, add-card, status, export."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import typer

from .cube import CUBES_DIR, CUBECOBRA_CSV_COLUMNS, Card, Cube, find_cube_dir, load_enriched, save_enriched, cube_dir, load_meta
from .cubecobra import _fetch_url
from .scryfall import fuzzy_lookup, ScryfallNetworkError

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cuber-config.json")


def resolve_cube_id(explicit: Optional[str]) -> str:
    """Return the cube ID to use, or exit with an error message if none available."""
    if explicit:
        return explicit
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            current = data.get("current")
            if current:
                return current
        except (json.JSONDecodeError, OSError):
            pass
    typer.echo(
        "No cube specified and no current cube set. Run `cuber use <id>` or pass the cube ID.",
        err=True,
    )
    raise typer.Exit(1)


# ── Slug utilities ─────────────────────────────────────────────────────────────

def slugify(name: str, short_id: str = "") -> str:
    """Convert a cube title to a filesystem-safe slug."""
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug or short_id or "cube"


def _used_slugs() -> set:
    if not os.path.isdir(CUBES_DIR):
        return set()
    return {e.name for e in os.scandir(CUBES_DIR) if e.is_dir()}


def _resolve_or_create_slug(title: str, short_id: str) -> str:
    """Return slug for a cube: existing slug if already fetched, new slug otherwise."""
    try:
        existing = find_cube_dir(short_id)
        return os.path.basename(existing)
    except FileNotFoundError:
        pass
    used = _used_slugs()
    base = slugify(title, short_id)
    slug = base
    if slug in used:
        slug = f"{base}-{short_id}"
    return slug


# ── cubeJSON card → CSV row ────────────────────────────────────────────────────

def _cubecobra_card_to_csv_row(card: Dict[str, Any]) -> Dict[str, str]:
    """Map a cubeJSON card object to the v1 CSV column format."""
    colors = card.get("colors") or []
    tags = card.get("tags") or []
    image_uris = card.get("image_uris") or {}
    try:
        cmc_int = str(int(float(card.get("cmc") or 0)))
    except (TypeError, ValueError):
        cmc_int = ""
    return {
        "name": card.get("name", ""),
        "CMC": cmc_int,
        "Type": card.get("type_line", ""),
        "Color": "".join(colors),
        "Set": (card.get("set") or "").upper(),
        "Collector Number": card.get("collector_number", ""),
        "Rarity": (card.get("rarity") or "").capitalize(),
        "Color Category": card.get("colorCategory") or card.get("color_category") or "",
        "status": card.get("status", ""),
        "Finish": card.get("finish") or "Non-Foil",
        "board": card.get("board", "mainboard"),
        "maybeboard": "false",
        "image URL": card.get("image_normal") or image_uris.get("normal", ""),
        "image Back URL": "",
        "tags": ";".join(str(t) for t in tags if t),
        "Notes": card.get("notes", ""),
        "MTGO ID": "",
        "Custom": "false",
        "Voucher": "false",
    }


def _write_cards_csv(cards: List[Dict[str, Any]], path: str) -> None:
    """Write a list of cubeJSON card dicts to CSV using the v1 column format."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=CUBECOBRA_CSV_COLUMNS, extrasaction="ignore"
        )
        writer.writeheader()
        for card in cards:
            writer.writerow(_cubecobra_card_to_csv_row(card))


# ── Merge helpers ──────────────────────────────────────────────────────────────

def _merge_mainboard(working_path: str, remote_path: str) -> None:
    """Re-fetch merge: add new remote cards; preserve local removals."""
    with open(working_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or CUBECOBRA_CSV_COLUMNS)
        working_rows = list(reader)
    with open(remote_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        remote_rows = list(reader)

    working_names_lower = {r.get("name", "").strip().lower() for r in working_rows}
    added = []
    for row in remote_rows:
        name_lower = row.get("name", "").strip().lower()
        if name_lower and name_lower not in working_names_lower:
            working_rows.append(row)
            working_names_lower.add(name_lower)
            added.append(row.get("name", ""))

    if added:
        print(f"  Merge: added {len(added)} new card(s) from remote:")
        for n in added[:5]:
            print(f"    + {n}")
        if len(added) > 5:
            print(f"    ... and {len(added) - 5} more")

    with open(working_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(working_rows)


# ── Fetch & disassemble ────────────────────────────────────────────────────────

def fetch_and_disassemble(short_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """Fetch cubeJSON from CubeCobra and disassemble into a project folder."""
    if dry_run:
        print(f"[dry-run] Would fetch: https://cubecobra.com/cube/api/cubeJSON/{short_id}")
        return {}

    print(f"Fetching cube '{short_id}' from CubeCobra...")

    cube_json: Optional[Dict] = None
    try:
        raw = _fetch_url(f"https://cubecobra.com/cube/api/cubeJSON/{short_id}")
        if raw:
            cube_json = json.loads(raw)
    except Exception as e:
        print(f"  cubeJSON fetch failed ({e}), falling back to CSV...")

    if cube_json is None:
        return _fetch_csv_only(short_id)

    title = cube_json.get("name") or short_id
    slug = _resolve_or_create_slug(title, short_id)

    cube_folder = os.path.join(CUBES_DIR, slug)
    remote_dir = os.path.join(cube_folder, "remote")
    os.makedirs(remote_dir, exist_ok=True)
    os.makedirs(os.path.join(cube_folder, "exports"), exist_ok=True)
    os.makedirs(os.path.join(cube_folder, "decks"), exist_ok=True)

    # remote/cube.json — pristine snapshot
    with open(os.path.join(remote_dir, "cube.json"), "w", encoding="utf-8") as f:
        json.dump(cube_json, f, indent=2, ensure_ascii=False)

    # Extract card lists
    cards_block = cube_json.get("cards", {})
    if isinstance(cards_block, dict):
        mainboard_cards = cards_block.get("mainboard") or []
        maybeboard_cards = cards_block.get("maybeboard") or []
    else:
        mainboard_cards = cube_json.get("mainboard") or []
        maybeboard_cards = cube_json.get("maybeboard") or []

    # remote/mainboard.csv — pristine snapshot
    remote_csv = os.path.join(remote_dir, "mainboard.csv")
    _write_cards_csv(mainboard_cards, remote_csv)
    print(f"  remote/mainboard.csv ({len(mainboard_cards)} cards)")

    # meta.json
    meta: Dict[str, Any] = {
        "title": title,
        "id": short_id,
        "slug": slug,
        "format": cube_json.get("type", ""),
        "owner": cube_json.get("owner", ""),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "card_count": len(mainboard_cards),
        "missing_cards": [],
        "schema_warning": None,
    }
    with open(os.path.join(cube_folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # primer.md — don't overwrite user edits on re-fetch
    primer_path = os.path.join(cube_folder, "primer.md")
    if not os.path.exists(primer_path):
        description = cube_json.get("description") or ""
        with open(primer_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n{description}\n" if description else f"# {title}\n")

    # Working mainboard.csv — copy on first fetch, merge on re-fetch
    working_csv = os.path.join(cube_folder, "mainboard.csv")
    if not os.path.exists(working_csv):
        shutil.copy2(remote_csv, working_csv)
        print(f"  mainboard.csv (working copy created)")
    else:
        _merge_mainboard(working_csv, remote_csv)

    # Working maybeboard.csv — only create, never overwrite
    maybe_csv = os.path.join(cube_folder, "maybeboard.csv")
    if not os.path.exists(maybe_csv):
        _write_cards_csv(maybeboard_cards, maybe_csv)

    print(f"\nCube project: cubes/{slug}/")
    return meta


def _fetch_csv_only(short_id: str) -> Dict[str, Any]:
    """Fallback when cubeJSON is unavailable: fetch CSV, use short_id as slug."""
    csv_url = f"https://cubecobra.com/cube/download/csv/{short_id}"
    content = _fetch_url(csv_url)
    if content is None:
        raise RuntimeError(
            f"Cube '{short_id}' not found. Check the ID and ensure the cube is public."
        )

    slug = short_id
    cube_folder = os.path.join(CUBES_DIR, slug)
    remote_dir = os.path.join(cube_folder, "remote")
    os.makedirs(remote_dir, exist_ok=True)
    os.makedirs(os.path.join(cube_folder, "exports"), exist_ok=True)
    os.makedirs(os.path.join(cube_folder, "decks"), exist_ok=True)

    remote_csv = os.path.join(remote_dir, "mainboard.csv")
    with open(remote_csv, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    working_csv = os.path.join(cube_folder, "mainboard.csv")
    if not os.path.exists(working_csv):
        shutil.copy2(remote_csv, working_csv)

    card_count = max(0, content.count("\n") - 1)
    meta: Dict[str, Any] = {
        "title": short_id,
        "id": short_id,
        "slug": slug,
        "format": "",
        "owner": "",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "card_count": card_count,
        "missing_cards": [],
        "schema_warning": None,
    }
    with open(os.path.join(cube_folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    primer_path = os.path.join(cube_folder, "primer.md")
    if not os.path.exists(primer_path):
        with open(primer_path, "w", encoding="utf-8") as f:
            f.write(f"# {short_id}\n")

    print(f"  Note: cubeJSON unavailable; fetched CSV only.")
    print(f"\nCube project: cubes/{slug}/")
    return meta


# ── add-card ───────────────────────────────────────────────────────────────────

def add_cards(
    id_or_slug: str,
    names: List[str],
    board: str = "mainboard",
    verify: bool = True,
) -> Dict[str, Any]:
    """Add one or more cards as stub rows to mainboard.csv or maybeboard.csv.

    Always appends exactly the names given — no deduplication against existing rows.
    Pass the same name multiple times to add multiple copies.

    With verify=True (default): calls Scryfall fuzzy lookup per card. Exact/fuzzy matches
    use the canonical Scryfall name. Not-found cards are rejected. Network failures add
    the card as an unverified stub. With verify=False: writes all names as stubs immediately.
    """
    cube_folder = find_cube_dir(id_or_slug)
    csv_filename = "mainboard.csv" if board == "mainboard" else "maybeboard.csv"
    csv_path = os.path.join(cube_folder, csv_filename)

    existing_rows: List[Dict] = []
    fieldnames = list(CUBECOBRA_CSV_COLUMNS)

    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or CUBECOBRA_CSV_COLUMNS)
            existing_rows = list(reader)

    stub_base = {col: "" for col in fieldnames}
    added: List[str] = []
    corrections: List[Dict[str, str]] = []
    not_found: List[str] = []
    unverified: List[str] = []

    for raw_name in names:
        name = " ".join(raw_name.strip().split())
        if not name:
            continue

        if not verify:
            existing_rows.append({**stub_base, "name": name})
            added.append(name)
            unverified.append(name)
            continue

        try:
            card = fuzzy_lookup(name)
        except ScryfallNetworkError:
            existing_rows.append({**stub_base, "name": name})
            added.append(name)
            unverified.append(name)
            continue

        if card is None:
            not_found.append(name)
            continue

        canonical = card["name"]
        if canonical.lower() != name.lower():
            corrections.append({"input": name, "canonical": canonical})

        existing_rows.append({**stub_base, "name": canonical})
        added.append(canonical)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing_rows)

    return {
        "added": added,
        "corrections": corrections,
        "not_found": not_found,
        "unverified": unverified,
    }


# ── remove-card ────────────────────────────────────────────────────────────────

def remove_cards(
    id_or_slug: str,
    names: List[str],
    board: str = "mainboard",
    count: Optional[int] = 1,
) -> Dict[str, Any]:
    """Remove cards from mainboard.csv or maybeboard.csv.

    By default removes ONE copy of each named card. Pass count to remove
    a specific number. Pass count=None to remove all copies.
    """
    cube_folder = find_cube_dir(id_or_slug)
    csv_filename = "mainboard.csv" if board == "mainboard" else "maybeboard.csv"
    csv_path = os.path.join(cube_folder, csv_filename)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"{csv_filename} not found in {cube_folder}")

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or CUBECOBRA_CSV_COLUMNS)
        existing_rows = list(reader)

    target_lower = {" ".join(n.strip().split()).lower() for n in names if n.strip()}
    removed: List[str] = []
    not_found: List[str] = []

    # Track how many copies we've removed per card (for --count mode)
    removed_counts: Dict[str, int] = {}
    kept_rows: List[Dict] = []

    for row in existing_rows:
        name = row.get("name", "").strip()
        name_lower = name.lower()
        if name_lower in target_lower:
            already_removed = removed_counts.get(name_lower, 0)
            if count is None or already_removed < count:
                removed_counts[name_lower] = already_removed + 1
                if name not in removed:
                    removed.append(name)
            else:
                kept_rows.append(row)
        else:
            kept_rows.append(row)

    for name in names:
        name_lower = " ".join(name.strip().split()).lower()
        if name_lower not in removed_counts:
            not_found.append(name.strip())

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(kept_rows)

    return {
        "removed": removed,
        "removed_counts": removed_counts,
        "not_found": not_found,
    }


# ── dedup ──────────────────────────────────────────────────────────────────────

def dedup_mainboard(id_or_slug: str, board: str = "mainboard") -> Dict[str, Any]:
    """Remove duplicate rows from mainboard.csv, keeping the first occurrence of each name."""
    cube_folder = find_cube_dir(id_or_slug)
    csv_filename = "mainboard.csv" if board == "mainboard" else "maybeboard.csv"
    csv_path = os.path.join(cube_folder, csv_filename)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"{csv_filename} not found in {cube_folder}")

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or CUBECOBRA_CSV_COLUMNS)
        existing_rows = list(reader)

    seen: set = set()
    deduped: List[Dict] = []
    duplicates: Dict[str, int] = {}

    for row in existing_rows:
        name = row.get("name", "").strip()
        name_lower = name.lower()
        if not name_lower:
            deduped.append(row)
            continue
        if name_lower in seen:
            duplicates[name] = duplicates.get(name, 1) + 1
        else:
            seen.add(name_lower)
            deduped.append(row)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deduped)

    return {
        "total_before": len(existing_rows),
        "total_after": len(deduped),
        "duplicates_removed": len(existing_rows) - len(deduped),
        "affected_cards": duplicates,
    }


# ── status ─────────────────────────────────────────────────────────────────────

def _load_csv_by_name(path: str) -> Dict[str, Dict]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {
            r["name"].strip(): r
            for r in reader
            if r.get("name", "").strip()
        }


def cube_status(id_or_slug: str) -> Dict[str, Any]:
    """Diff local working mainboard.csv against remote/mainboard.csv."""
    cube_folder = find_cube_dir(id_or_slug)
    remote = _load_csv_by_name(os.path.join(cube_folder, "remote", "mainboard.csv"))
    working = _load_csv_by_name(os.path.join(cube_folder, "mainboard.csv"))

    remote_names = set(remote)
    working_names = set(working)

    added = sorted(working_names - remote_names)
    removed = sorted(remote_names - working_names)

    tag_changed = []
    for name in remote_names & working_names:
        r_tags = remote[name].get("tags", "")
        w_tags = working[name].get("tags", "")
        if r_tags != w_tags:
            tag_changed.append({
                "name": name,
                "remote_tags": r_tags,
                "local_tags": w_tags,
            })

    return {
        "added": added,
        "removed": removed,
        "tag_changed": tag_changed,
        "unchanged_count": len(remote_names & working_names) - len(tag_changed),
    }


# ── tag backfill ───────────────────────────────────────────────────────────────

def backfill_tags_to_mainboard(cube: Cube, id_or_slug: str) -> int:
    """Write tags from a tagged Cube back into mainboard.csv."""
    cube_folder = find_cube_dir(id_or_slug)
    csv_path = os.path.join(cube_folder, "mainboard.csv")
    if not os.path.exists(csv_path):
        return 0

    tag_index = {c.name.strip().lower(): c for c in cube.cards}

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or CUBECOBRA_CSV_COLUMNS)
        rows = list(reader)

    updated = 0
    for row in rows:
        name = row.get("name", "").strip()
        card = tag_index.get(name.lower())
        if card is None:
            continue
        new_tags = ";".join(card.tags)
        if row.get("tags", "") != new_tags:
            row["tags"] = new_tags
            updated += 1

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return updated


# ── export helpers ────────────────────────────────────────────────────────────

def _load_enriched_index(cube_folder: str) -> Dict[str, str]:
    """Load enriched.json and return {name_lower: scryfall_id}. Empty dict if missing."""
    path = os.path.join(cube_folder, "enriched.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {
            c["name"].strip().lower(): c["scryfall_id"]
            for c in data.get("cards", [])
            if c.get("scryfall_id")
        }
    except (json.JSONDecodeError, OSError, KeyError):
        return {}


def _verify_cards_scryfall(names: List[str]) -> Dict[str, List[str]]:
    """Verify card names via live Scryfall fuzzy lookup.

    Returns {"failed": [...], "network_errors": [...]}.
    Rate delay is handled inside fuzzy_lookup.
    """
    failed: List[str] = []
    network_errors: List[str] = []
    for name in names:
        try:
            card = fuzzy_lookup(name)
            if card is None:
                failed.append(name)
        except ScryfallNetworkError:
            network_errors.append(name)
    return {"failed": failed, "network_errors": network_errors}


def _compute_enrichment_coverage(rows: List[Dict], enriched_index: Dict[str, str]) -> str:
    """Return "N/M" where N = rows with a scryfall_id in enriched_index, M = total rows."""
    total = len(rows)
    covered = sum(
        1 for r in rows
        if enriched_index.get(r.get("name", "").strip().lower())
    )
    return f"{covered}/{total}"


def _compute_rarity_delta(
    cube_folder: str,
    diff: Dict[str, Any],
) -> Dict[str, Dict[str, int]]:
    """Return per-rarity added/removed counts based on the cube_status diff."""
    working = _load_csv_by_name(os.path.join(cube_folder, "mainboard.csv"))
    remote = _load_csv_by_name(os.path.join(cube_folder, "remote", "mainboard.csv"))

    result: Dict[str, Dict[str, int]] = {}
    for name in diff.get("added", []):
        row = working.get(name)
        if row:
            rarity = (row.get("Rarity") or "unknown").lower()
            entry = result.setdefault(rarity, {"added": 0, "removed": 0})
            entry["added"] += 1
    for name in diff.get("removed", []):
        row = remote.get(name)
        if row:
            rarity = (row.get("Rarity") or "unknown").lower()
            entry = result.setdefault(rarity, {"added": 0, "removed": 0})
            entry["removed"] += 1
    return result


# ── export ─────────────────────────────────────────────────────────────────────

def _validate_mainboard(rows: List[Dict[str, str]]) -> Dict[str, List[str]]:
    """Run pre-flight checks on mainboard rows. Returns errors and warnings."""
    errors: List[str] = []
    warnings: List[str] = []

    # Missing collector number — only warn for cards that are enriched
    missing_cn = [
        r["name"].strip() for r in rows
        if r.get("CMC", "").strip() and not r.get("Collector Number", "").strip()
    ]
    if missing_cn:
        warnings.append(f"{len(missing_cn)} card(s) missing collector number")

    # Tag coverage — only warn if at least some cards are tagged
    any_tagged = any(r.get("tags", "").strip() for r in rows)
    if any_tagged:
        untagged = [r["name"].strip() for r in rows if not r.get("tags", "").strip()]
        if untagged:
            warnings.append(f"{len(untagged)} card(s) have no tags")

    return {"errors": errors, "warnings": warnings}


def assemble_export(id_or_slug: str, skip_scryfall: bool = False) -> Dict[str, Any]:
    """Validate mainboard, assemble exports/import-ready.csv, and append to export-log.json."""
    cube_folder = find_cube_dir(id_or_slug)
    exports_dir = os.path.join(cube_folder, "exports")
    os.makedirs(exports_dir, exist_ok=True)

    working_csv = os.path.join(cube_folder, "mainboard.csv")
    if not os.path.exists(working_csv):
        raise FileNotFoundError(f"mainboard.csv not found in {cube_folder}")

    with open(working_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r.get("name", "").strip()]

    validation = _validate_mainboard(rows)
    errors = validation["errors"]
    warnings = validation["warnings"]

    if errors:
        return {"path": None, "card_count": 0, "errors": errors, "warnings": warnings, "diff": None, "log_path": None}

    # Scryfall validation: cross-check enriched index, verify remainder live
    enriched_index = _load_enriched_index(cube_folder)
    missing_from_scryfall: List[str] = []
    scryfall_network_errors: List[str] = []

    if not skip_scryfall:
        unverified = [
            r["name"].strip() for r in rows
            if not enriched_index.get(r["name"].strip().lower())
        ]
        if unverified:
            sv = _verify_cards_scryfall(unverified)
            missing_from_scryfall = sv["failed"]
            scryfall_network_errors = sv["network_errors"]

        if missing_from_scryfall:
            sample = ", ".join(missing_from_scryfall[:5]) + ("..." if len(missing_from_scryfall) > 5 else "")
            return {
                "path": None, "card_count": 0,
                "errors": [f"{len(missing_from_scryfall)} card(s) not found on Scryfall: {sample}"],
                "warnings": warnings,
                "diff": None, "log_path": None,
            }
        if scryfall_network_errors:
            warnings.append(f"{len(scryfall_network_errors)} card(s) unverified (Scryfall unreachable)")

    diff = cube_status(id_or_slug)

    out_path = os.path.join(exports_dir, "import-ready.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CUBECOBRA_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in CUBECOBRA_CSV_COLUMNS})

    log_path = os.path.join(exports_dir, "export-log.json")
    log_entries: List[Dict[str, Any]] = []
    if os.path.exists(log_path):
        try:
            with open(log_path, encoding="utf-8") as f:
                log_entries = json.load(f)
        except (json.JSONDecodeError, OSError):
            log_entries = []

    export_number = len(log_entries) + 1
    meta_path = os.path.join(cube_folder, "meta.json")
    cube_title = id_or_slug
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                cube_title = json.load(f).get("title", id_or_slug)
        except (json.JSONDecodeError, OSError):
            pass

    enrichment_coverage = _compute_enrichment_coverage(rows, enriched_index)
    rarity_delta = _compute_rarity_delta(cube_folder, diff)

    log_entries.insert(0, {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "export_number": export_number,
        "cube_title": cube_title,
        "card_count": len(rows),
        "added": diff["added"],
        "removed": diff["removed"],
        "tag_changes": len(diff["tag_changed"]),
        "enrichment_coverage": enrichment_coverage,
        "missing_from_scryfall": missing_from_scryfall,
        "validation_summary": {"errors": len(errors), "warnings": len(warnings)},
        "rarity_delta": rarity_delta,
        "warnings": warnings,
    })
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entries, f, indent=2, ensure_ascii=False)

    primer_src = os.path.join(cube_folder, "primer.md")
    primer_export_path: Optional[str] = None
    if os.path.exists(primer_src):
        primer_dst = os.path.join(exports_dir, "primer.md")
        shutil.copy2(primer_src, primer_dst)
        primer_export_path = primer_dst

    return {
        "path": out_path,
        "card_count": len(rows),
        "errors": errors,
        "warnings": warnings,
        "diff": diff,
        "log_path": log_path,
        "primer_path": primer_export_path,
    }


# ── swap-card ──────────────────────────────────────────────────────────────────

# ── add-package ────────────────────────────────────────────────────────────────

def _package_card_to_csv_row(card: Dict[str, Any]) -> Dict[str, str]:
    """Map a CubeCobra package card (Scryfall schema) to a CSV row."""
    ci = card.get("color_identity") or []
    if isinstance(ci, str):
        ci = list(ci)
    colors = card.get("colors") or ci
    if isinstance(colors, str):
        colors = list(colors)
    try:
        cmc_int = str(int(float(card.get("cmc") or 0)))
    except (TypeError, ValueError):
        cmc_int = ""
    type_line = card.get("type_line") or card.get("type") or ""
    image_url = card.get("image_normal") or (card.get("image_uris") or {}).get("normal") or ""
    color_cat = card.get("color_category") or card.get("colorCategory") or ""
    if not color_cat:
        if len(ci) == 0:
            color_cat = "C"
        elif len(ci) > 1:
            color_cat = "M"
        else:
            color_cat = ci[0] if ci else ""
    return {
        "name": card.get("name") or "",
        "CMC": cmc_int,
        "Type": type_line,
        "Color": "".join(colors),
        "Set": (card.get("set") or "").upper(),
        "Collector Number": card.get("collector_number") or "",
        "Rarity": (card.get("rarity") or "").capitalize(),
        "Color Category": color_cat,
        "status": card.get("status") or "",
        "Finish": card.get("finish") or "Non-Foil",
        "board": "mainboard",
        "maybeboard": "false",
        "image URL": image_url,
        "image Back URL": "",
        "tags": ";".join(str(t) for t in (card.get("tags") or []) if t),
        "Notes": card.get("notes") or "",
        "MTGO ID": "",
        "Custom": "false",
        "Voucher": "false",
    }


def _package_card_to_enriched_card(card: Dict[str, Any]) -> Card:
    """Convert a CubeCobra package card (Scryfall schema) to a Card dataclass."""
    ci = card.get("color_identity") or []
    if isinstance(ci, str):
        ci = list(ci)
    colors = card.get("colors") or list(ci)
    if isinstance(colors, str):
        colors = list(colors)
    try:
        cmc = float(card.get("cmc") or 0)
    except (TypeError, ValueError):
        cmc = 0.0
    type_line = card.get("type_line") or card.get("type") or ""
    image_url = card.get("image_normal") or (card.get("image_uris") or {}).get("normal") or ""
    color_cat = card.get("color_category") or card.get("colorCategory") or ""
    if not color_cat:
        if len(ci) == 0:
            color_cat = "C"
        elif len(ci) > 1:
            color_cat = "M"
        else:
            color_cat = ci[0] if ci else ""
    scryfall_id = card.get("scryfall_id") or card.get("_id") or card.get("id") or ""
    return Card(
        name=card.get("name") or "",
        scryfall_id=scryfall_id,
        cmc=cmc,
        type_line=type_line,
        color_identity=ci,
        oracle_text=card.get("oracle_text") or "",
        rarity=(card.get("rarity") or "").lower(),
        set_code=(card.get("set") or "").lower(),
        collector_number=card.get("collector_number") or "",
        color_category=color_cat,
        board="mainboard",
        finish=card.get("finish") or "Non-Foil",
        status=card.get("status") or "",
        image_url=image_url,
        colors=colors,
        power=card.get("power"),
        toughness=card.get("toughness"),
        mana_cost=card.get("mana_cost"),
        tags=[str(t) for t in (card.get("tags") or []) if t],
    )


def add_cards_from_package(
    id_or_slug: str,
    package_cards: List[Dict[str, Any]],
    allow_duplicates: bool = False,
) -> Dict[str, Any]:
    """Add cards from a CubeCobra package to mainboard.csv and upsert into enriched.json.

    Returns {"added": [...], "skipped_existing": [...], "enriched_count": int}.
    """
    cube_folder = find_cube_dir(id_or_slug)
    csv_path = os.path.join(cube_folder, "mainboard.csv")

    existing_rows: List[Dict] = []
    fieldnames = list(CUBECOBRA_CSV_COLUMNS)

    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or CUBECOBRA_CSV_COLUMNS)
            existing_rows = list(reader)

    existing_names_lower = {r.get("name", "").strip().lower() for r in existing_rows if r.get("name")}

    added: List[str] = []
    skipped_existing: List[str] = []
    new_rows: List[Dict] = []
    enriched_cards_to_add: List[Card] = []

    for pkg_card in package_cards:
        name = (pkg_card.get("name") or "").strip()
        if not name:
            continue
        name_lower = name.lower()
        if not allow_duplicates and name_lower in existing_names_lower:
            skipped_existing.append(name)
            continue
        new_rows.append(_package_card_to_csv_row(pkg_card))
        enriched_cards_to_add.append(_package_card_to_enriched_card(pkg_card))
        added.append(name)
        existing_names_lower.add(name_lower)

    if new_rows:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(existing_rows + new_rows)

    # Upsert into enriched.json
    enriched_count = 0
    if enriched_cards_to_add:
        enriched_path = os.path.join(cube_folder, "enriched.json")
        if os.path.exists(enriched_path):
            try:
                enriched_cube = load_enriched(id_or_slug)
            except (FileNotFoundError, Exception):
                meta = load_meta(id_or_slug)
                _id = meta.get("id") or meta.get("short_id") or id_or_slug
                enriched_cube = Cube(
                    short_id=_id,
                    cube_id=_id,
                    title=meta.get("title", id_or_slug),
                    fetched_at=meta.get("fetched_at", ""),
                    cards=[],
                )
        else:
            meta = load_meta(id_or_slug)
            _id = meta.get("id") or meta.get("short_id") or id_or_slug
            enriched_cube = Cube(
                short_id=_id,
                cube_id=_id,
                title=meta.get("title", id_or_slug),
                fetched_at=meta.get("fetched_at", ""),
                cards=[],
            )

        existing_enriched = {c.name.strip().lower(): i for i, c in enumerate(enriched_cube.cards)}
        for card in enriched_cards_to_add:
            key = card.name.strip().lower()
            if key in existing_enriched:
                enriched_cube.cards[existing_enriched[key]] = card
            else:
                enriched_cube.cards.append(card)
                existing_enriched[key] = len(enriched_cube.cards) - 1
            enriched_count += 1

        save_enriched(enriched_cube, id_or_slug)

    return {
        "added": added,
        "skipped_existing": skipped_existing,
        "enriched_count": enriched_count,
    }


def swap_card(
    id_or_slug: str,
    old_name: str,
    new_name: str,
    board: str = "mainboard",
) -> Dict[str, Any]:
    """Atomically replace old_name with new_name. Verifies new card via Scryfall first.

    Returns a result dict with keys: "removed", "added", "correction" (or "error").
    No mutation occurs if verification fails or old card is not found.
    """
    try:
        card = fuzzy_lookup(new_name)
    except ScryfallNetworkError as exc:
        return {"error": f"Scryfall unreachable: {exc}", "network_error": True}

    if card is None:
        return {"error": f"'{new_name}' not found on Scryfall", "new_not_found": True}

    canonical = card["name"]
    correction = canonical if canonical.lower() != new_name.strip().lower() else None

    remove_result = remove_cards(id_or_slug, [old_name], board=board, count=1)
    if remove_result["not_found"]:
        return {"error": f"'{old_name}' not found in {board}", "old_not_found": True}

    add_cards(id_or_slug, [canonical], board=board, verify=False)

    return {
        "removed": old_name,
        "added": canonical,
        "correction": correction,
    }


# ── scale-cards ────────────────────────────────────────────────────────────────

def scale_cards(
    id_or_slug: str,
    names: List[str],
    factor: int,
    operation: str,
    board: str = "mainboard",
) -> Dict[str, Any]:
    """Scale card copy counts by multiplying or dividing existing counts.

    operation: "multiply" or "divide"
    Returns {scaled: [{name, before, after}], not_found: [...], zero_removals: [{name, before}]}.
    zero_removals are cards that were scaled to 0 and fully removed.
    """
    cube_folder = find_cube_dir(id_or_slug)
    csv_filename = "mainboard.csv" if board == "mainboard" else "maybeboard.csv"
    csv_path = os.path.join(cube_folder, csv_filename)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"{csv_filename} not found in {cube_folder}")

    copy_counts: Dict[str, int] = {}
    canonical_names: Dict[str, str] = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip()
            if name:
                key = name.lower()
                copy_counts[key] = copy_counts.get(key, 0) + 1
                canonical_names[key] = name

    scaled = []
    not_found = []
    zero_removals = []

    for raw_name in names:
        key = raw_name.strip().lower()
        if key not in copy_counts:
            not_found.append(raw_name.strip())
            continue

        current = copy_counts[key]
        card_name = canonical_names[key]

        if operation == "multiply":
            new_count = current * factor
            delta = new_count - current
            if delta > 0:
                add_cards(id_or_slug, [card_name] * delta, board=board, verify=False)
            elif delta < 0:
                remove_cards(id_or_slug, [card_name], board=board, count=abs(delta))
        else:
            new_count = math.floor(current / factor)
            delta = current - new_count
            if new_count == 0:
                zero_removals.append({"name": card_name, "before": current})
            if delta > 0:
                remove_cards(id_or_slug, [card_name], board=board, count=delta)

        scaled.append({"name": card_name, "before": current, "after": new_count})

    return {"scaled": scaled, "not_found": not_found, "zero_removals": zero_removals}

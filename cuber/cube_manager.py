"""Cube project lifecycle — fetch/disassemble, add-card, status, export."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .cube import CUBES_DIR, CUBECOBRA_CSV_COLUMNS, Cube, find_cube_dir
from .cubecobra import _fetch_url


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
        "short_id": short_id,
        "slug": slug,
        "format": cube_json.get("type", ""),
        "owner": cube_json.get("owner", ""),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
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
        "short_id": short_id,
        "slug": slug,
        "format": "",
        "owner": "",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
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
) -> Dict[str, Any]:
    """Add one or more cards as stub rows to mainboard.csv or maybeboard.csv.

    Always appends exactly the names given — no deduplication against existing rows.
    Pass the same name multiple times to add multiple copies.
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

    for raw_name in names:
        name = " ".join(raw_name.strip().split())
        if not name:
            continue
        existing_rows.append({**stub_base, "name": name})
        added.append(name)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing_rows)

    return {"added": added}


# ── remove-card ────────────────────────────────────────────────────────────────

def remove_cards(
    id_or_slug: str,
    names: List[str],
    board: str = "mainboard",
    count: Optional[int] = None,
) -> Dict[str, Any]:
    """Remove cards from mainboard.csv or maybeboard.csv.

    By default removes ALL copies of each named card. Pass count to remove
    only that many copies (useful for constructed cubes with intentional multiples).
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


# ── export ─────────────────────────────────────────────────────────────────────

def _validate_mainboard(rows: List[Dict[str, str]]) -> Dict[str, List[str]]:
    """Run pre-flight checks on mainboard rows. Returns errors and warnings."""
    errors: List[str] = []
    warnings: List[str] = []

    # Duplicate check
    name_counts: Dict[str, int] = {}
    for row in rows:
        n = row.get("name", "").strip()
        name_counts[n] = name_counts.get(n, 0) + 1
    duplicates = [n for n, c in name_counts.items() if c > 1]
    if duplicates:
        sample = ", ".join(duplicates[:5]) + ("..." if len(duplicates) > 5 else "")
        errors.append(f"{len(duplicates)} duplicate card(s): {sample}")

    # Unenriched stub check — no CMC, Type, or Set means enrich hasn't run
    stubs = [
        r["name"].strip() for r in rows
        if not r.get("CMC", "").strip()
        and not r.get("Type", "").strip()
        and not r.get("Set", "").strip()
    ]
    if stubs:
        sample = ", ".join(stubs[:5]) + ("..." if len(stubs) > 5 else "")
        errors.append(f"{len(stubs)} unenriched card(s) — run `cuber enrich` first: {sample}")

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


def assemble_export(id_or_slug: str) -> Dict[str, Any]:
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

    log_entries.insert(0, {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "card_count": len(rows),
        "added": diff["added"],
        "removed": diff["removed"],
        "tag_changes": len(diff["tag_changed"]),
        "warnings": warnings,
    })
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entries, f, indent=2, ensure_ascii=False)

    return {
        "path": out_path,
        "card_count": len(rows),
        "errors": errors,
        "warnings": warnings,
        "diff": diff,
        "log_path": log_path,
    }

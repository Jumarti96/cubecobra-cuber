"""CubeCobra fetch client — public read endpoints, no auth required."""

from __future__ import annotations

import csv as csv_module
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from .cube import (
    BASIC_LAND_NAMES,
    CUBES_DIR,
    CUBECOBRA_CSV_COLUMNS,
    ensure_cube_dir,
    save_meta,
)

BASE_URL = "https://cubecobra.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CubeCobraClient/1.0)"}


def _fetch_url(url: str) -> Optional[str]:
    """GET url; return text on 200, None on 404, raise on other errors.
    Falls back to curl subprocess on 403."""
    try:
        r = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=30)
    except httpx.RequestError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e

    if r.status_code == 200:
        return r.text
    if r.status_code == 404:
        return None
    if r.status_code == 403:
        return _fetch_url_curl(url)
    raise RuntimeError(f"Unexpected HTTP {r.status_code} from {url}")


def _fetch_url_curl(url: str) -> Optional[str]:
    """Fallback: use system curl with browser-like UA."""
    result = subprocess.run(
        ["curl", "-s", "-L", "-A", HEADERS["User-Agent"], url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"CubeCobra returned 403 and curl fallback failed.\n"
            f"The cube may be private, or the URL may have changed.\n"
            f"URL attempted: {url}"
        )
    return result.stdout or None


def fetch_cube(short_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """Download a public cube from CubeCobra. Returns meta dict."""
    csv_url = f"{BASE_URL}/cube/download/csv/{short_id}"

    if dry_run:
        print(f"[dry-run] Would fetch: {csv_url}")
        return {}

    print(f"Fetching cube '{short_id}' from CubeCobra...")
    content = _fetch_url(csv_url)

    if content is None:
        raise RuntimeError(
            f"Cube '{short_id}' not found on CubeCobra. "
            "Check the short ID and ensure the cube is public."
        )

    ensure_cube_dir(short_id)
    raw_path = os.path.join(CUBES_DIR, short_id, "raw.csv")
    with open(raw_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    # Extract title from CSV header if possible; fall back to short_id
    title = _extract_title(content, short_id)
    card_count = max(0, content.count("\n") - 1)  # rough count (minus header)

    meta: Dict[str, Any] = {
        "short_id": short_id,
        "cube_id": short_id,  # updated to UUID if available
        "title": title,
        "url": csv_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "card_count": card_count,
        "missing_cards": [],
        "schema_warning": False,
    }
    save_meta(meta, short_id)
    print(f"  Saved {raw_path} ({card_count} cards)")
    return meta


def _extract_title(csv_content: str, fallback: str) -> str:
    """Best-effort title extraction from CSV content or fallback to short_id."""
    lines = csv_content.strip().splitlines()
    if lines:
        first = lines[0].lower()
        if "name" in first:
            return fallback  # header line present, no title in file
    return fallback


def fetch_set(
    set_code: str,
    exclude_basics: bool = True,
    exclude_tokens: bool = True,
) -> Dict[str, Any]:
    """Fetch all cards from a retail MTG set via Scryfall and save as a v2 cube project."""
    set_code = set_code.lower().strip()
    print(f"Fetching set '{set_code}' from Scryfall...")

    cards = _scryfall_set_search(set_code, exclude_basics, exclude_tokens)
    if not cards:
        raise RuntimeError(
            f"No cards found for set code '{set_code}'. "
            "Check the code at https://scryfall.com/sets"
        )

    rows = [_scryfall_to_csv_row(card) for card in cards]

    # Build v2 folder structure (same layout as fetch_and_disassemble)
    cube_folder = os.path.join(CUBES_DIR, set_code)
    remote_dir = os.path.join(cube_folder, "remote")
    os.makedirs(remote_dir, exist_ok=True)
    os.makedirs(os.path.join(cube_folder, "exports"), exist_ok=True)
    os.makedirs(os.path.join(cube_folder, "decks"), exist_ok=True)

    # remote/mainboard.csv — pristine snapshot
    remote_csv = os.path.join(remote_dir, "mainboard.csv")
    with open(remote_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv_module.DictWriter(f, fieldnames=CUBECOBRA_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  remote/mainboard.csv ({len(cards)} cards)")

    # mainboard.csv — working copy; merge on re-fetch to preserve local edits
    working_csv = os.path.join(cube_folder, "mainboard.csv")
    if not os.path.exists(working_csv):
        shutil.copy2(remote_csv, working_csv)
        print(f"  mainboard.csv (working copy created)")
    else:
        with open(working_csv, encoding="utf-8") as f:
            reader = csv_module.DictReader(f)
            fieldnames = list(reader.fieldnames or CUBECOBRA_CSV_COLUMNS)
            working_rows = list(reader)
        working_lower = {r.get("name", "").strip().lower() for r in working_rows}
        added = []
        for row in rows:
            name_lower = row.get("name", "").strip().lower()
            if name_lower and name_lower not in working_lower:
                working_rows.append(row)
                working_lower.add(name_lower)
                added.append(row.get("name", ""))
        if added:
            print(f"  Merge: added {len(added)} new card(s) from set")
        with open(working_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv_module.DictWriter(
                f, fieldnames=fieldnames, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(working_rows)

    # primer.md — only create, never overwrite
    title = f"{set_code.upper()} Set Cube"
    primer_path = os.path.join(cube_folder, "primer.md")
    if not os.path.exists(primer_path):
        with open(primer_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\nFetched from Scryfall set `{set_code}`.\n")

    meta: Dict[str, Any] = {
        "title": title,
        "short_id": set_code,
        "slug": set_code,
        "format": "",
        "owner": "",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "card_count": len(cards),
        "missing_cards": [],
        "schema_warning": None,
        "source": f"scryfall-set:{set_code}",
    }
    save_meta(meta, set_code)

    print(f"\nCube project: cubes/{set_code}/")
    return meta


def _scryfall_set_search(
    set_code: str,
    exclude_basics: bool,
    exclude_tokens: bool,
) -> list:
    """Paginate through all cards in a Scryfall set search."""
    query = f"set:{set_code}"
    if exclude_basics:
        query += " -type:basic"
    if exclude_tokens:
        query += " -type:token"

    url = f"https://api.scryfall.com/cards/search?q={query}&unique=cards&order=name"
    cards = []

    while url:
        time.sleep(0.1)  # respect rate limit
        r = httpx.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 404:
            break
        r.raise_for_status()
        data = r.json()
        cards.extend(data.get("data", []))
        url = data.get("next_page")

    return cards


def _scryfall_to_csv_row(card: Dict[str, Any]) -> Dict[str, str]:
    """Map a Scryfall card object to a CubeCobra CSV row."""
    color_identity = "".join(card.get("color_identity", []))
    type_line = card.get("type_line", "")
    # For DFCs, use front face data
    if "card_faces" in card and card["card_faces"]:
        face = card["card_faces"][0]
        type_line = face.get("type_line", type_line)

    return {
        "name": card.get("name", ""),
        "CMC": str(int(card.get("cmc", 0))),
        "Type": type_line,
        "Color": color_identity,
        "Set": card.get("set", "").upper(),
        "Collector Number": card.get("collector_number", ""),
        "Rarity": card.get("rarity", "").capitalize(),
        "Color Category": _color_category(card),
        "status": "",
        "Finish": "Non-Foil",
        "board": "mainboard",
        "maybeboard": "false",
        "image URL": card.get("image_uris", {}).get("normal", ""),
        "image Back URL": "",
        "tags": "",
        "Notes": "",
        "MTGO ID": str(card.get("mtgo_id", "")),
        "Custom": "false",
        "Voucher": "false",
    }


def _color_category(card: Dict[str, Any]) -> str:
    ci = card.get("color_identity", [])
    if len(ci) == 0:
        return "C"
    if len(ci) > 1:
        return "M"
    return ci[0]

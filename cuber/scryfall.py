"""Scryfall API client with SQLite lazy cache."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .cube import (
    CUBES_DIR,
    CUBECOBRA_CSV_COLUMNS,
    Card,
    CardFace,
    Cube,
    load_enriched,
    load_meta,
    load_raw_csv,
    save_enriched,
    save_meta,
)

SCRYFALL_BASE = "https://api.scryfall.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CubeCobraClient/1.0)"}
CACHE_DB = os.path.join(CUBES_DIR, ".cache", "scryfall.db")
CACHE_TTL_DAYS = 7
BATCH_SIZE = 75
RATE_DELAY = 0.11  # slightly over 100ms for safety

DFC_LAYOUTS = {"transform", "modal_dfc", "reversible_card"}


# ── Cache ─────────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(CACHE_DB), exist_ok=True)
    conn = sqlite3.connect(CACHE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            name_normalized TEXT PRIMARY KEY,
            data            TEXT NOT NULL,
            cached_at       TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _normalize(name: str) -> str:
    return name.strip().lower()


def _cache_get(conn: sqlite3.Connection, name: str, refresh: bool) -> Optional[Dict]:
    row = conn.execute(
        "SELECT data, cached_at FROM cards WHERE name_normalized = ?",
        (_normalize(name),),
    ).fetchone()
    if row is None:
        return None
    if refresh:
        return None
    cached_at = datetime.fromisoformat(row[1])
    if datetime.now(timezone.utc) - cached_at > timedelta(days=CACHE_TTL_DAYS):
        return None
    return json.loads(row[0])


def _cache_set(conn: sqlite3.Connection, name: str, data: Dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO cards (name_normalized, data, cached_at) VALUES (?, ?, ?)",
        (_normalize(name), json.dumps(data), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# ── API fetch ─────────────────────────────────────────────────────────────────

def _fuzzy_lookup(name: str, conn: sqlite3.Connection) -> Optional[Dict]:
    """Fallback: look up a card by fuzzy name (handles DFCs and split cards)."""
    time.sleep(RATE_DELAY)
    try:
        r = httpx.get(
            f"{SCRYFALL_BASE}/cards/named",
            params={"fuzzy": name},
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            card = r.json()
            # Cache under both the queried name and the canonical Scryfall name
            _cache_set(conn, name, card)
            _cache_set(conn, card["name"], card)
            return card
    except Exception:
        pass
    return None


def lookup_cards(names: List[str], refresh: bool = False) -> Tuple[List[Dict], List[str]]:
    """Batch-lookup cards by name. Returns (found_cards, missing_names)."""
    conn = _get_conn()
    results: List[Dict] = []
    to_fetch: List[str] = []
    missing: List[str] = []

    # Serve from cache first
    for name in names:
        cached = _cache_get(conn, name, refresh)
        if cached is not None:
            results.append(cached)
        else:
            to_fetch.append(name)

    # Batch-fetch uncached cards
    batch_missing: List[str] = []
    for i in range(0, len(to_fetch), BATCH_SIZE):
        batch = to_fetch[i : i + BATCH_SIZE]
        identifiers = [{"name": n} for n in batch]
        time.sleep(RATE_DELAY)
        try:
            r = httpx.post(
                f"{SCRYFALL_BASE}/cards/collection",
                json={"identifiers": identifiers},
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Scryfall API error: {e}") from e

        found_names = set()
        for card in data.get("data", []):
            _cache_set(conn, card["name"], card)
            results.append(card)
            found_names.add(card["name"].strip().lower())

        # Cards not found — try fuzzy fallback (handles DFCs, split cards)
        for nf in data.get("not_found", []):
            nf_name = nf.get("name", str(nf))
            card = _fuzzy_lookup(nf_name, conn)
            if card:
                results.append(card)
                # Also cache under the original queried name
                _cache_set(conn, nf_name, card)
            else:
                batch_missing.append(nf_name)

    conn.close()
    return results, batch_missing


# ── Enrichment ────────────────────────────────────────────────────────────────

def _scryfall_to_card(row: Dict[str, str], sf: Dict[str, Any]) -> Card:
    """Merge a CubeCobra CSV row with Scryfall data into a Card."""
    layout = sf.get("layout", "")
    card_faces = None

    if layout in DFC_LAYOUTS and "card_faces" in sf:
        card_faces = [
            CardFace(
                name=f.get("name", ""),
                oracle_text=f.get("oracle_text", ""),
                mana_cost=f.get("mana_cost", ""),
                type_line=f.get("type_line", ""),
                power=f.get("power"),
                toughness=f.get("toughness"),
            )
            for f in sf["card_faces"]
        ]
        oracle_text = "\n//\n".join(
            f.get("oracle_text", "") for f in sf["card_faces"]
        )
        type_line = sf["card_faces"][0].get("type_line", sf.get("type_line", ""))
        image_back = (
            sf["card_faces"][1].get("image_uris", {}).get("normal", "")
            if len(sf["card_faces"]) > 1
            else ""
        )
    else:
        oracle_text = sf.get("oracle_text", "")
        type_line = sf.get("type_line", "")
        image_back = row.get("image Back URL", "")

    # Existing tags from the CSV row (may have been manually set)
    raw_tags = row.get("tags", "")
    existing_tags = [t.strip() for t in raw_tags.split(";") if t.strip()]

    return Card(
        name=sf.get("name", row.get("name", "")),
        scryfall_id=sf.get("id", ""),
        cmc=float(sf.get("cmc", 0)),
        type_line=type_line,
        colors=sf.get("colors", []),
        color_identity=sf.get("color_identity", []),
        oracle_text=oracle_text,
        rarity=sf.get("rarity", row.get("Rarity", "").lower()),
        set_code=sf.get("set", row.get("Set", "").lower()),
        collector_number=sf.get("collector_number", row.get("Collector Number", "")),
        color_category=row.get("Color Category", ""),
        board=row.get("board", "mainboard"),
        finish=row.get("Finish", "Non-Foil"),
        status=row.get("status", ""),
        image_url=sf.get("image_uris", {}).get("normal", row.get("image URL", "")),
        power=sf.get("power"),
        toughness=sf.get("toughness"),
        mana_cost=sf.get("mana_cost"),
        layout=layout or None,
        image_back_url=image_back or None,
        tags=existing_tags,
        notes=row.get("Notes") or None,
        mtgo_id=str(sf.get("mtgo_id", row.get("MTGO ID", ""))) or None,
        card_faces=card_faces,
    )


def _backfill_mainboard_csv(cube_folder: str, cards: List[Card]) -> int:
    """Write Scryfall-derived fields back into mainboard.csv, preserving user-controlled columns."""
    csv_path = os.path.join(cube_folder, "mainboard.csv")
    if not os.path.exists(csv_path):
        return 0

    card_by_name: Dict[str, Card] = {}
    for c in cards:
        card_by_name[c.name.strip().lower()] = c
        if " // " in c.name:
            front = c.name.split(" // ")[0].strip().lower()
            if front not in card_by_name:
                card_by_name[front] = c

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or CUBECOBRA_CSV_COLUMNS)
        rows = list(reader)

    updated = 0
    for row in rows:
        name = row.get("name", "").strip()
        card = card_by_name.get(name.lower())
        if card is None:
            continue
        cmc_val = card.cmc
        try:
            cmc_str = str(int(cmc_val)) if cmc_val == int(cmc_val) else str(cmc_val)
        except (ValueError, OverflowError):
            cmc_str = str(cmc_val)
        row["CMC"] = cmc_str
        row["Type"] = card.type_line
        row["Color"] = "".join(card.colors)
        row["Set"] = card.set_code.upper()
        row["Collector Number"] = card.collector_number
        row["Rarity"] = card.rarity.capitalize()
        row["image URL"] = card.image_url or ""
        row["image Back URL"] = card.image_back_url or ""
        updated += 1

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return updated


def enrich_cube(short_id: str, refresh: bool = False) -> Cube:
    """Load mainboard.csv, enrich all cards via Scryfall, write enriched.json."""
    rows = load_raw_csv(short_id)
    meta = load_meta(short_id)

    # Detect new cards not yet in enriched.json (stubs from add-card)
    stub_count = 0
    try:
        existing = load_enriched(short_id)
        existing_lower = {c.name.strip().lower() for c in existing.cards}
        stub_count = sum(
            1 for r in rows
            if r.get("name", "").strip()
            and r["name"].strip().lower() not in existing_lower
        )
    except FileNotFoundError:
        pass

    names = [r["name"] for r in rows if r.get("name")]
    print(f"Enriching {len(names)} cards via Scryfall (cache: {'bypass' if refresh else 'enabled'})...")
    if stub_count:
        print(f"  Hydrating {stub_count} new card(s) added via add-card...")

    sf_cards, missing = lookup_cards(names, refresh=refresh)

    # Build a lookup by normalized name; also index DFCs by front-face name
    sf_by_name: Dict[str, Dict] = {}
    for sf in sf_cards:
        sf_by_name[sf["name"].strip().lower()] = sf
        # DFCs: also index by front face name so "Delver of Secrets" finds
        # "Delver of Secrets // Insectile Aberration"
        if "card_faces" in sf and sf["card_faces"]:
            front = sf["card_faces"][0].get("name", "").strip().lower()
            if front and front not in sf_by_name:
                sf_by_name[front] = sf

    cards: List[Card] = []
    validation_warnings: List[str] = []

    for row in rows:
        name = row.get("name", "").strip()
        if not name:
            continue
        sf = sf_by_name.get(name.lower())
        if sf is None:
            validation_warnings.append(f"Not found on Scryfall: {name}")
            continue
        try:
            card = _scryfall_to_card(row, sf)
            # Validate required fields
            if not card.name or not card.scryfall_id or not card.type_line:
                validation_warnings.append(f"Validation failed (missing fields): {name}")
                continue
            cards.append(card)
        except Exception as e:
            validation_warnings.append(f"Error enriching {name}: {e}")

    cube = Cube(
        short_id=short_id,
        cube_id=meta.get("id") or meta.get("cube_id") or short_id,
        title=meta.get("title", short_id),
        fetched_at=meta.get("fetched_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
        cards=cards,
    )

    path = save_enriched(cube, short_id)
    updated = _backfill_mainboard_csv(os.path.dirname(path), cards)

    # Update meta
    meta["card_count"] = len(cards)
    meta["missing_cards"] = missing + [
        w.replace("Not found on Scryfall: ", "")
        for w in validation_warnings
        if w.startswith("Not found")
    ]
    meta["validation_warnings"] = validation_warnings
    save_meta(meta, short_id)

    print(f"  Enriched {len(cards)} cards -> {path}")
    print(f"  Updated {updated} rows in mainboard.csv")
    if missing:
        print(f"  Missing ({len(missing)}): {', '.join(missing[:5])}"
              + ("..." if len(missing) > 5 else ""))
    if validation_warnings:
        print(f"  Warnings: {len(validation_warnings)} cards had issues")

    return cube

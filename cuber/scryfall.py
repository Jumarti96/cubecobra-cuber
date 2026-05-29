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

DFC_LAYOUTS = {"transform", "modal_dfc", "reversible_card"}  # layouts with a distinct back-face image
MULTIFACE_LAYOUTS = DFC_LAYOUTS | {"split", "aftermath", "adventure", "flip"}


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


def _identifier_cache_key(ident: Dict) -> str:
    """Compute the SQLite cache key for a Scryfall identifier dict."""
    if "collector_number" in ident and "set" in ident:
        return f"{ident['set'].lower()}:{ident['collector_number']}"
    return _normalize(ident.get("name", ""))


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

class ScryfallNetworkError(Exception):
    """Raised when Scryfall is unreachable due to a network or timeout error."""
    pass


def fuzzy_lookup(name: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict]:
    """Look up a card by fuzzy name. Returns the card dict or None (not found).

    When called without conn (external use): checks cache first and raises
    ScryfallNetworkError on network/timeout failure.
    When conn is passed (internal use): skips cache pre-check and swallows
    exceptions, returning None on any failure.
    """
    manage_conn = conn is None
    if manage_conn:
        conn = _get_conn()
    try:
        if manage_conn:
            cached = _cache_get(conn, name, False)
            if cached is not None:
                return cached
        time.sleep(RATE_DELAY)
        try:
            r = httpx.get(
                f"{SCRYFALL_BASE}/cards/named",
                params={"fuzzy": name},
                headers=HEADERS,
                timeout=15,
            )
        except (httpx.NetworkError, httpx.TimeoutException, OSError) as exc:
            if manage_conn:
                raise ScryfallNetworkError(str(exc)) from exc
            return None
        if r.status_code == 200:
            card = r.json()
            _cache_set(conn, name, card)
            _cache_set(conn, card["name"], card)
            return card
        return None
    except ScryfallNetworkError:
        raise
    except Exception:
        return None
    finally:
        if manage_conn:
            conn.close()


def lookup_cards(identifiers: List[Dict], refresh: bool = False) -> Tuple[List[Dict], List[str]]:
    """Batch-lookup cards by Scryfall identifier dicts. Returns (found_cards, missing_names).

    Each identifier is one of:
      {"name": "Lightning Bolt"}
      {"name": "Lightning Bolt", "set": "m11"}
      {"set": "mh3", "collector_number": "42", "_name": "Grief"}  <- _name stripped before POST
    """
    conn = _get_conn()
    results: List[Dict] = []
    to_fetch: List[Dict] = []
    key_to_name: Dict[str, str] = {}
    missing: List[str] = []

    for ident in identifiers:
        name = ident.get("_name") or ident.get("name", "")
        cache_key = _identifier_cache_key(ident)
        if name:
            key_to_name[cache_key] = name

        cached = _cache_get(conn, cache_key, refresh)
        if cached is not None:
            results.append(cached)
        else:
            scryfall_ident = {k: v for k, v in ident.items() if not k.startswith("_")}
            to_fetch.append(scryfall_ident)

    for i in range(0, len(to_fetch), BATCH_SIZE):
        batch = to_fetch[i : i + BATCH_SIZE]
        time.sleep(RATE_DELAY)
        try:
            r = httpx.post(
                f"{SCRYFALL_BASE}/cards/collection",
                json={"identifiers": batch},
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Scryfall API error: {e}") from e

        for card in data.get("data", []):
            _cache_set(conn, card["name"], card)
            # Also cache under set:cn key so subsequent set-pinned lookups hit cache
            if card.get("set") and card.get("collector_number"):
                _cache_set(conn, f"{card['set'].lower()}:{card['collector_number']}", card)
            results.append(card)

        for nf in data.get("not_found", []):
            nf_key = _identifier_cache_key(nf)
            nf_name = key_to_name.get(nf_key) or nf.get("name", "")
            if "collector_number" in nf and "set" in nf and nf_name:
                print(f"  Warning: pinned printing {nf.get('set', '').upper()} "
                      f"#{nf.get('collector_number')} unavailable; "
                      f"falling back to name lookup for '{nf_name}'")
            card = fuzzy_lookup(nf_name, conn) if nf_name else None
            if card:
                results.append(card)
                if nf_name:
                    _cache_set(conn, nf_name, card)
            else:
                missing.append(nf_name or str(nf))

    conn.close()
    return results, missing


# ── Enrichment ────────────────────────────────────────────────────────────────

def _build_identifier(row: Dict[str, str]) -> Dict[str, str]:
    """Build a Scryfall identifier from a mainboard.csv row (three-tier logic).

    Tier 1: set + collector_number -> exact printing pin
    Tier 2: set only             -> name + set for set-scoped lookup
    Tier 3: neither              -> name only (Scryfall canonical)
    """
    name = row.get("name", "").strip()
    set_code = (row.get("Set") or "").strip()
    cn = (row.get("Collector Number") or "").strip()

    if set_code and cn:
        return {"set": set_code.lower(), "collector_number": cn, "_name": name}
    if set_code:
        return {"name": name, "set": set_code.lower()}
    return {"name": name}


def _load_enriched_dict(short_id: str) -> Dict[str, Card]:
    """Load enriched.json and return a {name_lower: Card} dict; empty dict if missing."""
    try:
        cube = load_enriched(short_id)
        return {c.name.strip().lower(): c for c in cube.cards}
    except FileNotFoundError:
        return {}


def _is_already_enriched(row: Dict[str, str], existing: Dict[str, Card]) -> bool:
    """Return True if this mainboard row's card is already correctly enriched.

    Checks: scryfall_id present, set matches (if specified), CN matches (if specified).
    """
    name = row.get("name", "").strip()
    if not name:
        return False
    card = existing.get(name.lower())
    if card is None or not card.scryfall_id:
        return False
    set_code = (row.get("Set") or "").strip()
    cn = (row.get("Collector Number") or "").strip()
    if set_code and card.set_code.lower() != set_code.lower():
        return False
    if cn and card.collector_number != cn:
        return False
    return True


def _scryfall_to_card(row: Dict[str, str], sf: Dict[str, Any]) -> Card:
    """Merge a CubeCobra CSV row with Scryfall data into a Card."""
    layout = sf.get("layout", "")
    card_faces = None

    if layout in MULTIFACE_LAYOUTS and "card_faces" in sf:
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
            if layout in DFC_LAYOUTS and len(sf["card_faces"]) > 1
            else row.get("image Back URL", "")
        )
    else:
        oracle_text = sf.get("oracle_text", "")
        type_line = sf.get("type_line", "")
        image_back = row.get("image Back URL", "")

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
        # Preserve user-specified Set; only write from Scryfall if row has none
        if not row.get("Set", "").strip():
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

    mainboard_rows = [r for r in rows if r.get("name", "").strip()]

    # Skip-if-enriched: partition rows into already-correct and needs-fetch
    existing = _load_enriched_dict(short_id)
    if refresh:
        to_fetch_rows = mainboard_rows
        already_enriched_cards: List[Card] = []
    else:
        to_fetch_rows = [r for r in mainboard_rows if not _is_already_enriched(r, existing)]
        already_enriched_names = {
            r["name"].strip().lower()
            for r in mainboard_rows
            if _is_already_enriched(r, existing)
        }
        already_enriched_cards = [existing[n] for n in already_enriched_names if n in existing]

    skip_count = len(mainboard_rows) - len(to_fetch_rows)
    fetch_count = len(to_fetch_rows)

    print(f"Enriching {len(mainboard_rows)} cards via Scryfall (cache: {'bypass' if refresh else 'enabled'})...")
    if skip_count and not refresh:
        print(f"  Skipped {skip_count} (already enriched). Fetching {fetch_count} new/changed cards.")

    identifiers = [_build_identifier(r) for r in to_fetch_rows]
    if identifiers:
        sf_cards, missing = lookup_cards(identifiers, refresh=refresh)
    else:
        sf_cards, missing = [], []

    # Build name lookup for fetched cards; DFCs indexed by front-face name too
    sf_by_name: Dict[str, Dict] = {}
    for sf in sf_cards:
        sf_by_name[sf["name"].strip().lower()] = sf
        if "card_faces" in sf and sf["card_faces"]:
            front = sf["card_faces"][0].get("name", "").strip().lower()
            if front and front not in sf_by_name:
                sf_by_name[front] = sf

    # Start with already-enriched cards, then append newly fetched
    cards: List[Card] = list(already_enriched_cards)
    validation_warnings: List[str] = []

    for row in to_fetch_rows:
        name = row.get("name", "").strip()
        if not name:
            continue
        sf = sf_by_name.get(name.lower())
        if sf is None:
            validation_warnings.append(f"Not found on Scryfall: {name}")
            continue
        try:
            card = _scryfall_to_card(row, sf)
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

    meta["card_count"] = len(cards)
    meta["missing_cards"] = missing + [
        w.replace("Not found on Scryfall: ", "")
        for w in validation_warnings
        if w.startswith("Not found")
    ]
    meta["validation_warnings"] = validation_warnings
    save_meta(meta, short_id)

    newly_fetched = len(cards) - len(already_enriched_cards)
    print(f"  Enriched {len(cards)} cards -> {path}")
    if skip_count and not refresh:
        print(f"  Skipped {skip_count} (already enriched). Fetched {newly_fetched} new/changed cards.")
    print(f"  Updated {updated} rows in mainboard.csv")
    if missing:
        print(f"  Missing ({len(missing)}): {', '.join(missing[:5])}"
              + ("..." if len(missing) > 5 else ""))
    if validation_warnings:
        print(f"  Warnings: {len(validation_warnings)} cards had issues")

    return cube

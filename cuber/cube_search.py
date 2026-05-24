"""Merged card pool loader, multi-criteria search, draft pool support, and copy policy."""

from __future__ import annotations

import csv
import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from .cube import find_cube_dir, load_enriched


# ── Pool loaders ────────────────────────────────────────────────────────────

def load_merged_pool(
    id_or_slug: str,
    card_pool_rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Load enriched.json cards and merge functional tags from tagged.csv.

    tagged.csv tags are merged onto each card's existing tags list (no duplicates).
    Returns a list of card dicts ready for search_pool().

    card_pool_rules (optional) restricts and/or multiplies the pool:
      - excluded: list of card names to remove regardless of rarity
      - only_from: {rarity: [allowed names]} — all other cards of that rarity excluded
      - multipliers: {rarity: N} — each card of that rarity appears N times in the pool
    """
    cube = load_enriched(id_or_slug)
    cube_folder = find_cube_dir(id_or_slug)
    tagged_csv = os.path.join(cube_folder, "tagged.csv")

    tags_by_name: Dict[str, List[str]] = {}
    if os.path.exists(tagged_csv):
        with open(tagged_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                if not name:
                    continue
                raw = row.get("tags") or ""
                csv_tags = [t.strip() for t in raw.split(";") if t.strip()]
                tags_by_name[name] = csv_tags

    pool = []
    for card in cube.cards:
        if card.board != "mainboard":
            continue
        d = card.to_dict()
        merged = list(card.tags)
        for tag in tags_by_name.get(card.name, []):
            if tag not in merged:
                merged.append(tag)
        d["tags"] = merged
        pool.append(d)

    if card_pool_rules:
        pool = _apply_card_pool_rules(pool, card_pool_rules)

    return pool


def _apply_card_pool_rules(
    pool: List[Dict[str, Any]],
    rules: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Apply card_pool_rules filters and multipliers to a pool.

    Processing order: exclusions and only_from narrow the pool first,
    then multipliers expand it.
    """
    excluded: set = set(rules.get("excluded") or [])
    only_from: Dict[str, List[str]] = rules.get("only_from") or {}
    multipliers: Dict[str, int] = rules.get("multipliers") or {}

    result: List[Dict[str, Any]] = []
    for card in pool:
        name = card.get("name", "")
        rarity = (card.get("rarity") or "").lower()

        if name in excluded:
            continue

        if rarity in only_from:
            if name not in set(only_from[rarity]):
                continue

        copies = int(multipliers.get(rarity, 1))
        for _ in range(copies):
            result.append(dict(card))

    return result


def _parse_draft_pool_text(text: str) -> Counter:
    """Parse a multiline draft pool text into {card_name: count}.

    Supports:
      - One card per line
      - Comma-separated list
      - "Nx Card Name" format
    """
    counts: Counter = Counter()
    # Split by newline or comma
    raw_items = re.split(r"[\n,]", text)
    for item in raw_items:
        item = item.strip()
        if not item:
            continue
        # Check for "Nx " prefix
        m = re.match(r"^(\d+)x?\s+(.+)", item, re.IGNORECASE)
        if m:
            qty = int(m.group(1))
            name = m.group(2).strip()
        else:
            qty = 1
            name = item
        counts[name] += qty
    return counts


def load_draft_pool(
    id_or_slug: str,
    draft_text: Optional[str] = None,
    draft_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load a draft pool and return matching cards from the cube.

    Priority:
      1. draft_text (inline pasted text)
      2. draft_path (path to .txt or .csv file)

    Returns only cards present in the draft pool, with a `max_available`
    field set to the quantity drafted.
    """
    full_pool = load_merged_pool(id_or_slug)
    full_index = {c["name"]: c for c in full_pool}

    # Resolve source
    if draft_text:
        pool_counts = _parse_draft_pool_text(draft_text)
    elif draft_path and os.path.exists(draft_path):
        ext = os.path.splitext(draft_path)[1].lower()
        if ext == ".csv":
            pool_counts = _parse_draft_csv(draft_path)
        else:
            with open(draft_path, encoding="utf-8") as f:
                pool_counts = _parse_draft_pool_text(f.read())
    else:
        raise FileNotFoundError(f"Draft pool file not found: {draft_path}")

    result = []
    for name, qty in pool_counts.items():
        card = full_index.get(name)
        if card is None:
            # Try case-insensitive match
            for k, v in full_index.items():
                if k.lower() == name.lower():
                    card = v
                    break
        if card is None:
            continue
        card_copy = dict(card)
        card_copy["max_available"] = qty
        result.append(card_copy)

    return result


def _parse_draft_csv(path: str) -> Counter:
    """Parse a CubeCobra-style CSV with name and quantity columns."""
    counts: Counter = Counter()
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            if not name:
                continue
            qty_str = row.get("quantity") or row.get("qty") or "1"
            try:
                qty = int(qty_str)
            except ValueError:
                qty = 1
            counts[name] += qty
    return counts


# ── Copy policy helper ───────────────────────────────────────────────────────

def get_max_copies(
    card: Dict[str, Any],
    copies_policy: Optional[Dict[str, Any]] = None,
) -> int:
    """Return the maximum number of copies allowed for this card.

    Resolution order:
      1. per_card override
      2. per_rarity override
      3. cube_actual (enriched.json count, or draft pool max_available)
      4. Default fallback = 4
    """
    if copies_policy is None:
        copies_policy = {}

    name = card.get("name", "")
    rarity = (card.get("rarity") or "").lower()

    # 1. per_card override
    per_card = copies_policy.get("per_card", {})
    if name in per_card:
        return per_card[name]

    # 2. per_rarity override
    per_rarity = copies_policy.get("per_rarity", {})
    if rarity in per_rarity:
        return per_rarity[rarity]

    # 3. cube_actual / draft pool
    if "max_available" in card:
        return card["max_available"]

    # 4. Default
    default = copies_policy.get("default", 4)
    return default


# ── Search ───────────────────────────────────────────────────────────────────

def search_pool(
    pool: List[Dict[str, Any]],
    *,
    color_identity: Optional[List[str]] = None,
    splash_color_identity: Optional[List[str]] = None,
    oracle_pattern: Optional[str] = None,
    card_type: Optional[str] = None,
    cmc_min: Optional[float] = None,
    cmc_max: Optional[float] = None,
    tags: Optional[List[str]] = None,
    rarity: Optional[str] = None,
    board: str = "mainboard",
) -> List[Dict[str, Any]]:
    """Filter a merged card pool by any combination of criteria.

    color_identity: cards whose CI is a subset of these colors (e.g. ["W", "U"])
    splash_color_identity: if provided, also include splash-eligible cards.
      A card is splash-eligible if:
        - Its CI contains exactly 1 color not in color_identity
        - It has ≤ 2 pips of the off-color OR CMC ≥ 4 OR has kicker/hybrid
    oracle_pattern: regex applied to oracle_text (case-insensitive)
    card_type: substring match against type_line (e.g. "Creature", "Instant")
    cmc_min/cmc_max: inclusive CMC range filter
    tags: all listed tags must be present (case-insensitive)
    rarity: exact rarity match (common/uncommon/rare/mythic)
    board: "mainboard" or "maybeboard"
    """
    results = []
    for card in pool:
        if card.get("board", "mainboard") != board:
            continue
        if color_identity is not None:
            ci = set(card.get("color_identity") or [])
            core_colors = set(color_identity)
            in_core = ci.issubset(core_colors)
            if not in_core and splash_color_identity is not None:
                # Check splash eligibility
                allowed = set(splash_color_identity)
                all_allowed = core_colors | allowed
                if not ci.issubset(all_allowed):
                    continue
                off_color = ci - core_colors
                if len(off_color) != 1:
                    continue
                # Splash criteria: ≤ 2 off-color pips OR CMC ≥ 4 OR kicker
                cmc = float(card.get("cmc") or 0)
                mana_cost = card.get("mana_cost") or ""
                off_color_letter = next(iter(off_color))
                off_pips = mana_cost.count(f"{{{off_color_letter}}}")
                has_kicker = "kicker" in [t.lower() for t in (card.get("tags") or [])]
                if not (off_pips <= 2 or cmc >= 4 or has_kicker):
                    continue
            elif not in_core:
                continue
        if oracle_pattern is not None:
            oracle = card.get("oracle_text") or ""
            if not re.search(oracle_pattern, oracle, re.IGNORECASE):
                continue
        if card_type is not None:
            type_line = card.get("type_line") or ""
            if card_type.lower() not in type_line.lower():
                continue
        cmc = float(card.get("cmc") or 0)
        if cmc_min is not None and cmc < cmc_min:
            continue
        if cmc_max is not None and cmc > cmc_max:
            continue
        if tags is not None:
            card_tags_lower = [t.lower() for t in (card.get("tags") or [])]
            if not all(t.lower() in card_tags_lower for t in tags):
                continue
        if rarity is not None and (card.get("rarity") or "").lower() != rarity.lower():
            continue
        results.append(card)
    return results


def format_search_results(cards: List[Dict[str, Any]], limit: int = 25) -> str:
    """Return a compact ASCII table: Name | CI | CMC | Rarity | Tags | Oracle excerpt."""
    if not cards:
        return "No cards found."

    shown = cards[:limit]
    name_w = min(max((len(c.get("name") or "") for c in shown), default=4), 32)

    header = (
        f"{'Name':<{name_w}}  {'CI':<6}  {'CMC':<3}  {'Rar':<5}  "
        f"{'Tags':<24}  Oracle excerpt"
    )
    sep = "-" * (name_w + 6 + 3 + 5 + 24 + 64)
    lines = [header, sep]

    for card in shown:
        name = (card.get("name") or "")[:name_w]
        ci = "".join(card.get("color_identity") or []) or "C"
        cmc = str(int(float(card.get("cmc") or 0)))
        rar = (card.get("rarity") or "")[:5].capitalize()
        tags_str = (";".join(card.get("tags") or []))[:24]
        oracle = (card.get("oracle_text") or "").replace("\n", " ")[:60]
        lines.append(
            f"{name:<{name_w}}  {ci:<6}  {cmc:<3}  {rar:<5}  "
            f"{tags_str:<24}  {oracle}"
        )

    if len(cards) > limit:
        lines.append(f"... and {len(cards) - limit} more cards")

    return "\n".join(lines)

"""Merged card pool loader and multi-criteria search."""

from __future__ import annotations

import csv
import os
import re
from typing import Any, Dict, List, Optional

from .cube import find_cube_dir, load_enriched


def load_merged_pool(id_or_slug: str) -> List[Dict[str, Any]]:
    """Load enriched.json cards and merge functional tags from tagged.csv.

    tagged.csv tags are merged onto each card's existing tags list (no duplicates).
    Returns a list of card dicts ready for search_pool().
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
        d = card.to_dict()
        merged = list(card.tags)
        for tag in tags_by_name.get(card.name, []):
            if tag not in merged:
                merged.append(tag)
        d["tags"] = merged
        pool.append(d)

    return pool


def search_pool(
    pool: List[Dict[str, Any]],
    *,
    color_identity: Optional[List[str]] = None,
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
            ci = card.get("color_identity") or []
            if not set(ci).issubset(set(color_identity)):
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

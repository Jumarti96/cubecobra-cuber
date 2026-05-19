"""Exporters — write tagged.csv (CubeCobra-importable) and deck JSON."""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List

from .cube import CUBES_DIR, CUBECOBRA_CSV_COLUMNS, Card, Cube, cube_dir


def write_tagged_csv(cube: Cube, short_id: str) -> str:
    """Write 19-column CubeCobra CSV with tags as semicolons. Safe for apostrophes."""
    path = os.path.join(cube_dir(short_id), "tagged.csv")
    rows = []
    for card in cube.cards:
        tags_str = ";".join(t for t in card.tags if t)
        cc = card.color_category or ""
        if not cc or cc == "null":
            ci = card.color_identity
            if not ci:
                cc = "C"
            elif len(ci) > 1:
                cc = "M"
            else:
                cc = ci[0]
        rows.append({
            "name": card.name,
            "CMC": str(int(card.cmc)),
            "Type": card.type_line,
            "Color": "".join(card.color_identity),
            "Set": card.set_code.upper(),
            "Collector Number": card.collector_number,
            "Rarity": card.rarity.capitalize() if card.rarity else "",
            "Color Category": cc,
            "status": card.status,
            "Finish": card.finish,
            "board": card.board,
            "maybeboard": "false",
            "image URL": card.image_url or "",
            "image Back URL": card.image_back_url or "",
            "tags": tags_str,
            "Notes": card.notes or "",
            "MTGO ID": card.mtgo_id or "",
            "Custom": "false",
            "Voucher": "false",
        })

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CUBECOBRA_CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    return path


def write_deck_json(
    cards: List[Card],
    short_id: str,
    deck_name: str,
    strategy: str = "",
    colors: str = "",
) -> str:
    """Write a deck to cubes/{short_id}/decks/{deck_name}.json."""
    from datetime import datetime, timezone

    decks_dir = os.path.join(cube_dir(short_id), "decks")
    os.makedirs(decks_dir, exist_ok=True)

    # Sanitize deck_name for filesystem
    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in deck_name.lower())
    path = os.path.join(decks_dir, f"{safe_name}.json")

    lands = [c for c in cards if "Land" in c.type_line]
    nonlands = [c for c in cards if "Land" not in c.type_line]

    deck = {
        "deck_name": deck_name,
        "cube_short_id": short_id,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "colors": colors,
        "land_count": len(lands),
        "nonland_count": len(nonlands),
        "cards": [c.to_dict() for c in cards],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(deck, f, indent=2, ensure_ascii=False)

    return path

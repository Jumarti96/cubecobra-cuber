"""Exporters — write tagged.csv (CubeCobra-importable) and deck JSON."""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
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
    """Write a deck to cubes/{short_id}/decks/{deck_name}/deck.json."""
    from datetime import datetime, timezone
    from .cube import load_meta

    meta = load_meta(short_id)
    cube_id = meta.get("id") or meta.get("short_id", short_id)
    cube_slug = meta.get("slug", "")

    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in deck_name.lower())
    deck_folder = os.path.join(cube_dir(short_id), "decks", safe_name)
    os.makedirs(deck_folder, exist_ok=True)
    path = os.path.join(deck_folder, "deck.json")

    lands = [c for c in cards if "Land" in c.type_line]
    nonlands = [c for c in cards if "Land" not in c.type_line]

    deck = {
        "deck_name": deck_name,
        "cube_id": cube_id,
        "cube_slug": cube_slug,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "strategy": strategy,
        "colors": colors,
        "land_count": len(lands),
        "nonland_count": len(nonlands),
        "cards": [c.to_dict() for c in cards],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(deck, f, indent=2, ensure_ascii=False)

    return path


def _card_sort_key(card: Card) -> tuple:
    creature = 0 if "Creature" in card.type_line else 1 if "Land" in card.type_line else 2
    return (creature, card.name)


def _group_cards(cards: List[Card]) -> List[tuple]:
    counts: Dict[tuple, int] = defaultdict(int)
    groups: Dict[tuple, Card] = {}
    for c in cards:
        key = (c.name, c.set_code)
        counts[key] += 1
        if key not in groups:
            groups[key] = c
    result = []
    for key, card in groups.items():
        result.append((counts[key], card.set_code, card.name, card.type_line))
    result.sort(key=lambda x: _card_sort_key(Card(
        name=x[2], scryfall_id="", cmc=0, type_line=x[3],
        color_identity=[], oracle_text="", rarity="", set_code=x[1],
        collector_number="", color_category="", board="", finish="",
        status="", image_url="",
    )))
    return result


def write_mwdeck(
    mainboard: List[Card],
    sideboard: List[Card],
    short_id: str,
    deck_name: str,
) -> str:
    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in deck_name.lower())
    deck_folder = os.path.join(cube_dir(short_id), "decks", safe_name)
    os.makedirs(deck_folder, exist_ok=True)
    path = os.path.join(deck_folder, "deck.mwDeck")

    main_groups = _group_cards(mainboard)
    side_groups = _group_cards(sideboard)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"// NAME : {deck_name}\n")
        f.write("// CREATOR : Cuber\n")
        f.write("// FORMAT : Cube\n")

        for qty, set_code, name, _type_line in main_groups:
            code = set_code.upper() if set_code else "???"
            f.write(f"{qty} [{code}] {name}\n")

        for qty, set_code, name, _type_line in side_groups:
            code = set_code.upper() if set_code else "???"
            f.write(f"SB:  {qty} [{code}] {name}\n")

    return path


def write_deck_analysis_md(
    analysis_text: str,
    short_id: str,
    deck_name: str,
    frontmatter: Dict[str, Any],
) -> str:
    """Write deck analysis as analysis.md with YAML frontmatter to the deck folder.

    frontmatter keys: deck_name, cube_id, cube_slug, colors, format,
                      built_at, mana_audit_status, restrictions_status
    """
    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in deck_name.lower())
    deck_folder = os.path.join(cube_dir(short_id), "decks", safe_name)
    os.makedirs(deck_folder, exist_ok=True)
    path = os.path.join(deck_folder, "analysis.md")

    fm_lines = []
    for k, v in frontmatter.items():
        safe_v = str(v).replace('"', '\\"')
        fm_lines.append(f'{k}: "{safe_v}"')

    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("\n".join(fm_lines))
        f.write("\n---\n\n")
        f.write(analysis_text)

    return path

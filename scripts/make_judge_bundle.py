"""Assemble a blinded A/B judge bundle from two saved deck folders.

Used by the deck-judge protocol (docs/deck-judge-protocol.md): the bundle carries the two
decks under randomized labels A/B plus the shared card pool and dossier, and nothing that
identifies which deck came from which builder, skill version, or session. The label key is
written OUTSIDE the bundle directory so a judge pointed at the bundle can never read it.

Usage:
    python scripts/make_judge_bundle.py <deck_dir_1> <deck_dir_2> \
        --cube cubes/<slug> --out <bundle_dir> [--seed N]

Prints the bundle path, the label-key path, and the bundle's SHA-256 (the integrity hash
the judge prompt embeds).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from typing import Any, Dict, List, Optional

# Deck-level fields that could identify a deck's origin, age, or session — stripped.
_DECK_STRIP = {"deck_name", "built_at", "dossier_sha256", "cube_id", "cube_slug"}

# Per-card display/metadata fields irrelevant to judging — stripped for size and to
# avoid leaking set/printing differences between builds.
_CARD_STRIP = {
    "image_url", "image_back_url", "mtgo_id", "finish", "status", "notes",
    "collector_number", "set", "scryfall_id", "color_category", "layout", "custom",
    "voucher", "maybeboard",
}

# Pool record fields shipped to judges (oracle evidence, no taxonomy, no display data).
_POOL_FIELDS = (
    "name", "oracle_text", "mana_cost", "colors", "color_identity", "cmc",
    "type_line", "rarity", "power", "toughness",
)


def _clean_card(card: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in card.items() if k not in _CARD_STRIP}


def _clean_deck(deck: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in deck.items() if k not in _DECK_STRIP}
    for board in ("mainboard", "sideboard"):
        out[board] = [_clean_card(c) for c in (out.get(board) or [])]
    return out


def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pool_records(cube_dir: str) -> List[Dict[str, Any]]:
    enriched = _load_json(os.path.join(cube_dir, "enriched.json"))
    records = []
    for card in enriched.get("cards", []):
        if card.get("board") != "mainboard":
            continue
        records.append({k: card.get(k) for k in _POOL_FIELDS})
    return records


def build_bundle(
    deck_dir_1: str,
    deck_dir_2: str,
    cube_dir: str,
    out_dir: str,
    seed: Optional[int] = None,
) -> Dict[str, str]:
    """Write `<out_dir>/judge_input.json` (blinded) and a sibling label-key file.

    Returns {"bundle_path", "key_path", "sha256"}. The label assignment is a coin flip
    (seedable for reproducibility); the key file maps A/B back to the input folders and
    must never be shown to a judge.
    """
    deck1 = _clean_deck(_load_json(os.path.join(deck_dir_1, "deck.json")))
    deck2 = _clean_deck(_load_json(os.path.join(deck_dir_2, "deck.json")))

    rng = random.Random(seed)
    if rng.random() < 0.5:
        labels = {"A": deck_dir_1, "B": deck_dir_2}
        decks = {"A": deck1, "B": deck2}
    else:
        labels = {"A": deck_dir_2, "B": deck_dir_1}
        decks = {"A": deck2, "B": deck1}

    bundle = {
        "decks": decks,
        "card_pool": _pool_records(cube_dir),
        "dossier": _load_json(os.path.join(cube_dir, "dossier.json")),
    }

    os.makedirs(out_dir, exist_ok=True)
    bundle_path = os.path.join(out_dir, "judge_input.json")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False)

    sha256 = hashlib.sha256(open(bundle_path, "rb").read()).hexdigest()

    # The key lives OUTSIDE the bundle directory: a judge reads only judge_input.json.
    key_path = os.path.normpath(out_dir) + "_label_key.json"
    with open(key_path, "w", encoding="utf-8") as f:
        json.dump({"labels": labels, "seed": seed, "bundle_sha256": sha256}, f, indent=2)

    return {"bundle_path": bundle_path, "key_path": key_path, "sha256": sha256}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("deck_dir_1", help="first saved deck folder (contains deck.json)")
    ap.add_argument("deck_dir_2", help="second saved deck folder (contains deck.json)")
    ap.add_argument("--cube", required=True,
                    help="cube directory, e.g. cubes/<slug> (needs enriched.json + dossier.json)")
    ap.add_argument("--out", required=True, help="output directory for judge_input.json")
    ap.add_argument("--seed", type=int, default=None,
                    help="seed for the label coin flip (default: nondeterministic)")
    args = ap.parse_args()

    result = build_bundle(args.deck_dir_1, args.deck_dir_2, args.cube, args.out, args.seed)
    print(f"bundle:    {result['bundle_path']}")
    print(f"label key: {result['key_path']}  (never show this to a judge)")
    print(f"sha256:    {result['sha256']}")


if __name__ == "__main__":
    main()

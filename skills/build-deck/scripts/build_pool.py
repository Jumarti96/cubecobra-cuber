"""Phase 0 — build the working pool cache from a cube's enriched data.

Usage:
    python skills/build-deck/scripts/build_pool.py --run <run-token>

Reads `_workspace/<run>/run_config.json` (cube_slug + card_pool_rules) and writes
`_workspace/<run>/working_pool.json`.

Two things this script exists to guarantee, both of which were previously re-derived
by hand every run and got missed:

1. DFC BACKFILL. enriched.json leaves top-level `mana_cost`, `power` and `toughness`
   NULL on every transform/modal double-faced card and stores the real values on
   `card_faces[0]`. Left alone this silently zeroes those cards' pip demand in the
   mana audit AND makes effective_cost.best_mode reject them from the colour gate
   entirely — on one cube that hid 41 cards, including several the deck wanted.

2. DEDUPE. load_merged_pool materialises `multipliers` as duplicate rows (503 rows
   for 305 distinct cards at 2x commons). Counting that raw double-counts every
   common and uncommon while rares stay at one row, so the distortion is uneven.
   Copy limits are enforced separately by cube_search.get_max_copies, which needs
   no duplicate rows.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.getcwd())

from _common import (BASICS, base_parser, dump_json, load_config, run_dir,  # noqa: E402
                     utf8)

from cuber import cube_search  # noqa: E402

FIELDS = ["name", "oracle_text", "mana_cost", "colors", "color_identity", "tags",
          "taxonomic_profile", "cmc", "type_line", "rarity", "power", "toughness",
          "board"]

# Minimal synthesized entries for basics. Basics are FORMAT-SUPPLIED: they are never
# rarity-capped and are added whether or not the cube list contains them.
BASIC_STUB = {
    "Plains":   ("W", "({T}: Add {W}.)", "Basic Land — Plains"),
    "Island":   ("U", "({T}: Add {U}.)", "Basic Land — Island"),
    "Swamp":    ("B", "({T}: Add {B}.)", "Basic Land — Swamp"),
    "Mountain": ("R", "({T}: Add {R}.)", "Basic Land — Mountain"),
    "Forest":   ("G", "({T}: Add {G}.)", "Basic Land — Forest"),
}


def main() -> int:
    utf8()
    args = base_parser(__doc__ or "", need_deck=False).parse_args()
    cfg = load_config(args.run)
    out_dir = run_dir(args.run)

    raw = cube_search.load_merged_pool(cfg["cube_slug"],
                                       card_pool_rules=cfg.get("card_pool_rules") or None)
    print(f"raw rows: {len(raw)}")

    seen: dict = {}
    dfc_fixed: list = []
    for c in raw:
        name = c.get("name")
        if name in seen:
            continue                                   # dedupe: one row per distinct card
        row = {k: c.get(k) for k in FIELDS}
        faces = c.get("card_faces") or []
        if faces:
            row["card_faces"] = [
                {k: f.get(k) for k in
                 ("name", "oracle_text", "mana_cost", "type_line", "power", "toughness")}
                for f in faces
            ]
            if not row.get("mana_cost"):
                row["mana_cost"] = faces[0].get("mana_cost") or ""
                dfc_fixed.append(name)
            if row.get("power") is None:
                row["power"] = faces[0].get("power")
                row["toughness"] = faces[0].get("toughness")
        seen[name] = row

    added = []
    for name, (ci, oracle, type_line) in BASIC_STUB.items():
        if name not in seen:
            seen[name] = {"name": name, "oracle_text": oracle, "mana_cost": "",
                          "colors": [], "color_identity": [ci], "tags": [],
                          "taxonomic_profile": None, "cmc": 0, "type_line": type_line,
                          "rarity": "common", "power": None, "toughness": None,
                          "board": "mainboard"}
            added.append(name)

    pool = list(seen.values())
    size = dump_json(pool, os.path.join(out_dir, "working_pool.json"))

    print(f"distinct cards: {len(pool)}  ({size:,} bytes)")
    print(f"by rarity: {dict(Counter(c.get('rarity') for c in pool))}")
    print(f"synthesized basics: {added or 'none (cube already had them)'}")
    print(f"DFC mana_cost backfilled from card_faces[0]: {len(dfc_fixed)}")
    if dfc_fixed:
        print(f"  {sorted(dfc_fixed)[:8]}{' ...' if len(dfc_fixed) > 8 else ''}")

    still = [c["name"] for c in pool
             if not c.get("mana_cost") and "land" not in (c.get("type_line") or "").lower()]
    if still:
        # Meld results are never cast, so an empty cost is correct for them.
        print(f"nonland cards still without mana_cost (expected: meld results): {still}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

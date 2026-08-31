"""Phase 5B step 3/4 — land count and pip math.

Usage:
    python skills/build-deck/scripts/land_math.py --run <token> --deck deck1
    python skills/build-deck/scripts/land_math.py --run <token> --deck deck1 --spec <spec.json>

`--spec` takes {"nonlands": [[name, qty], ...]} for costing a list before it is a deck;
without it the script reads the deck's own nonland entries.

Prints the land_target dict VERBATIM. Do not round, adjust or re-derive any of its
numbers by hand — Phase 6 audits against the same function, so a hand-derived count
creates a disagreement the audit will flag.

Commander formats do not use land_target at all: deck_audit averages the Burgess and
Karsten recommendations instead and reports land_target_trace as null. This script
says so rather than printing a number that does not apply.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.getcwd())

from _common import (base_parser, is_commander_format, is_land, load_config,  # noqa: E402
                     load_deck, load_json, load_pool, utf8)

from cuber import deck_audit  # noqa: E402


def main() -> int:
    utf8()
    p = base_parser(__doc__ or "")
    p.add_argument("--spec", help="optional {'nonlands': [[name, qty], ...]}")
    args = p.parse_args()

    cfg = load_config(args.run)
    pool = load_pool(args.run)
    D = load_deck(args.run, args.deck)
    core = D.get("core_colors") or []

    if args.spec:
        entries = [{"name": n, "qty": q} for n, q in load_json(args.spec)["nonlands"]]
    else:
        entries = [c for c in D["mainboard"] if not is_land(pool[c["name"]])]

    rows = []
    for e in entries:
        rows.extend([pool[e["name"]]] * e["qty"])
    n = len(rows)
    deck_size = cfg["deck_size"]
    avg_mv = sum(float(c.get("cmc") or 0) for c in rows) / n
    accel = deck_audit.accel_count(rows)

    print(f"nonlands={n}  land slots={deck_size - n}  avg_mv={avg_mv:.3f}  accel={accel}")

    if is_commander_format(cfg):
        print("land_target: NOT APPLICABLE for commander formats — deck_audit averages "
              "the Burgess and Karsten recommendations and reports land_target_trace as "
              "null. Take the count from the Phase 6 audit instead.")
    else:
        trace = deck_audit.land_target(deck_size, avg_mv, accel)
        print("land_target trace (record VERBATIM as land_math.target):")
        print(json.dumps(trace, indent=1, default=str))
        if trace.get("clamped"):
            print("  !! clamped=true — the target ran outside the sane land-fraction band. "
                  "Re-check the projected avg MV before accepting this number.")

    pips: Counter = Counter()
    for c in rows:
        for sym in re.findall(r"\{([WUBRG])\}", c.get("mana_cost") or ""):
            pips[sym] += 1
    total = sum(pips[k] for k in core) or 1
    print(f"pips: {dict(pips)}")
    for k in core:
        print(f"  {k}: {pips[k]} ({100 * pips[k] / total:.1f}%)")

    print("curve:", sorted(Counter(float(c.get("cmc") or 0) for c in rows).items()))
    rm = sorted({c["name"] for c in rows if c.get("rarity") in ("rare", "mythic")})
    print(f"rare+mythic nonland cards: {len(rm)} {rm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

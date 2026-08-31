"""Phase 6 — mana audit gate.

Usage:
    python skills/build-deck/scripts/mana_audit.py --run <token> --deck deck1

Writes `<deck>/audit.json` and prints deck_audit.format_audit_report.

Passes `format` and `commander_cards` through from run_config. deck_audit branches on
format internally — commander formats use the Burgess/Karsten average and set
land_target_trace to null — so passing commander_cards=None on a commander build does
not error, it silently defaults the commander's mana value to 4.

Cards are expanded from the WORKING POOL rows, not the deck rows, because deck_audit
derives ramp_count and cantrip_count from card["tags"].
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.getcwd())

from _common import (base_parser, commander_cards, dump_json, expand,  # noqa: E402
                     load_config, load_deck, load_pool, run_dir, utf8)

from cuber import deck_audit  # noqa: E402


def main() -> int:
    utf8()
    args = base_parser(__doc__ or "").parse_args()
    cfg = load_config(args.run)
    D = load_deck(args.run, args.deck)
    pool = load_pool(args.run)

    cards = expand(D["mainboard"], pool)
    audit = deck_audit.mana_audit(
        cards,
        cfg["format"],
        commander_cards(cfg, pool),
        core_colors=D.get("core_colors"),
        splash_colors=D.get("splash_colors"),
    )
    print(deck_audit.format_audit_report(audit))
    dump_json(audit, os.path.join(run_dir(args.run), args.deck, "audit.json"))
    status = audit.get("overall_status")
    print("\nRESULT:", status)
    return 0 if status in ("PASS", "WARN", None) else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Phase 5C — deterministic pre-flight validation. Every check is a string or number
comparison; none is a judgement.

Usage:
    python skills/build-deck/scripts/validate_build.py --run <token> --deck deck1
    python skills/build-deck/scripts/validate_build.py --run <token> --deck deck1 --json

Deck size, sideboard size and the pool rules all come from run_config.json. Hardcoding
any of them (an earlier throwaway version pinned DECK_SIZE = 40) makes this script
fail every 60-card and Commander build on check 1 forever.

Exit status is nonzero on any failure, so a caller can gate on it.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.getcwd())

from _common import (BASICS, base_parser, is_commander_format, is_land,  # noqa: E402
                     load_config, load_deck, load_pool, utf8)

from cuber import cube_search, effective_cost  # noqa: E402


def main() -> int:
    utf8()
    p = base_parser(__doc__ or "")
    p.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = p.parse_args()

    cfg = load_config(args.run)
    D = load_deck(args.run, args.deck)
    pool = load_pool(args.run)
    rules = cfg.get("card_pool_rules") or None
    core = D.get("core_colors") or []
    splash = D.get("splash_colors") or []

    deck_size = cfg["deck_size"]
    sb_size = D.get("sideboard_size", cfg["sideboard_size"])
    commanders = cfg.get("commander") or []

    mb, sb = D["mainboard"], D.get("sideboard", [])
    results = []

    def chk(name, ok, msg):
        results.append({"check": name, "pass": bool(ok), "detail": msg})

    # 1 — sizes. For commander formats deck_size already INCLUDES the commander.
    mb_n = sum(c["qty"] for c in mb) + (len(commanders) if is_commander_format(cfg) else 0)
    sb_n = sum(c["qty"] for c in sb)
    chk("1 mainboard size", mb_n == deck_size,
        f"{mb_n} vs {deck_size} expected"
        + (f" (incl. {len(commanders)} commander)" if commanders else ""))
    chk("1 sideboard size", sb_n == sb_size, f"{sb_n} vs {sb_size} expected")

    # 2 — exact-name membership. Synthesized basics are in the cache and count.
    missing = [c["name"] for c in mb + sb if c["name"] not in pool]
    chk("2 exact-name membership", not missing,
        f"not in pool: {missing}" if missing else "all names found")

    # 3 — copy limits via the same helper the pool loader uses. Basics are exempt.
    totals = defaultdict(int)
    for c in mb + sb:
        totals[c["name"]] += c["qty"]
    for n in commanders:
        totals[n] += 1
    over = []
    for name, qty in totals.items():
        if name in BASICS or name not in pool:
            continue
        mx = cube_search.get_max_copies(pool[name], rules)
        if qty > mx:
            over.append(f"{name}: {qty} > {mx}")
    chk("3 copy limits", not over, "; ".join(over) or "all within card_pool_rules")

    # 4 — colour usability by USABLE MODE, not printed identity. A card with a
    # colourless/in-colour replacement mode (a cycler, a kicker declined) is legal
    # even though color_identity prints off-colour.
    identity = core + splash
    if is_commander_format(cfg) and commanders:
        identity = sorted({c for n in commanders
                           for c in (pool[n].get("color_identity") or [])})
    bad, modes = [], {}
    for c in mb + sb:
        card = pool.get(c["name"])
        if card is None or is_land(card):
            continue
        m = effective_cost.best_mode(card, identity, [] if is_commander_format(cfg) else splash)
        if m is None:
            bad.append(c["name"])
        elif set(card.get("color_identity") or []) - set(identity):
            modes[c["name"]] = {"mode": m.get("mode"), "usable_as": m.get("usable_as")}
    chk("4 colour usability (best_mode)", not bad,
        f"unusable: {bad}" if bad else f"all usable in {identity}")

    # 5 — splash cap. A card castable in core_colors ALONE is core, not a splash,
    # even when its printed identity is off-colour: best_mode(card, core, []) already
    # returns non-None for it. Keying this check on raw color_identity wrongly
    # rejects such cards.
    cand = set(D.get("splash_candidates") or [])
    splashed = [c["name"] for c in mb + sb
                if c["name"] in pool and not is_land(pool[c["name"]])
                and set(pool[c["name"]].get("color_identity") or []) - set(core)
                and effective_cost.best_mode(pool[c["name"]], core, []) is None]
    not_named = [n for n in splashed if n not in cand]
    per = defaultdict(int)
    for n in splashed:
        for col in set(pool[n].get("color_identity") or []) - set(core):
            per[col] += 1
    overs = [f"{k}:{v}" for k, v in per.items() if v > 3]
    chk("5 splash cap", not not_named and not overs,
        f"not in splash_candidates: {not_named}; over-3: {overs}"
        if (not_named or overs) else f"{len(splashed)} splash cards played")

    # 6 — extra user constraint, when one was set (e.g. "at most N rares total").
    cap = (cfg.get("card_pool_rules") or {}).get("max_rare_mythic_total")
    if cap is not None:
        rm = sorted({c["name"] for c in mb + sb
                     if c["name"] in pool and pool[c["name"]].get("rarity") in ("rare", "mythic")})
        chk(f"6 rare/mythic cap (<={cap})", len(rm) <= cap, f"{len(rm)}: {rm}")

    ok = all(r["pass"] for r in results)
    if args.json:
        print(json.dumps({"deck": args.deck, "all_pass": ok, "results": results,
                          "off_identity_modes": modes}, ensure_ascii=False, indent=1))
    else:
        print(f"=== PHASE 5C VALIDATION — {args.deck} ({D.get('deck_name')}) ===")
        for r in results:
            print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['check']}: {r['detail']}")
        if modes:
            print(f"  note cards played OFF their printed identity: {modes}")
        print("RESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

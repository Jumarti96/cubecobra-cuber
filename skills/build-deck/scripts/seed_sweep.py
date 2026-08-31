"""Phase 5A — generate the machine seed, and verify the sweep partitions it exactly.

Usage:
    python skills/build-deck/scripts/seed_sweep.py --run <token> --deck deck1 \
        --pipeline <pipeline.json>
    python skills/build-deck/scripts/seed_sweep.py --run <token> --deck deck1 \
        --partition <partition.json> --verify

`pipeline.json`: {"payoff": str, "clusters": [str], "core_colors": [str],
                  "splash_colors": [str], "splash_candidates": [str]}

The seed is a QUERY RESULT, not a remembered list. Membership is the query's output;
the builder annotates and subtracts from it but never authors it.

FOUR BANDS. The six structural roles are Enabler/Fodder, Engine/Outlet,
Payload/Payoff, Interaction/Disruption, Infrastructure/Consistency and Standalone
Threat. A three-band seed (pipeline clusters + staple roles + threat roles) covers
only four of them: Engine/Outlet and Enabler/Fodder reach the seed ONLY by cluster
overlap, so a repeatable engine card whose clusters sit outside the locked pipeline
is invisible to every downstream agent. On one cube that hid a repeatable non-combat
drain creature and a colourless evasion granter — both of which the deck wanted, and
both of which had to be re-found much later at far higher cost. The engine band
closes the gap; measured on two pipelines it left zero colour-usable nonland cards
orphaned, for 11 and 5 extra seed rows respectively.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.getcwd())

from _common import (base_parser, dump_json, load_config, load_json,  # noqa: E402
                     load_pool, run_dir, utf8)

from cuber import cube_search  # noqa: E402

STAPLE_ROLES = {"Interaction/Disruption", "Infrastructure/Consistency"}
THREAT_ROLES = {"Payload/Payoff", "Standalone Threat"}
ENGINE_ROLES = {"Engine/Outlet", "Enabler/Fodder"}
STAPLE_CAP, THREAT_CAP, ENGINE_CAP = 40, 25, 25


def prof(c):  return c.get("taxonomic_profile") or {}
def clus(c):  return set(prof(c).get("synergy_clusters") or [])
def roles(c): return set(prof(c).get("structural_roles") or [])
def is_land(c): return "land" in (c.get("type_line") or "").lower()


def build_seed(run, deck, pipeline):
    pool = list(load_pool(run).values())
    core = pipeline["core_colors"]
    splash = pipeline.get("splash_colors") or []
    candidates = pipeline.get("splash_candidates") or []
    want = set(pipeline["clusters"])
    payoff = pipeline["payoff"]

    # search_pool stamps `usable_as` via effective_cost.best_mode, so the slice carries
    # the same colour-usability verdict Phase 5C check 4 and Challenger item 4 test
    # against. Never pass tags= — pooled tags come only from tagged.csv, are AND-only,
    # and return zero rows IN SILENCE on a cube without one.
    core_cards = cube_search.search_pool(pool, color_identity=core)
    wide = cube_search.search_pool(pool, color_identity=core, splash_color_identity=splash)
    by_name = {c["name"]: c for c in wide}

    pipeline_band = [c for c in core_cards
                     if not is_land(c) and (clus(c) & want or c["name"] == payoff)]
    have = {c["name"] for c in pipeline_band}
    # A splash colour admits nothing but its named candidates. Lands are excluded from
    # every band: they are chosen from the whole pool in steps 3-4.
    pipeline_band += [by_name[n] for n in candidates
                      if n in by_name and n not in have and not is_land(by_name[n])]

    def band(role_set, cap, taken):
        picked = sorted((c for c in core_cards
                         if c["name"] not in taken and not is_land(c) and roles(c) & role_set),
                        key=lambda c: (float(c.get("cmc") or 0), c["name"]))
        return picked[:cap], [c["name"] for c in picked[cap:]]

    seen = {c["name"] for c in pipeline_band}
    staple, staple_dropped = band(STAPLE_ROLES, STAPLE_CAP, seen)
    seen |= {c["name"] for c in staple}
    threat, threat_dropped = band(THREAT_ROLES, THREAT_CAP, seen)
    seen |= {c["name"] for c in threat}
    engine, engine_dropped = band(ENGINE_ROLES, ENGINE_CAP, seen)

    def row(c, b):
        d = {k: c.get(k) for k in
             ("name", "oracle_text", "type_line", "mana_cost", "cmc", "usable_as")}
        d["rarity"] = c.get("rarity")
        d["band"] = b
        return d

    seed = ([row(c, "pipeline") for c in pipeline_band] + [row(c, "staple") for c in staple]
            + [row(c, "threat") for c in threat] + [row(c, "engine") for c in engine])

    meta = {"script": "skills/build-deck/scripts/seed_sweep.py",
            "pipeline_band": len(pipeline_band), "staple_band": len(staple),
            "threat_band": len(threat), "engine_band": len(engine),
            "seed_total": len(seed),
            "staple_cap": STAPLE_CAP, "threat_cap": THREAT_CAP, "engine_cap": ENGINE_CAP,
            "staple_dropped": staple_dropped, "threat_dropped": threat_dropped,
            "engine_dropped": engine_dropped,
            **{k: pipeline.get(k) for k in
               ("core_colors", "splash_colors", "splash_candidates", "clusters", "payoff")}}

    d = os.path.join(run_dir(run), deck)
    os.makedirs(d, exist_ok=True)
    dump_json(seed, os.path.join(d, "seed.json"))
    dump_json(meta, os.path.join(d, "seed_query.json"))

    print(f"bands  pipeline={len(pipeline_band)}  staple={len(staple)}  "
          f"threat={len(threat)}  engine={len(engine)}  total={len(seed)}")
    dropped = staple_dropped + threat_dropped + engine_dropped
    print(f"dropped by caps (recorded in seed_query, visible to the absence audit): "
          f"{len(dropped)}")
    for b in ("pipeline", "staple", "threat", "engine"):
        names = [c["name"] for c in seed if c["band"] == b]
        print(f"[{b}] {len(names)}: {names}")
    return 0


def verify(run, deck, partition_path):
    """Assert the sweep's two lists partition the seed EXACTLY.

    A card in the seed and in neither list is the failure this exists to prevent: no
    agent downstream ever sees it, and nothing records that it was considered.
    """
    d = os.path.join(run_dir(run), deck)
    seed = load_json(os.path.join(d, "seed.json"))
    sweep = load_json(partition_path if partition_path else os.path.join(d, "sweep.json"))
    names = {c["name"] for c in seed}
    inc = {e["card"] for e in sweep["include_candidates"]}
    exc = {n for e in sweep["considered_but_excluded"]
           for n in (e.get("cards") or [e["card"]])}

    problems = []
    if names - (inc | exc):
        problems.append(f"UNRECORDED (in seed, in neither list): {sorted(names - (inc | exc))}")
    if inc & exc:
        problems.append(f"DOUBLE-LISTED: {sorted(inc & exc)}")
    if (inc | exc) - names:
        problems.append(f"NOT IN SEED: {sorted((inc | exc) - names)}")
    bad = [e["card"] for e in sweep["include_candidates"]
           if e.get("count_dependent") and e["card"] in exc]
    if bad:
        problems.append(f"count_dependent card also excluded: {bad}")

    if problems:
        for p in problems:
            print("  [FAIL]", p)
        print("RESULT: PARTITION IS NOT EXACT")
        return 1
    cd = sum(1 for e in sweep["include_candidates"] if e.get("count_dependent"))
    notable = sum(1 for e in sweep["considered_but_excluded"] if e.get("notable"))
    print(f"VERIFY PASS  seed={len(names)}  include={len(inc)}  excluded={len(exc)}  "
          f"count_dependent={cd}  notable_exclusions={notable}")
    return 0


def main() -> int:
    utf8()
    p = base_parser(__doc__ or "")
    p.add_argument("--pipeline", help="pipeline json for seed generation")
    p.add_argument("--partition", help="partition/sweep json for --verify")
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()
    load_config(args.run)                       # validates the run exists and its format
    if args.verify:
        return verify(args.run, args.deck, args.partition)
    if not args.pipeline:
        raise SystemExit("--pipeline is required unless --verify is given")
    return build_seed(args.run, args.deck, load_json(args.pipeline))


if __name__ == "__main__":
    raise SystemExit(main())

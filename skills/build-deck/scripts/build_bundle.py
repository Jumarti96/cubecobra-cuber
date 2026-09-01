"""Phase 8 — write the grill bundles. Phase 9 approval rounds — write the delta.

Usage:
    python skills/build-deck/scripts/build_bundle.py --run <token> --deck deck1
    python skills/build-deck/scripts/build_bundle.py --run <token> --deck deck1 --delta

Writes:
    <deck>/grill_proposer.json    ~25 KB   the Proposer reads ONLY this
    <deck>/grill_challenger.json  ~250 KB  the Challenger reads ONLY this
    <deck>/grill_delta.json        ~30 KB  approval rounds only (--delta)

WHY A DELTA. An approval round asks the Challenger to verify a handful of changed
slots, and it used to re-read the whole 250-300 KB challenger bundle to do it. Measured
on a three-deck run: five approval rounds, and ~90% of what each reloaded was provably
unchanged since round 0. The delta ships the deck array, the re-run gate outputs and
ONLY the build_output keys that actually moved — an ~88% cut.

The caller declares nothing about what changed. `grill_challenger.json` already on disk
IS a byte-exact snapshot of what the Challenger's context holds, so we diff against it.
That makes the changed-key set a machine fact rather than a prompt-adherence gamble —
the same argument that splits the two bundles in the first place.

Two consequences of that design, both load-bearing:
  * --delta does NOT rewrite the full bundles. Rewriting grill_challenger.json would
    destroy the snapshot the NEXT delta diffs against, so suppression is required for
    correctness, not just for cost. A fresh Challenger, or a re-dispatched Proposer,
    needs a full (non---delta) rebuild first.
  * --delta with no snapshot and no --changed-bo is an ERROR, not a fallback. Silently
    shipping the full build_output would be a cost regression; silently shipping an
    empty delta would be a quality regression. Neither is an acceptable default.

The full `deck` array always ships in the delta. It is small (~20 KB) and it is what
keeps the Challenger's recounts correct: every denominator moves when any slot changes,
so a deck array trimmed to just the swapped cards would look cheaper and make every
recount wrong.

WHY TWO FILES. The Proposer's job is to defend the cards in `deck`; it never needs
the card pool or the dossier. Shipping it a single 440 KB bundle spent roughly 70% of
its context on a pool it cannot use. Splitting by role is a guarantee; telling one
agent "do not read that key" is a prompt-adherence gamble.

POOL PROJECTION. The Challenger's pool is projected down by four fields:
  tags        — provably a subset of taxonomic_profile on every row (verified 305/305)
  card_faces  — SAFE TO DROP ONLY BECAUSE build_pool.py backfills the front face's
                mana_cost/power/toughness onto the top level. effective_cost falls
                back to card_faces[0] when mana_cost is empty; with the backfill that
                branch is unreachable. If the backfill is ever removed, restore this
                field in the same commit or every DFC looks castable in every colour.
  board       — constant "mainboard" on every pool row
  colors      — no Phase 9 check reads it; colour work goes through best_mode

oracle_text and taxonomic_profile are NEVER trimmed: they are the IRON RULE's evidence
base and what checklist items 2, 5 and 10 read.

The dossier ships WHOLE to the Challenger. An earlier proposal trimmed tribal_rosters,
structural_census and pool_limits as unreferenced; the run record contradicts that —
structural_census.graveyard_hate was load-bearing in two decks, and tribal_rosters
verified a 51-creature tribal count twice.

That graveyard_hate anecdote used to read "the cube contains no graveyard hate at all".
It was wrong, and it is worth keeping as a cautionary note rather than deleting: the zero
was a false negative in dossier._GY_HATE_RE, which matched only whole-graveyard exile and
missed the commoner single-card form, on a cube that actually contains two such cards.
Two decks conceded the graveyard threat class on that zero. The regex is fixed (see the
comment on _GY_HATE_RE) — but the conclusion here stands and is strengthened: the dossier
ships whole BECAUSE its census fields drive real decisions, which is exactly why a wrong
one is expensive — and why a coverage_declaration that conceded a threat class on the
strength of a census zero should have cited the probe it was trusting.

TWO BUGS THIS FIXES, both in the `deck` array:
  tags       — deck_audit derives ramp_count/cantrip_count from card["tags"]. Without
               it, checklist item 8 ("independently re-run mana_audit on the deck
               array") computes accel=0 where the builder got a nonzero value, and the
               Challenger reports a phantom discrepancy. This happened.
  usable_as  — the Proposer is required to defend an off-identity card by naming the
               mode that makes it legal, which it cannot do without this field.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.getcwd())

from _common import (base_parser, dump_json, load_config, load_deck,  # noqa: E402
                     load_json, load_pool, run_dir, utf8)

from cuber import effective_cost  # noqa: E402

# Fields projected OUT of each working_pool row for the Challenger bundle.
POOL_DROP = ("tags", "card_faces", "board", "colors")

# build_output keys the Proposer may see. Deliberately excludes count_dependent_verdicts:
# its contract requires it to state counts ITSELF, so handing it the builder's numbers
# is anti-adversarial. Also excludes skeleton_selection, structural_checks,
# failure_modes and phase9_repairs, none of which its checklist reads.
PROPOSER_BO_KEYS = ("macro_archetype", "deck_identity", "thesis_turn", "default_role",
                    "slot_allocation", "pip_math")

# Keys that must never appear in a delta — the whole point of the delta is to stop
# re-shipping them. Asserted before write, because a silent regression here is invisible
# (the delta still "works", it just costs what it was built to save).
DELTA_FORBIDDEN = ("build_output", "dossier", "sweep", "working_pool")

# structural.json ships at the delta's top level as `structural` (it is the proof of
# repair), so shipping it again inside build_output_delta would send the same object twice.
DELTA_BO_SKIP = ("structural_checks",)


def load_prev_bundle(deck_dir):
    """The last full challenger bundle — the snapshot the Challenger's context holds."""
    p = os.path.join(deck_dir, "grill_challenger.json")
    return load_json(p) if os.path.exists(p) else None


def changed_bo_keys(new, old, skip=DELTA_BO_SKIP):
    """build_output keys whose value differs from the last-shipped bundle.

    Union of both key sets, so a DELETED key is reported too. A forward-only `new - old`
    diff would silently hide a retraction, which is exactly the kind of change an
    approval round exists to verify.
    """
    old = old or {}
    keys = (set(new) | set(old)) - set(skip)
    return sorted(k for k in keys if new.get(k) != old.get(k))


def bo_delta(new, old, skip=DELTA_BO_SKIP):
    """{changed key: new value}. A key deleted since the snapshot maps to None."""
    return {k: new.get(k) for k in changed_bo_keys(new, old, skip)}


def deck_delta(new_rows, old_rows):
    """The '-X +Y with counts' line, computed rather than retyped by the orchestrator."""
    old_rows = old_rows or []
    new_q = {(r["name"], r["board"]): r["qty"] for r in new_rows}
    old_q = {(r["name"], r["board"]): r["qty"] for r in old_rows}
    added = sorted(f"{n} ({b}) x{new_q[(n, b)]}" for (n, b) in set(new_q) - set(old_q))
    removed = sorted(f"{n} ({b}) x{old_q[(n, b)]}" for (n, b) in set(old_q) - set(new_q))
    qty = [{"card": n, "board": b, "was": old_q[(n, b)], "now": new_q[(n, b)]}
           for (n, b) in sorted(set(new_q) & set(old_q))
           if new_q[(n, b)] != old_q[(n, b)]]
    return {"added": added, "removed": removed, "qty_changed": qty}


def deck_rows(D, pool):
    """One row per distinct card, carrying everything BOTH agents need."""
    rows = []
    for board in ("mainboard", "sideboard"):
        for c in D.get(board, []):
            src = pool[c["name"]]
            mode = effective_cost.best_mode(src, D.get("core_colors") or [],
                                            D.get("splash_colors") or [])
            rows.append({
                "name": c["name"], "qty": c["qty"], "board": board,
                "role": c.get("role"),
                "oracle_text": src.get("oracle_text"),
                "mana_cost": src.get("mana_cost"), "cmc": src.get("cmc"),
                "type_line": src.get("type_line"), "rarity": src.get("rarity"),
                "colors": src.get("colors"), "color_identity": src.get("color_identity"),
                "power": src.get("power"), "toughness": src.get("toughness"),
                # Bug fix 1 — deck_audit reads card["tags"] for ramp/cantrip.
                "tags": src.get("tags") or [],
                # Bug fix 2 — the Proposer defends off-identity cards by naming the mode.
                "usable_as": (mode or {}).get("usable_as"),
                "cast_mode": (mode or {}).get("mode"),
                "answers": c.get("answers"), "when_to_board": c.get("when_to_board"),
            })
    return rows


def main() -> int:
    utf8()
    p = base_parser(__doc__ or "")
    p.add_argument("--delta", action="store_true",
                   help="Phase 9 approval round: write ONLY grill_delta.json")
    p.add_argument("--changed-bo", default="",
                   help="comma-separated build_output keys; override for when no prior "
                        "grill_challenger.json exists to diff against")
    p.add_argument("--pool-query", default="",
                   help="--delta only: ship the working_pool rows whose oracle_text "
                        "matches this regex, for an absence re-check")
    p.add_argument("--with-pool", action="store_true",
                   help="--delta only: ship the whole projected working_pool (last resort)")
    args = p.parse_args()
    cfg = load_config(args.run)
    d = os.path.join(run_dir(args.run), args.deck)
    L = lambda f: load_json(os.path.join(d, f))

    D = load_deck(args.run, args.deck)
    pool = load_pool(args.run)
    build_output = L("build_output.json")
    if os.path.exists(os.path.join(d, "structural.json")):
        # Embed rather than ship twice — the standalone file stays on disk for humans.
        build_output["structural_checks"] = L("structural.json")

    rows = deck_rows(D, pool)
    meta = {k: D.get(k) for k in
            ("deck_name", "cube_id", "format", "core_colors", "splash_colors",
             "splash_candidates", "splash_note", "sideboard_size",
             "unanswered_threat_classes")}
    meta["deck_size"] = cfg["deck_size"]
    meta["commander"] = cfg.get("commander")

    rules = dict(cfg.get("card_pool_rules") or {})

    # Phase 5C results, captured live so the bundle can never disagree with the gate.
    val = subprocess.run(
        [sys.executable, os.path.join("skills", "build-deck", "scripts", "validate_build.py"),
         "--run", args.run, "--deck", args.deck],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONPATH": ".:skills/build-deck/scripts",
             "PYTHONIOENCODING": "utf-8"})
    validation = [l for l in (val.stdout or "").strip().splitlines() if l.strip()]

    common = {
        "deck": rows,
        "deck_meta": meta,
        "audit": L("audit.json"),
        "card_pool_rules": rules,
        "restrictions_checklist": build_output.get("restrictions_checklist"),
        "validation_report": validation,
    }

    slim_pool = [{k: v for k, v in c.items() if k not in POOL_DROP} for c in pool.values()]

    if args.delta:
        prev = load_prev_bundle(d)
        override = [k.strip() for k in args.changed_bo.split(",") if k.strip()]
        if prev is None and not override:
            print("ERROR: --delta needs a base snapshot to diff against, and no "
                  "grill_challenger.json exists in this deck dir.\n"
                  "  Round 0? Run without --delta.\n"
                  "  Snapshot lost? Pass --changed-bo <comma-separated build_output keys>.")
            return 2

        prev_bo = (prev or {}).get("build_output") or {}
        if override:
            bo_keys = sorted(override)
            bo = {k: build_output.get(k) for k in bo_keys}
        else:
            bo_keys = changed_bo_keys(build_output, prev_bo)
            bo = bo_delta(build_output, prev_bo)

        delta = dict(common)
        delta.update({
            "bundle_kind": "delta",
            "base_bundle": "grill_challenger.json",
            "base_bundle_bytes": (os.path.getsize(os.path.join(d, "grill_challenger.json"))
                                  if prev is not None else None),
            "delta_note": "Everything not present here is UNCHANGED from the "
                          "grill_challenger.json already in your context. Do not re-read it.",
            "structural": L("structural.json") if os.path.exists(
                os.path.join(d, "structural.json")) else None,
            "build_output_delta": bo,
            "build_output_delta_keys": bo_keys,
            "deck_changes": deck_delta(rows, (prev or {}).get("deck")),
        })

        if args.pool_query:
            import re as _re
            pat = _re.compile(args.pool_query, _re.IGNORECASE)
            delta["working_pool"] = [c for c in slim_pool
                                     if pat.search(c.get("oracle_text") or "")]
            delta["pool_query"] = args.pool_query
        elif args.with_pool:
            delta["working_pool"] = slim_pool

        leaked = set(DELTA_FORBIDDEN) & set(delta)
        if args.pool_query or args.with_pool:
            leaked -= {"working_pool"}
        assert not leaked, f"delta re-shipped a full artifact: {sorted(leaked)}"

        d_bytes = dump_json(delta, os.path.join(d, "grill_delta.json"), compact=True)
        base = delta["base_bundle_bytes"]
        cut = f"  ({100 * (base - d_bytes) // base}% smaller than grill_challenger.json)" if base else ""
        print(f"grill_delta.json       {d_bytes:>9,} bytes{cut}")
        print(f"build_output keys shipped: {bo_keys or '(none changed)'}")
        dc = delta["deck_changes"]
        print(f"deck changes: -{len(dc['removed'])} +{len(dc['added'])}, "
              f"{len(dc['qty_changed'])} qty change(s)")
        if "working_pool" in delta:
            print(f"  !! pool attached: {len(delta['working_pool'])} rows "
                  f"({'--pool-query' if args.pool_query else '--with-pool'})")
        print("excluded: working_pool, dossier, sweep, unchanged build_output keys")
        print("full bundles deliberately NOT rewritten — they are the snapshot this "
              "delta was computed against")
        print(f"validation: {validation[-1] if validation else '(none)'}")
        if val.returncode != 0:
            print("  !! Phase 5C is FAILING — the repair is not finished.")
        return 0

    if os.path.exists(os.path.join(d, "grill_challenger.json")):
        print("  !! overwriting an existing grill_challenger.json — if an approval round "
              "is in flight, this advances the snapshot its next delta diffs against.")

    proposer = dict(common)
    proposer["build_output_lite"] = {k: build_output.get(k) for k in PROPOSER_BO_KEYS
                                     if k in build_output}
    p_bytes = dump_json(proposer, os.path.join(d, "grill_proposer.json"), compact=True)

    dossier_path = os.path.join("cubes", cfg["cube_slug"], "dossier.json")
    dossier = load_json(dossier_path) if os.path.exists(dossier_path) else {}
    if not dossier.get("interaction_chains"):
        # An empty list plus its caveat is 300 bytes of "nothing here".
        dossier = {k: v for k, v in dossier.items()
                   if k not in ("interaction_chains", "chains_caveat", "chains_seeded_at")}

    challenger = dict(common)
    challenger.update({"build_output": build_output, "sweep": L("sweep.json"),
                       "working_pool": slim_pool, "dossier": dossier})
    c_bytes = dump_json(challenger, os.path.join(d, "grill_challenger.json"), compact=True)

    print(f"grill_proposer.json    {p_bytes:>9,} bytes   ({len(rows)} deck rows)")
    print(f"grill_challenger.json  {c_bytes:>9,} bytes   "
          f"({len(rows)} deck rows, {len(slim_pool)} pool rows)")
    print(f"pool fields dropped: {list(POOL_DROP)}")
    print(f"deck rows now carry: tags (fixes the accel_count recompute) + usable_as")
    print(f"validation: {validation[-1] if validation else '(none)'}")
    if val.returncode != 0:
        print("  !! Phase 5C is FAILING — do not run the grill until it passes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

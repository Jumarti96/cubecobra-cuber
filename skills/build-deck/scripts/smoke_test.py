"""Smoke test every phase script against all four supported formats.

Usage:
    python skills/build-deck/scripts/smoke_test.py --cube <slug> [--keep]

Builds a throwaway run per format under `_workspace/run-smoke-<format>/`, synthesises
a legal-shaped deck from the cube's own pool, and drives every script end to end.

This exists because the previous generation of per-run scripts hardcoded `DECK_SIZE =
40`, a cube slug, a pool-rules dict, a cube-specific land-name table and
`commander_cards=None`. Every one of those passes a 40-card run and silently produces
wrong output — or refuses to run at all — on any other format. A script directory
without this test is a liability, not an asset.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.getcwd())

from _common import FORMATS, is_land, load_json, run_dir, utf8  # noqa: E402

SCRIPTS = os.path.join("skills", "build-deck", "scripts")
ENV = {**os.environ, "PYTHONPATH": f".{os.pathsep}{SCRIPTS}", "PYTHONIOENCODING": "utf-8"}

RULES = {"base": "cube_mainboard",
         "multipliers": {"common": 2, "uncommon": 2, "rare": 1, "mythic": 1},
         "only_from": {}, "excluded": []}


def sh(script, *a):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *a],
                       capture_output=True, text=True, encoding="utf-8", env=ENV)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def synth_deck(pool, cfg, fmt):
    """Build a shape-legal deck: singleton for commander, up to the copy cap otherwise."""
    spec = FORMATS[fmt]
    singleton = spec["commanders"] > 0
    nonlands = [c for c in pool.values() if not is_land(c) and c.get("mana_cost")]
    nonlands.sort(key=lambda c: (float(c.get("cmc") or 0), c["name"]))

    commander = None
    if singleton:
        legends = [c for c in nonlands
                   if "legendary" in (c.get("type_line") or "").lower()
                   and "creature" in (c.get("type_line") or "").lower()]
        commander = legends[0]["name"] if legends else nonlands[0]["name"]

    identity = set(pool[commander].get("color_identity") or []) if commander else set()
    if not singleton:
        identity = {"B"}                       # a plain mono-black shell for 40/60-card

    usable = [c for c in nonlands
              if set(c.get("color_identity") or []) <= identity and c["name"] != commander]
    lands_n = round(spec["deck_size"] * 0.4)
    spells_n = spec["deck_size"] - lands_n - (1 if commander else 0)

    mb, used = [], 0
    cap = 1 if singleton else 2
    for c in usable:
        if used >= spells_n:
            break
        q = min(cap, spells_n - used)
        mb.append({"name": c["name"], "qty": q, "role": "threat"})
        used += q
    basic = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
    mb.append({"name": basic[sorted(identity)[0]], "qty": lands_n, "role": "land"})

    sb = []
    if spec["sideboard"]:
        left = spec["sideboard"]
        for c in usable[used:]:
            if left <= 0:
                break
            q = min(cap, left)
            # `when_to_board` — the canonical field per build.md step 7. An earlier
            # fixture wrote `answers` to match render_save.py, which hid the fact that
            # the script read the wrong key and rendered an empty column. Fixtures
            # follow the spec, never the implementation.
            sb.append({"name": c["name"], "qty": q, "role": "hate",
                       "when_to_board": "vs smoke decks"})
            left -= q

    return {"deck_name": f"smoke-{fmt}", "cube_id": cfg["cube_slug"], "format": fmt,
            "sideboard_size": spec["sideboard"], "core_colors": sorted(identity),
            "splash_colors": [], "splash_candidates": [],
            "mainboard": mb, "sideboard": sb}, commander


def main() -> int:
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--cube", required=True)
    ap.add_argument("--keep", action="store_true", help="do not delete the smoke runs")
    args = ap.parse_args()

    overall = 0
    for fmt in FORMATS:
        token = f"run-smoke-{fmt}"
        rd = run_dir(token)
        shutil.rmtree(rd, ignore_errors=True)
        os.makedirs(rd, exist_ok=True)   # deck dir deliberately NOT created
        print(f"\n=========== {fmt} ===========")

        meta = load_json(os.path.join("cubes", args.cube, "meta.json"))
        cfg = {"run_token": token, "cube_slug": args.cube, "short_id": meta["short_id"],
               "format": fmt, "card_pool_rules": RULES}
        with open(os.path.join(rd, "run_config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=1)

        rc, out = sh("build_pool.py", "--run", token)
        print(f"  build_pool            {'ok' if rc == 0 else 'FAIL'}")
        if rc:
            print(out); overall = 1; continue

        pool = {c["name"]: c for c in load_json(os.path.join(rd, "working_pool.json"))}
        deck, commander = synth_deck(pool, cfg, fmt)
        if commander:
            cfg["commander"] = [commander]
            with open(os.path.join(rd, "run_config.json"), "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=1)
            print(f"  commander             {commander}")
        # seed_sweep runs at Phase 5A, BEFORE deck.json exists at 5B — it is the first
        # thing to write into the per-deck directory on a real run. The dir is left
        # uncreated above so this asserts the scripts make it themselves; requiring the
        # orchestrator to mkdir it first is an instruction it can silently skip.
        pipeline = {"payoff": deck["mainboard"][0]["name"], "clusters": ["Aristocrats/Sacrifice"],
                    "core_colors": deck["core_colors"], "splash_colors": [],
                    "splash_candidates": []}
        with open(os.path.join(rd, "pipeline.json"), "w", encoding="utf-8") as f:
            json.dump(pipeline, f)
        rc, out = sh("seed_sweep.py", "--run", token, "--deck", "d1",
                     "--pipeline", os.path.join(rd, "pipeline.json"))
        made_dir = os.path.isdir(os.path.join(rd, "d1"))
        bands = next((l for l in out.splitlines() if l.startswith("bands")), out[:80])
        print(f"  seed_sweep            {'ok' if rc == 0 else 'FAIL'}  {bands}"
              f"   [created deck dir: {'yes' if made_dir else 'NO'}]")
        overall |= rc | int(not made_dir)
        if not made_dir:
            print(out[-500:])

        with open(os.path.join(rd, "d1", "deck.json"), "w", encoding="utf-8") as f:
            json.dump(deck, f, indent=1)

        # validate_build is expected to report size failures on a synthetic deck; what
        # must NOT happen is a crash, or check 1 asserting 40 on a non-40 format.
        rc, out = sh("validate_build.py", "--run", token, "--deck", "d1")
        size_line = next((l for l in out.splitlines() if "mainboard size" in l), "")
        crashed = "Traceback" in out
        expect = FORMATS[fmt]["deck_size"]
        right_target = f"vs {expect} expected" in size_line
        print(f"  validate_build        {'ok' if not crashed else 'CRASH'}  "
              f"[deck_size target {expect}: {'correct' if right_target else 'WRONG'}]")
        overall |= int(crashed or not right_target)

        rc, out = sh("land_math.py", "--run", token, "--deck", "d1")
        is_cmd = FORMATS[fmt]["commanders"] > 0
        said_na = "NOT APPLICABLE for commander" in out
        ok = rc == 0 and (said_na if is_cmd else not said_na)
        print(f"  land_math             {'ok' if ok else 'FAIL'}  "
              f"[{'defers to Burgess/Karsten' if is_cmd else 'land_target trace'}]")
        overall |= int(not ok)
        if not ok:
            print(out[-600:])

        # mana_audit exits nonzero when the DECK is bad. A synthetic fixture is
        # deliberately crude, so its PASS/FAIL verdict says nothing about the script.
        # What is under test: did it run, and did it take the right format branch?
        rc, out = sh("mana_audit.py", "--run", token, "--deck", "d1")
        apath = os.path.join(rd, "d1", "audit.json")
        ran = "Traceback" not in out and os.path.exists(apath)
        audit = load_json(apath) if ran else {}
        # Commander formats must average Burgess/Karsten and leave the trace null;
        # every other format must produce a land_target trace.
        cmd_ok = (audit.get("land_target_trace") is None) if is_cmd \
            else (audit.get("land_target_trace") is not None)
        ok = ran and cmd_ok
        print(f"  mana_audit            {'ok' if ok else 'FAIL'}  "
              f"[{'Burgess/Karsten, trace null' if is_cmd else 'land_target trace present'}"
              f"; deck verdict {audit.get('overall_status')} — fixture quality, not tested]")
        overall |= int(not ok)
        if not ok:
            print(out[-600:])

        checks = {"macro_archetype": "aggro", "thesis_turn": 6,
                  "role_counts": {"payoff": [{"qty": 4}]},
                  "coverage_declaration": {k: {"conceded": "smoke test"} for k in
                                           ("wide_boards", "single_large_threat",
                                            "noncreature_permanents", "stack", "graveyard")}}
        cp = os.path.join(rd, "checks.json")
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(checks, f)
        rc, out = sh("structural.py", "--run", token, "--deck", "d1", "--checks", cp)
        rep = load_json(os.path.join(rd, "d1", "structural.json")) if "Traceback" not in out else {}
        # The verdict must reach BOTH the printed line and the exit code. Reading the
        # wrong key made STATUS print None and the exit code stick at 0 — a HARD gate
        # that could never fail. Assert agreement, not merely absence of a traceback.
        vs = rep.get("overall_status")
        agrees = vs is not None and f"STATUS: {vs}" in out and rc == (1 if vs == "FAIL" else 0)
        print(f"  structural            {'ok' if agrees else 'FAIL'}  "
              f"[verdict {vs}, printed+exit agree: {'yes' if agrees else 'NO'}]")
        overall |= int(not agrees)

        # NEGATIVE FIXTURE — a coverage declaration naming a card that is not in the
        # deck must FAIL and must exit 1. A gate that passes everything is a bug, not
        # a success; this is the check whose absence let the broken exit path ship.
        bad = json.loads(json.dumps(checks))
        bad["coverage_declaration"]["graveyard"] = {"cards": ["Card That Does Not Exist"]}
        bp = os.path.join(rd, "checks_bad.json")
        with open(bp, "w", encoding="utf-8") as f:
            json.dump(bad, f)
        brc, bout = sh("structural.py", "--run", token, "--deck", "d1", "--checks", bp)
        caught = brc == 1 and "STATUS: FAIL" in bout
        print(f"  structural (bad fix.) {'ok' if caught else 'FAIL'}  "
              f"[phantom coverage card rejected + exit 1: {'yes' if caught else 'NO'}]")
        overall |= int(not caught)
        if not caught:
            print(f"      rc={brc}\n{bout[-400:]}")
        # restore the good report so later stages bundle a passing gate
        sh("structural.py", "--run", token, "--deck", "d1", "--checks", cp)

        bo = {"macro_archetype": "aggro", "deck_identity": "Smoke test deck.",
              "thesis_turn": 6, "default_role": "aggressor",
              "failure_modes": {m: {"mitigation": "smoke"} for m in
                                ("flood", "screw", "decapitation", "gas-out", "raced",
                                 "disruption-fizzle")},
              "restrictions_checklist": {"smoke": "PASS"}}
        with open(os.path.join(rd, "d1", "build_output.json"), "w", encoding="utf-8") as f:
            json.dump(bo, f)
        sweep = {"include_candidates": [], "considered_but_excluded": []}
        with open(os.path.join(rd, "d1", "sweep.json"), "w", encoding="utf-8") as f:
            json.dump(sweep, f)

        rc, out = sh("build_bundle.py", "--run", token, "--deck", "d1")
        sizes = [l for l in out.splitlines() if "grill_" in l]
        print(f"  build_bundle          {'ok' if rc == 0 else 'FAIL'}")
        for s in sizes:
            print(f"      {s.strip()}")
        overall |= rc
        if rc:
            print(out[-800:])

        # Phase 9 approval round. Runs on every format for free, and catches the two ways
        # --delta can silently stop paying for itself: re-shipping a full artifact, or
        # rewriting the snapshot it is supposed to diff against.
        full_p = os.path.join(rd, "d1", "grill_challenger.json")
        before = os.path.getsize(full_p) if os.path.exists(full_p) else 0
        rc, out = sh("build_bundle.py", "--run", token, "--deck", "d1", "--delta")
        delta_p = os.path.join(rd, "d1", "grill_delta.json")
        problems = []
        if rc:
            problems.append("nonzero exit")
        if not os.path.exists(delta_p):
            problems.append("no grill_delta.json")
        else:
            with open(delta_p, encoding="utf-8") as f:
                delta = json.load(f)
            leaked = [k for k in ("build_output", "dossier", "sweep", "working_pool")
                      if k in delta]
            if leaked:
                problems.append(f"re-shipped {leaked}")
            if not delta.get("deck"):
                problems.append("empty deck array")
            if os.path.getsize(delta_p) >= before:
                problems.append("not smaller than the full bundle")
        if before and os.path.getsize(full_p) != before:
            problems.append("--delta rewrote grill_challenger.json (snapshot destroyed)")
        print(f"  build_bundle --delta  {'ok' if not problems else 'FAIL: ' + '; '.join(problems)}")
        if problems:
            overall |= 1
            print(out[-800:])

        rc, out = sh("render_save.py", "--run", token, "--deck", "d1")
        print(f"  render_save           {'ok' if 'Traceback' not in out else 'CRASH'}")
        overall |= int("Traceback" in out)
        if "Traceback" in out:
            print(out[-800:])
        else:
            rc, out = sh("validate_analysis.py", "--run", token, "--deck", "d1")
            # A synthetic deck has no real analysis body; the header maths must still hold.
            hdr = [l for l in out.splitlines() if "header" in l or "FAIL" in l]
            print(f"  validate_analysis     {'headers ok' if rc == 0 else 'reported:'}")
            for h in hdr[:4]:
                print(f"      {h.strip()}")

        if not args.keep:
            shutil.rmtree(rd, ignore_errors=True)

    print("\n===========================================")
    print("SMOKE TEST:", "ALL FORMATS OK" if overall == 0 else "FAILURES PRESENT")
    return overall


if __name__ == "__main__":
    raise SystemExit(main())

"""Phase 6b — structural gate (curve / assembly / goldfish / coverage).

Usage:
    python skills/build-deck/scripts/structural.py --run <token> --deck deck1 \
        --checks <checks.json>

`checks.json`: {"macro_archetype": str, "thesis_turn": int,
                "role_counts": {...}, "coverage_declaration": {...}}

Thresholds live in cuber/deck_checks.py and are never re-derived here.

assembly and coverage are HARD gates: a failure is repaired and re-run, not
rationalised. curve and goldfish are WARN-tier — each flag gets one line in
build_output.structural_responses.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.getcwd())

from _common import (base_parser, dump_json, expand, load_config, load_deck,  # noqa: E402
                     load_json, load_pool, run_dir, utf8)

from cuber import deck_checks  # noqa: E402


def main() -> int:
    utf8()
    p = base_parser(__doc__ or "")
    p.add_argument("--checks", required=True, help="role_counts + coverage_declaration")
    args = p.parse_args()

    cfg = load_config(args.run)
    checks = load_json(args.checks)
    D = load_deck(args.run, args.deck)
    pool = load_pool(args.run)

    dossier_path = os.path.join("cubes", cfg["cube_slug"], "dossier.json")
    threat_profile = None
    if os.path.exists(dossier_path):
        threat_profile = load_json(dossier_path).get("threat_profile")

    report = deck_checks.run_structural_checks(
        expand(D["mainboard"], pool),
        checks["macro_archetype"],
        checks["thesis_turn"],
        checks["role_counts"],
        checks["coverage_declaration"],
        threat_profile=threat_profile,
        seed=0,
    )
    print(deck_checks.format_checks_report(report))
    dump_json(report, os.path.join(run_dir(args.run), args.deck, "structural.json"))

    # run_structural_checks returns the verdict as `overall_status` at the top level;
    # `status` is the key on each SUB-check (curve, assembly, goldfish, coverage). Reading
    # `status` here silently yielded None, so the exit code was always 0 and this HARD gate
    # could never fail. Do not "simplify" this back.
    status = report["overall_status"]
    print("\nSTATUS:", status)
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

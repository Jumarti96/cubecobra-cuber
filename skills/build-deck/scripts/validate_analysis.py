"""Phase 10 — re-parse analysis.md and assert it describes the deck it was built from.

Usage:
    python skills/build-deck/scripts/validate_analysis.py --run <token> --deck deck1
    python skills/build-deck/scripts/validate_analysis.py --run <token> --deck deck1 --saved

Without --saved it checks the workspace preview; with --saved it checks the file
written into cubes/<slug>/decks/<name>/.

Any mismatch is a HARD failure: regenerate analysis.md from the deck arrays. Never
hand-patch the output to make this agree — the whole point is that the prose cannot
drift from the list.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.getcwd())

from _common import base_parser, load_config, load_deck, run_dir, utf8  # noqa: E402

MODES = ["flood", "screw", "decapitation", "gas-out", "raced", "disruption-fizzle"]
SECTIONS = ("LANDS", "CREATURES", "INSTANTS & SORCERIES", "OTHER SPELLS")


def main() -> int:
    utf8()
    p = base_parser(__doc__ or "")
    p.add_argument("--saved", action="store_true")
    args = p.parse_args()

    cfg = load_config(args.run)
    D = load_deck(args.run, args.deck)
    path = (os.path.join("cubes", cfg["cube_slug"], "decks", D["deck_name"], "analysis.md")
            if args.saved
            else os.path.join(run_dir(args.run), args.deck, "analysis_preview.md"))
    txt = open(path, encoding="utf-8").read()

    mb_total = sum(c["qty"] for c in D["mainboard"])
    sb_total = sum(c["qty"] for c in D.get("sideboard", []))
    fails = []

    m = re.search(r"^## MAINBOARD \((\d+) spells \+ (\d+) lands = (\d+)\)", txt, re.M)
    if not m:
        fails.append("## MAINBOARD header missing or malformed")
    else:
        sp, la, to = map(int, m.groups())
        if sp + la != to:
            fails.append(f"MAINBOARD header arithmetic: {sp}+{la} != {to}")
        if to != mb_total:
            fails.append(f"MAINBOARD total {to} != deck.json {mb_total}")

    seen = 0
    for name, hdr, body in re.findall(
            r"^### (" + "|".join(map(re.escape, SECTIONS)) + r") \((\d+)\)\s*\n\s*```\n(.*?)\n```",
            txt, re.M | re.S):
        qty = sum(int(x) for x in re.findall(r"\bx(\d+)\b", body))
        seen += qty
        if qty != int(hdr):
            fails.append(f"### {name}: header {hdr} != summed qty {qty}")
    if seen != mb_total:
        fails.append(f"section totals {seen} != mainboard {mb_total}")

    m = re.search(r"^## SIDEBOARD \((\d+)\)\s*\n\s*```\n(.*?)\n```", txt, re.M | re.S)
    if sb_total and not m:
        fails.append("## SIDEBOARD section missing")
    elif m:
        qty = sum(int(x) for x in re.findall(r"\bx(\d+)\b", m.group(2)))
        if qty != int(m.group(1)):
            fails.append(f"SIDEBOARD header {m.group(1)} != summed qty {qty}")
        if qty != sb_total:
            fails.append(f"SIDEBOARD total {qty} != deck.json {sb_total}")

    if "scryfall" in txt.lower():
        fails.append("contains 'scryfall' — no external links are permitted")
    if re.search(r"\]\(https?://", txt):
        fails.append("contains an external markdown link")

    am = re.search(r"^## ANALYSIS\b(.*?)(?=^## |\Z)", txt, re.M | re.S)
    if not am:
        fails.append("## ANALYSIS section missing")
    else:
        body = am.group(1)
        if not re.search(r"^### DECK IDENTITY", body, re.M):
            fails.append("## ANALYSIS must open with ### DECK IDENTITY")
        fm = re.search(r"^### FAILURE MODES\b(.*?)(?=^### |\Z)", body, re.M | re.S)
        if not fm:
            fails.append("### FAILURE MODES missing from ## ANALYSIS")
        else:
            for mode in MODES:
                if mode not in fm.group(1):
                    fails.append(f"FAILURE MODES missing '{mode}'")

    print(f"=== ANALYSIS VALIDATION — {path} ===")
    if fails:
        for f in fails:
            print("  [FAIL]", f)
        print("RESULT: FAILURES PRESENT")
        return 1
    print(f"  [PASS] mainboard header + section sums ({seen} cards)")
    print(f"  [PASS] sideboard header + sum ({sb_total} cards)")
    print("  [PASS] no scryfall, no external links")
    print("  [PASS] ANALYSIS opens with DECK IDENTITY; all six failure modes present")
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

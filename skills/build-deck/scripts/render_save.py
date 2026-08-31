"""Phases 10-11 — render analysis.md and save the four deck files.

Usage:
    python skills/build-deck/scripts/render_save.py --run <token> --deck deck1
    python skills/build-deck/scripts/render_save.py --run <token> --deck deck1 --save

Without --save it writes <deck>/analysis_preview.md only, so the validator can run
before anything lands in the cube directory.

DIVISION OF LABOUR. This script emits every MECHANICAL section — the card tables and
their header counts, the structural report, the six-row failure-mode table, the
excluded-cards table, the mana audit, the restrictions checklist. The model supplies
only `build_output.analysis_body`: the DECK IDENTITY prose and the free-form
observations. Header counts are therefore COMPUTED from the deck arrays at render
time and cannot drift from the list, which is the failure this repeatedly hit when
the prose was authored by hand and the list changed underneath it.

Land annotations are derived from ORACLE TEXT, never a card-name lookup table — a
name table is locked to one cube.
"""
from __future__ import annotations

import datetime
import os
import sys

sys.path.insert(0, os.getcwd())

from _common import (BASICS, base_parser, color_str, dump_json, is_land,  # noqa: E402
                     land_note, load_config, load_deck, load_json, load_pool,
                     run_dir, utf8)

from cuber import deck_audit, deck_checks, exporter  # noqa: E402

RAR = {"common": "C", "uncommon": "U", "rare": "R", "mythic": "M"}
MODES = ["flood", "screw", "decapitation", "gas-out", "raced", "disruption-fizzle"]
CW_CARD, CW_ROLE = 44, 30


def w(s, n):
    return str(s if s is not None else "")[:n].ljust(n)


def main() -> int:
    utf8()
    p = base_parser(__doc__ or "")
    p.add_argument("--save", action="store_true")
    p.add_argument("--name", help="deck slug for cubes/<id>/decks/<name>/; "
                                  "defaults to deck.json's deck_name")
    args = p.parse_args()

    cfg = load_config(args.run)
    d = os.path.join(run_dir(args.run), args.deck)
    D = load_deck(args.run, args.deck)
    pool = load_pool(args.run)
    BO = load_json(os.path.join(d, "build_output.json"))
    AUDIT = load_json(os.path.join(d, "audit.json"))
    SWEEP = load_json(os.path.join(d, "sweep.json"))
    struct_path = os.path.join(d, "structural.json")
    STRUCT = load_json(struct_path) if os.path.exists(struct_path) else \
        BO.get("structural_checks")

    meta = load_json(os.path.join("cubes", cfg["cube_slug"], "meta.json"))
    short_id, slug = meta["short_id"], meta["slug"]
    built_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    card = lambda n: pool[n]
    mb, sb = D["mainboard"], D.get("sideboard", [])
    lands = [e for e in mb if is_land(card(e["name"]))]
    nonland = [e for e in mb if not is_land(card(e["name"]))]

    def bucket(e):
        tl = (card(e["name"]).get("type_line") or "").lower()
        if "creature" in tl:
            return "CREATURES"
        if "instant" in tl or "sorcery" in tl:
            return "INSTANTS & SORCERIES"
        return "OTHER SPELLS"

    groups = {"CREATURES": [], "INSTANTS & SORCERIES": [], "OTHER SPELLS": []}
    for e in nonland:
        groups[bucket(e)].append(e)
    for k in groups:
        groups[k].sort(key=lambda e: (float(card(e["name"]).get("cmc") or 0), e["name"]))
    lands.sort(key=lambda e: (e["name"] not in BASICS, e["name"]))

    n_lands = sum(e["qty"] for e in lands)
    n_spells = sum(e["qty"] for e in nonland)
    n_sb = sum(e["qty"] for e in sb)

    def land_block():
        out = []
        for e in lands:
            note = land_note(card(e["name"]))
            out.append(f"  {('x' + str(e['qty'])).ljust(4)} {w(e['name'], CW_CARD)} "
                       f"{note}".rstrip())
        return "\n".join(out)

    def table(entries):
        out = ["CMC  " + w("Card", CW_CARD) + " Qty   " + w("Color", 5) + " "
               + w("Role", CW_ROLE) + " Rar"]
        for e in entries:
            c = card(e["name"])
            out.append(f"{str(int(float(c.get('cmc') or 0))).rjust(3)}  "
                       f"{w(e['name'], CW_CARD)} {('x' + str(e['qty'])).ljust(5)} "
                       f"{w(color_str(c), 5)} {w(e.get('role'), CW_ROLE)} "
                       f"{RAR.get(c.get('rarity'), '?')}")
        return "\n".join(out)

    def sb_table():
        out = [w("Card", CW_CARD) + " Qty   " + w("Color", 5) + " "
               + w("Role / When to board in", 46) + " Rar"]
        for e in sorted(sb, key=lambda x: (float(card(x["name"]).get("cmc") or 0), x["name"])):
            c = card(e["name"])
            # `when_to_board` is the canonical field (build.md step 7, and what every
            # saved deck.json carries). `answers` is accepted as a fallback only.
            note = f"{e.get('role', '')}: {e.get('when_to_board') or e.get('answers') or ''}"
            out.append(f"{w(e['name'], CW_CARD)} {('x' + str(e['qty'])).ljust(5)} "
                       f"{w(color_str(c), 5)} {w(note, 46)} {RAR.get(c.get('rarity'), '?')}")
        return "\n".join(out)

    def failure_table():
        rows = ["| Mode | Verdict | Reasoning |", "|---|---|---|"]
        fm = BO.get("failure_modes") or {}
        for m in MODES:
            e = fm.get(m) or {}
            verdict = "mitigation" if "mitigation" in e else "accepted"
            txt = (e.get("mitigation") or e.get("accepted") or "(MISSING)")
            rows.append(f"| `{m}` | {verdict} | "
                        f"{txt.replace('|', chr(92) + '|').replace(chr(10), ' ')} |")
        return "\n".join(rows)

    def excluded_table():
        rows = ["| Card(s) | Reason |", "|---|---|"]
        for e in SWEEP.get("considered_but_excluded", []):
            if not e.get("notable"):
                continue
            names = ", ".join(e.get("cards") or [e.get("card", "?")])
            rows.append(f"| {names} | {e['reason'].replace('|', chr(92) + '|')} |")
        return "\n".join(rows)

    checks_report = deck_checks.format_checks_report(STRUCT) if STRUCT else "(not run)"
    audit_report = deck_audit.format_audit_report(AUDIT)
    status = ("PASS" if "PASS" in audit_report.splitlines()[0]
              else "WARN" if "WARN" in audit_report.splitlines()[0] else "FAIL")

    parts = ["### DECK IDENTITY\n\n" + (BO.get("deck_identity") or "").strip()]
    body = (BO.get("analysis_body") or "").strip()
    if body:
        parts.append(body)
    parts.append("### STRUCTURAL CHECKS\n\n```\n" + checks_report + "\n```")
    sr = BO.get("structural_responses") or []
    parts.append("\n".join(f"- {x}" for x in sr) if sr else
                 "_No WARN-tier structural flags were raised._")
    parts.append("### FAILURE MODES\n\n" + failure_table())
    parts.append("### CARDS CONSIDERED BUT EXCLUDED\n\n" + excluded_table())
    analysis_body = "\n\n".join(parts)

    restr = BO.get("restrictions_checklist") or {}
    restr_txt = "\n".join(
        (f"[{'PASS' if 'PASS' in str(v) else 'INFO'}] {k}: {v}" if not isinstance(v, dict)
         else f"       {k}: {v}") for k, v in restr.items())

    md = [f"## MAINBOARD ({n_spells} spells + {n_lands} lands = {n_spells + n_lands})\n"]
    if cfg.get("commander"):
        md.append("### COMMANDER\n\n```\n"
                  + "\n".join(f"  {n}" for n in cfg["commander"]) + "\n```\n")
    md.append(f"### LANDS ({n_lands})\n\n```\n{land_block()}\n```\n")
    for k in ("CREATURES", "INSTANTS & SORCERIES", "OTHER SPELLS"):
        if groups[k]:
            md.append(f"### {k} ({sum(e['qty'] for e in groups[k])})\n\n"
                      f"```\n{table(groups[k])}\n```\n")
    if sb:
        md.append(f"## SIDEBOARD ({n_sb})\n\n```\n{sb_table()}\n```\n")
    md.append(f"## ANALYSIS\n\n{analysis_body}\n")
    md.append(f"## MANA AUDIT: {status}\n\n```\n{audit_report}\n```\n")
    md.append(f"## RESTRICTIONS COMPLIANCE\n\n```\n{restr_txt}\n```")
    text = "\n".join(md)

    with open(os.path.join(d, "analysis_preview.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text if not args.save else f"rendered {len(text):,} chars")

    if not args.save:
        return 0

    name = args.name or D["deck_name"]

    # export_meta is built HERE, at save time, for the ~50 cards in this deck — not at
    # Phase 0 for all several hundred in the pool. Its only consumer is the TSV writer
    # below; a whole-pool copy is ~66 KB of which ~10 KB is ever read, carried through
    # the entire run. Re-opening enriched.json once at the end is cheaper.
    EXPORT_KEYS = ("set", "collector_number", "image_url", "image_back_url")
    emp = os.path.join(run_dir(args.run), "export_meta.json")
    wanted = {e["name"] for e in mb} | {e["name"] for e in sb}
    export_meta = load_json(emp) if os.path.exists(emp) else {}
    if not wanted <= set(export_meta):
        enriched = load_json(os.path.join("cubes", slug, "enriched.json"))
        rows = enriched.get("cards", enriched) if isinstance(enriched, dict) else enriched
        if isinstance(rows, dict):
            rows = list(rows.values())
        for c in rows:
            if c.get("name") in wanted:
                export_meta[c["name"]] = {k: c.get(k) for k in EXPORT_KEYS}
        # Synthesized basics are not in enriched.json; blank fields, the TSV tolerates them.
        for n in wanted - set(export_meta):
            export_meta[n] = {k: None for k in EXPORT_KEYS}
        dump_json(export_meta, emp)
        print(f"export_meta.json  {len(export_meta)} deck cards "
              f"(built at save, not Phase 0)")

    def cdicts(entries, board):
        out = []
        for e in entries:
            c, em = card(e["name"]), export_meta.get(e["name"], {})
            for _ in range(e["qty"]):
                out.append({**{k: c.get(k) for k in
                               ("name", "oracle_text", "mana_cost", "colors",
                                "color_identity", "cmc", "type_line", "rarity",
                                "power", "toughness", "tags")},
                            "set": em.get("set"), "collector_number": em.get("collector_number"),
                            "image_url": em.get("image_url"),
                            "image_back_url": em.get("image_back_url"),
                            "role": e.get("role"), "board": board})
        return out

    main_cards, side_cards = cdicts(mb, "mainboard"), cdicts(sb, "sideboard")
    folder = os.path.join("cubes", slug, "decks", name)
    os.makedirs(folder, exist_ok=True)

    dump_json({"deck_name": name, "cube_id": short_id, "cube_slug": slug,
               "built_at": built_at, "format": D["format"],
               "strategy": BO.get("macro_archetype"),
               "colors": "".join(D.get("core_colors") or []),
               "identity": BO.get("deck_identity"),
               "restrictions": restr, "commander": cfg.get("commander"),
               "mana_audit": {k: AUDIT.get(k) for k in
                              ("land_count", "recommended_land_count", "land_count_status",
                               "ramp_count", "cantrip_count", "accel_count",
                               "land_target_trace", "avg_cmc", "pip_demand",
                               "land_color_production", "color_balance_status",
                               "color_balance_per_color", "overall_status")},
               "mainboard": main_cards, "sideboard": side_cards},
              os.path.join(folder, "deck.json"))

    COLS = ["name", "CMC", "Type", "Color", "Set", "Collector Number", "Rarity",
            "Color Category", "status", "Finish", "board", "maybeboard", "image URL",
            "image Back URL", "tags", "Notes", "MTGO ID", "Custom", "Voucher"]
    rows = ["\t".join(COLS)]
    for c in main_cards + side_cards:
        tags = ";".join(c.get("tags") or [] if isinstance(c.get("tags"), list) else [])
        rows.append("\t".join(str(x) if x is not None else "" for x in [
            c["name"], int(float(c.get("cmc") or 0)), c.get("type_line"), color_str(c),
            c.get("set"), c.get("collector_number"), (c.get("rarity") or "").capitalize(),
            "", "Not Owned", "Non-Foil", c["board"], "false", c.get("image_url"),
            c.get("image_back_url"), tags, "", "", "", ""]))
    with open(os.path.join(folder, "deck.tsv"), "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")

    class _C:
        __slots__ = ("name", "set_code", "type_line")

        def __init__(self, src):
            self.name = src["name"]
            self.set_code = src.get("set") or ""
            self.type_line = src.get("type_line") or ""

    exporter.write_mwdeck([_C(c) for c in main_cards], [_C(c) for c in side_cards],
                          short_id, name)
    exporter.write_deck_analysis_md(text, short_id, name, {
        "deck_name": name, "cube_id": short_id, "cube_slug": slug,
        "colors": "".join(D.get("core_colors") or []), "format": D["format"],
        "built_at": built_at, "mana_audit_status": status, "restrictions_status": "PASS"})

    print("\nSaved:")
    for f in ("deck.json", "deck.tsv", "deck.mwDeck", "analysis.md"):
        pth = os.path.join(folder, f)
        print(f"  {pth}   {'OK' if os.path.exists(pth) else 'MISSING'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

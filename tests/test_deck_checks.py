import sys
import os

# Add parent to path so we can import cuber modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cuber import deck_checks as dch


# ── fixtures ──────────────────────────────────────────────────────────────────

def card(name, type_line="Creature — Human", mana_cost="{1}{R}", cmc=2,
         oracle_text="", colors=None, color_identity=None):
    return {
        "name": name,
        "type_line": type_line,
        "mana_cost": mana_cost,
        "cmc": cmc,
        "oracle_text": oracle_text,
        "colors": colors or ["R"],
        "color_identity": color_identity or ["R"],
    }


def mountain(n=1):
    return [card(f"Mountain {i}", type_line="Basic Land — Mountain", mana_cost="",
                 cmc=0, oracle_text="({T}: Add {R}.)", colors=[], color_identity=[])
            for i in range(n)]


def island(n=1):
    return [card(f"Island {i}", type_line="Basic Land — Island", mana_cost="",
                 cmc=0, oracle_text="({T}: Add {U}.)", colors=[], color_identity=[])
            for i in range(n)]


def red_drops(n, mv, name_prefix="Bear"):
    cost = "{R}" if mv == 1 else "{" + str(mv - 1) + "}{R}"
    return [card(f"{name_prefix} {mv}-{i}", mana_cost=cost, cmc=mv) for i in range(n)]


# ── p_at_least_one ────────────────────────────────────────────────────────────

def test_p_at_least_one_matches_methodology_table():
    # 10% of deck, 10 cards seen (turn 3 on the draw) → ~65%
    p = dch.p_at_least_one(4, 40, 10)
    assert abs(p - 0.6513) < 0.001, p


def test_p_at_least_one_zero_copies():
    assert dch.p_at_least_one(0, 40, 10) == 0.0


# ── assembly_check ────────────────────────────────────────────────────────────

def test_assembly_check_passes_at_critical_mass():
    rep = dch.assembly_check(40, {"payoff": 6, "enabler": 8}, thesis_turn=3)
    assert rep["cards_seen"] == 10  # 7 + thesis_turn, on the draw
    assert rep["status"] == "PASS", rep
    assert rep["roles"]["payoff"]["p"] > 0.75
    assert rep["roles"]["enabler"]["p"] > 0.75


def test_assembly_check_fails_below_critical_mass():
    # 3 copies in 40, seen-10: p ≈ 0.54 < 0.75 → hard FAIL
    rep = dch.assembly_check(40, {"payoff": 3}, thesis_turn=3)
    assert rep["status"] == "FAIL", rep
    assert rep["roles"]["payoff"]["status"] == "FAIL"


# ── curve_check ───────────────────────────────────────────────────────────────

def aggro_deck_good():
    # 24 nonland: 6×1, 8×2, 6×3, 4×4 → 25% / 33% / 25% / 17%
    deck = red_drops(6, 1) + red_drops(8, 2) + red_drops(6, 3) + red_drops(4, 4)
    return deck + mountain(16)


def test_curve_check_pass_and_ignores_lands():
    rep = dch.curve_check(aggro_deck_good(), "Aggro")
    assert rep["nonland_count"] == 24
    assert rep["status"] == "PASS", rep["flags"]


def test_curve_check_warns_on_two_drop_shortage():
    # 24 nonland with only 2 two-drops (8%) — Aggro wants ≥ 25% at MV 2
    deck = red_drops(10, 1) + red_drops(2, 2) + red_drops(8, 3) + red_drops(4, 4) + mountain(16)
    rep = dch.curve_check(deck, "Aggro")
    assert rep["status"] == "WARN", rep
    assert any("MV 2" in f["rule"] for f in rep["flags"]), rep["flags"]


def test_curve_check_top_end_rule_uses_thesis_turn():
    # Combo has no shape bands; 5 of 20 nonland above thesis turn 4 (25% > 10%) → WARN
    deck = red_drops(15, 2) + red_drops(5, 6) + mountain(14)
    rep = dch.curve_check(deck, "Combo", thesis_turn=4)
    assert rep["status"] == "WARN", rep
    assert any("thesis" in f["rule"].lower() for f in rep["flags"]), rep["flags"]


def test_curve_check_never_hard_fails():
    deck = red_drops(20, 7) + mountain(16)  # absurd curve, still only WARN
    rep = dch.curve_check(deck, "Aggro", thesis_turn=3)
    assert rep["status"] == "WARN"


# ── goldfish_sim ──────────────────────────────────────────────────────────────

def test_goldfish_sim_perfect_red_deck_passes():
    deck = red_drops(23, 1) + mountain(17)
    rep = dch.goldfish_sim(deck, n_hands=1000, seed=7)
    # keepable = P(2–5 lands in 7) ≈ 0.878 for 17/40 lands
    assert 0.83 < rep["keepable_rate"] < 0.93, rep["keepable_rate"]
    assert rep["status"] == "PASS"
    assert rep["play_by_turn"][1] > 0.9


def test_goldfish_sim_all_lands_deck_warns():
    rep = dch.goldfish_sim(mountain(40), n_hands=200, seed=7)
    assert rep["keepable_rate"] == 0.0
    assert rep["status"] == "WARN"


def test_goldfish_sim_castability_is_color_aware():
    # Islands cannot pay {G}: no hand has a castable early play
    green = [card(f"Elf {i}", mana_cost="{G}", cmc=1, colors=["G"], color_identity=["G"])
             for i in range(23)]
    rep = dch.goldfish_sim(green + island(17), n_hands=200, seed=7)
    assert rep["keepable_rate"] == 0.0, rep["keepable_rate"]


def test_goldfish_sim_is_deterministic():
    deck = red_drops(23, 1) + mountain(17)
    a = dch.goldfish_sim(deck, n_hands=300, seed=42)
    b = dch.goldfish_sim(deck, n_hands=300, seed=42)
    assert a == b


# ── answer_coverage ───────────────────────────────────────────────────────────

def full_declaration(mainboard):
    bolt = mainboard[0]["name"]
    return {
        "wide_boards": {"cards": [bolt]},
        "single_large_threat": {"cards": [bolt]},
        "noncreature_permanents": {"conceded": "mono-red pool has no enchantment removal"},
        "stack": {"conceded": "no counterspells in R; racing instead"},
        "graveyard": {"cards": [bolt]},
    }


def test_answer_coverage_pass():
    mb = red_drops(24, 2) + mountain(16)
    rep = dch.answer_coverage(mb, full_declaration(mb))
    assert rep["status"] == "PASS", rep["flags"]


def test_answer_coverage_missing_class_fails():
    mb = red_drops(24, 2) + mountain(16)
    decl = full_declaration(mb)
    del decl["graveyard"]
    rep = dch.answer_coverage(mb, decl)
    assert rep["status"] == "FAIL"
    assert any("graveyard" in f["detail"] for f in rep["flags"]), rep["flags"]


def test_answer_coverage_phantom_card_fails():
    mb = red_drops(24, 2) + mountain(16)
    decl = full_declaration(mb)
    decl["wide_boards"] = {"cards": ["Not In Deck"]}
    rep = dch.answer_coverage(mb, decl)
    assert rep["status"] == "FAIL"
    assert any("Not In Deck" in f["detail"] for f in rep["flags"]), rep["flags"]


def test_answer_coverage_empty_concession_fails():
    mb = red_drops(24, 2) + mountain(16)
    decl = full_declaration(mb)
    decl["stack"] = {"conceded": ""}
    rep = dch.answer_coverage(mb, decl)
    assert rep["status"] == "FAIL"


def test_answer_coverage_unknown_class_fails():
    mb = red_drops(24, 2) + mountain(16)
    decl = full_declaration(mb)
    decl["lifegain"] = {"cards": [mb[0]["name"]]}
    rep = dch.answer_coverage(mb, decl)
    assert rep["status"] == "FAIL"


# ── aggregator + report ───────────────────────────────────────────────────────

def test_run_structural_checks_overall_tiers():
    deck = aggro_deck_good()
    mb = deck
    decl = full_declaration(mb)
    ok = dch.run_structural_checks(
        deck, "Aggro", thesis_turn=5, role_counts={"payoff": 8, "enabler": 10},
        coverage_declaration=decl, n_hands=300, seed=7)
    assert ok["overall_status"] in ("PASS", "WARN")  # goldfish/curve may WARN, never FAIL

    bad = dch.run_structural_checks(
        deck, "Aggro", thesis_turn=5, role_counts={"payoff": 1},
        coverage_declaration=decl, n_hands=300, seed=7)
    assert bad["overall_status"] == "FAIL"  # assembly is a hard gate


def test_format_checks_report_mentions_sections():
    deck = aggro_deck_good()
    rep = dch.run_structural_checks(
        deck, "Aggro", thesis_turn=5, role_counts={"payoff": 8},
        coverage_declaration=full_declaration(deck), n_hands=300, seed=7)
    text = dch.format_checks_report(rep)
    for token in ("Structural Checks", "Curve", "Assembly", "Goldfish", "Coverage"):
        assert token in text, token

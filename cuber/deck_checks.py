"""Structural deck checks distilled from the deck-building methodology: curve shape,
critical-mass (assembly) math, goldfish/keepability simulation, and answer coverage.

Gate tiers (Phase 6b of /build-deck):
  - `assembly_check` and `answer_coverage` are HARD gates — a FAIL blocks the build.
  - `curve_check` and `goldfish_sim` are WARN-tier — a threshold miss requires a recorded
    response in build_output, never a forced rebuild.

Every function follows the `deck_audit` pattern: pure, takes deck-card dicts, returns a
report dict with a `status` key; `format_checks_report` renders the aggregate.

A "deck card" is a dict with at least `name`, `type_line`, `mana_cost`, `cmc`,
`oracle_text`, `colors` — one dict per physical copy (expand `qty` before calling).
"""

from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional, Sequence

Card = Dict[str, Any]

_PIP_RE = re.compile(r"\{([WUBRG])\}")
_ADD_ANY_RE = re.compile(
    r"Add (?:one mana of any color|[a-z]+ mana of any color|mana of any (?:one )?color)",
    re.IGNORECASE,
)
_BASIC_TYPE_TO_COLOR = {
    "Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G",
}

# The five threat classes a maindeck coverage declaration must address (methodology
# Phase 5), keyed to `dossier.threat_profile` vocabulary.
THREAT_CLASSES = (
    "wide_boards",
    "single_large_threat",
    "noncreature_permanents",
    "stack",
    "graveyard",
)


def _is_land(c: Card) -> bool:
    return "land" in (c.get("type_line") or "").lower()


# ── critical-mass math ────────────────────────────────────────────────────────

def p_at_least_one(copies: int, deck_size: int, cards_seen: int) -> float:
    """P(≥1 of `copies` functional copies seen in `cards_seen` cards): 1 − (1 − c/N)^n.

    The methodology's redundancy table (7 cards = opening hand, ~10 = turn 3,
    ~13 = turn 6) is this formula with cards_seen = 7 + turn, on the draw.
    """
    if copies <= 0 or deck_size <= 0:
        return 0.0
    return 1.0 - (1.0 - copies / deck_size) ** cards_seen


def assembly_check(
    deck_size: int,
    role_counts: Dict[str, int],
    thesis_turn: int,
    threshold: float = 0.75,
) -> Dict[str, Any]:
    """HARD gate: every engine role must be seen with p ≥ `threshold` by the thesis turn.

    `role_counts` maps role name (e.g. "payoff", "enabler") to its functional-copy count
    in the deck. cards_seen = 7 + thesis_turn (opening hand plus one draw per turn, on
    the draw — the convention the methodology's worked table uses).
    """
    cards_seen = 7 + thesis_turn
    roles: Dict[str, Any] = {}
    worst = "PASS"
    for role, count in role_counts.items():
        p = p_at_least_one(count, deck_size, cards_seen)
        status = "PASS" if p >= threshold else "FAIL"
        if status == "FAIL":
            worst = "FAIL"
        roles[role] = {"count": count, "p": round(p, 4), "status": status}
    return {
        "deck_size": deck_size,
        "thesis_turn": thesis_turn,
        "cards_seen": cards_seen,
        "threshold": threshold,
        "roles": roles,
        "status": worst,
    }


# ── curve shape (WARN-tier) ───────────────────────────────────────────────────

# Bands are shares of NONLAND cards, mapped from the methodology's curve shapes onto
# the skill's five macro-archetypes. `mv_max: None` means unbounded above.
# All misses are WARN — curve shape is a heuristic, not arithmetic.
CURVE_BANDS: Dict[str, List[Dict[str, Any]]] = {
    "Aggro": [
        {"rule": "MV 1 share", "mv_min": 1, "mv_max": 1, "min_share": 0.15},
        {"rule": "MV 2 share", "mv_min": 2, "mv_max": 2, "min_share": 0.25},
        {"rule": "MV 4+ share", "mv_min": 4, "mv_max": None, "max_share": 0.20},
    ],
    "Tempo": [
        {"rule": "MV 2 share", "mv_min": 2, "mv_max": 2, "min_share": 0.20},
        {"rule": "MV 4+ share", "mv_min": 4, "mv_max": None, "max_share": 0.30},
    ],
    "Midrange": [
        {"rule": "MV 2 share", "mv_min": 2, "mv_max": 2, "min_share": 0.15},
        {"rule": "MV 6+ share", "mv_min": 6, "mv_max": None, "max_share": 0.10},
    ],
    "Control": [
        {"rule": "MV 0-2 share", "mv_min": 0, "mv_max": 2, "min_share": 0.25},
    ],
    "Combo": [],  # engine-driven curves; only the thesis-turn top-end rule applies
}

# Share of nonland cards above the thesis turn's MV that triggers the top-end warning.
TOP_END_MAX_SHARE = 0.10


def curve_check(
    deck_cards: Sequence[Card],
    macro_archetype: str,
    thesis_turn: Optional[int] = None,
) -> Dict[str, Any]:
    """WARN-tier: nonland MV distribution vs the archetype's bands, plus the top-end
    rule (share of nonland cards with MV > thesis_turn must stay ≤ TOP_END_MAX_SHARE).

    Never returns FAIL: curve bands are heuristics; a miss demands a recorded response,
    not a rebuild.
    """
    nonland = [c for c in deck_cards if not _is_land(c)]
    n = len(nonland)
    dist: Dict[int, int] = {}
    for c in nonland:
        mv = int(c.get("cmc") or 0)
        dist[mv] = dist.get(mv, 0) + 1

    flags: List[Dict[str, Any]] = []
    for band in CURVE_BANDS.get(macro_archetype, []):
        lo, hi = band["mv_min"], band["mv_max"]
        count = sum(v for mv, v in dist.items()
                    if mv >= lo and (hi is None or mv <= hi))
        share = count / n if n else 0.0
        if "min_share" in band and share < band["min_share"]:
            flags.append({
                "rule": band["rule"],
                "detail": f"share {share:.0%} below band minimum {band['min_share']:.0%}",
            })
        if "max_share" in band and share > band["max_share"]:
            flags.append({
                "rule": band["rule"],
                "detail": f"share {share:.0%} above band maximum {band['max_share']:.0%}",
            })

    if thesis_turn is not None and n:
        above = sum(v for mv, v in dist.items() if mv > thesis_turn)
        share = above / n
        if share > TOP_END_MAX_SHARE:
            flags.append({
                "rule": "Above thesis turn",
                "detail": f"share of nonland cards with MV > {thesis_turn} is "
                          f"{share:.0%} (max {TOP_END_MAX_SHARE:.0%})",
            })

    return {
        "archetype": macro_archetype,
        "nonland_count": n,
        "distribution": {str(k): v for k, v in sorted(dist.items())},
        "flags": flags,
        "status": "WARN" if flags else "PASS",
    }


# ── goldfish / keepability simulation (WARN-tier) ─────────────────────────────

KEEPABLE_THRESHOLD = 0.80


def _land_produces(c: Card) -> set:
    """Colors a land can add: basic land types in the type line, explicit {X} adds in
    oracle text, and any-color text (counts for all five)."""
    colors: set = set()
    tl = c.get("type_line") or ""
    for basic, col in _BASIC_TYPE_TO_COLOR.items():
        if basic in tl:
            colors.add(col)
    oracle = c.get("oracle_text") or ""
    for line in oracle.splitlines():
        if "add" in line.lower():
            colors.update(_PIP_RE.findall(line))
    if _ADD_ANY_RE.search(oracle):
        colors.update("WUBRG")
    return colors


def _castable(c: Card, lands: Sequence[Card], max_mv: int) -> bool:
    """Documented heuristic: castable if MV ≤ max_mv AND each colored-pip requirement is
    met by at least that many lands producing the color. Generic mana is assumed payable
    when the MV bound holds. Multi-color multi-pip costs are checked per color
    independently (a slight overcount, accepted for a WARN-tier signal)."""
    mv = int(c.get("cmc") or 0)
    if mv > max_mv:
        return False
    pips: Dict[str, int] = {}
    for p in _PIP_RE.findall(c.get("mana_cost") or ""):
        pips[p] = pips.get(p, 0) + 1
    for color, need in pips.items():
        have = sum(1 for l in lands if color in _land_produces(l))
        if have < need:
            return False
    return True


def goldfish_sim(
    deck_cards: Sequence[Card],
    n_hands: int = 1000,
    seed: int = 0,
) -> Dict[str, Any]:
    """WARN-tier seeded Monte Carlo over opening hands (methodology Phase 8, mechanized).

    Per simulated game, 10 cards are drawn (7-card hand + 3 turns of draws, on the draw):
      - keepable: hand has 2–5 lands AND at least one nonland with MV ≤ 3 castable
        color-wise off the hand's lands with MV ≤ lands_in_hand + 1.
      - turn3_land_rate: ≥3 lands among the first 10 cards.
      - play_by_turn[t]: among the first 7+t cards, a nonland with MV ≤ t is castable
        off the lands seen so far (t = 1..3).

    Status is WARN when keepable_rate < KEEPABLE_THRESHOLD, else PASS. Deterministic
    for a given (deck order, n_hands, seed).
    """
    rng = random.Random(seed)
    deck = list(deck_cards)
    keepable = 0
    turn3_lands = 0
    plays = {1: 0, 2: 0, 3: 0}

    for _ in range(n_hands):
        drawn = rng.sample(deck, min(10, len(deck)))
        hand = drawn[:7]
        hand_lands = [c for c in hand if _is_land(c)]
        n_lands = len(hand_lands)
        if 2 <= n_lands <= 5:
            max_mv = min(3, n_lands + 1)
            if any(_castable(c, hand_lands, max_mv)
                   for c in hand if not _is_land(c)):
                keepable += 1
        if sum(1 for c in drawn if _is_land(c)) >= 3:
            turn3_lands += 1
        for t in (1, 2, 3):
            seen = drawn[:7 + t]
            lands_seen = [c for c in seen if _is_land(c)]
            max_mv = min(t, len(lands_seen))
            if max_mv and any(_castable(c, lands_seen, max_mv)
                              for c in seen if not _is_land(c)):
                plays[t] += 1

    rate = keepable / n_hands
    return {
        "n_hands": n_hands,
        "seed": seed,
        "keepable_rate": round(rate, 4),
        "keepable_threshold": KEEPABLE_THRESHOLD,
        "turn3_land_rate": round(turn3_lands / n_hands, 4),
        "play_by_turn": {t: round(v / n_hands, 4) for t, v in plays.items()},
        "status": "PASS" if rate >= KEEPABLE_THRESHOLD else "WARN",
    }


# ── answer coverage (HARD gate) ───────────────────────────────────────────────

def answer_coverage(
    mainboard: Sequence[Card],
    coverage_declaration: Dict[str, Any],
    threat_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """HARD gate on the coverage declaration's completeness — mechanical checks only.

    `coverage_declaration` maps each THREAT_CLASSES entry to either
    `{"cards": [mainboard names]}` or `{"conceded": "<one-line mechanism reason>"}`.
    Checks: every class present, no unknown classes, named cards exist in the mainboard,
    card lists non-empty, concessions carry a non-empty reason. Whether the oracle text
    actually supports each claim stays with the Challenger (checks 2/5).

    `threat_profile` is advisory context only; it is echoed into the report untouched.
    """
    names = {c.get("name") for c in mainboard}
    flags: List[Dict[str, Any]] = []
    classes: Dict[str, Any] = {}

    for cls in THREAT_CLASSES:
        entry = coverage_declaration.get(cls)
        if entry is None:
            flags.append({"rule": "missing class",
                          "detail": f"no declaration for threat class '{cls}'"})
            classes[cls] = {"status": "FAIL"}
            continue
        if "cards" in entry:
            cards = entry.get("cards") or []
            missing = [n for n in cards if n not in names]
            if not cards:
                flags.append({"rule": "empty answer list",
                              "detail": f"'{cls}' declares cards but names none"})
                classes[cls] = {"status": "FAIL", "cards": cards}
            elif missing:
                flags.append({"rule": "phantom answer",
                              "detail": f"'{cls}' names cards not in the mainboard: "
                                        + ", ".join(missing)})
                classes[cls] = {"status": "FAIL", "cards": cards, "missing": missing}
            else:
                classes[cls] = {"status": "OK", "cards": cards}
        elif "conceded" in entry:
            reason = (entry.get("conceded") or "").strip()
            if not reason:
                flags.append({"rule": "empty concession",
                              "detail": f"'{cls}' is conceded without a reason"})
                classes[cls] = {"status": "FAIL", "conceded": ""}
            else:
                classes[cls] = {"status": "CONCEDED", "conceded": reason}
        else:
            flags.append({"rule": "malformed entry",
                          "detail": f"'{cls}' has neither 'cards' nor 'conceded'"})
            classes[cls] = {"status": "FAIL"}

    for cls in coverage_declaration:
        if cls not in THREAT_CLASSES:
            flags.append({"rule": "unknown class",
                          "detail": f"'{cls}' is not a recognized threat class"})

    return {
        "classes": classes,
        "flags": flags,
        "threat_profile": threat_profile,
        "status": "FAIL" if flags else "PASS",
    }


# ── aggregator + report ───────────────────────────────────────────────────────

def run_structural_checks(
    deck_cards: Sequence[Card],
    macro_archetype: str,
    thesis_turn: int,
    role_counts: Dict[str, int],
    coverage_declaration: Dict[str, Any],
    threat_profile: Optional[Dict[str, Any]] = None,
    n_hands: int = 1000,
    seed: int = 0,
) -> Dict[str, Any]:
    """Run all four structural checks and tier the overall status.

    FAIL only from the hard gates (assembly, coverage); WARN from the heuristic
    checks (curve, goldfish); PASS otherwise.
    """
    mainboard = list(deck_cards)
    curve = curve_check(mainboard, macro_archetype, thesis_turn=thesis_turn)
    assembly = assembly_check(len(mainboard), role_counts, thesis_turn)
    goldfish = goldfish_sim(mainboard, n_hands=n_hands, seed=seed)
    coverage = answer_coverage(mainboard, coverage_declaration, threat_profile)

    if assembly["status"] == "FAIL" or coverage["status"] == "FAIL":
        overall = "FAIL"
    elif curve["status"] == "WARN" or goldfish["status"] == "WARN":
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "curve": curve,
        "assembly": assembly,
        "goldfish": goldfish,
        "coverage": coverage,
        "overall_status": overall,
    }


def format_checks_report(report: Dict[str, Any]) -> str:
    """Human-readable rendering of a `run_structural_checks` report."""
    curve = report["curve"]
    assembly = report["assembly"]
    goldfish = report["goldfish"]
    coverage = report["coverage"]

    lines = [
        f"── Structural Checks: {report['overall_status']} {'─' * 34}",
        f"Curve ({curve['archetype']}):  [{curve['status']}]",
    ]
    dist = "  ".join(f"{mv}:{n}" for mv, n in curve["distribution"].items())
    lines.append(f"  MV distribution ({curve['nonland_count']} nonland):  {dist}")
    for f in curve["flags"]:
        lines.append(f"  WARN  {f['rule']}: {f['detail']}")

    lines.append(
        f"Assembly (thesis turn {assembly['thesis_turn']}, "
        f"{assembly['cards_seen']} cards seen):  [{assembly['status']}]"
    )
    for role, info in assembly["roles"].items():
        lines.append(
            f"  {info['status']:4}  {role}: {info['count']} copies → "
            f"p={info['p']:.2f} (need ≥ {assembly['threshold']:.2f})"
        )

    lines.append(
        f"Goldfish ({goldfish['n_hands']} hands, seed {goldfish['seed']}):  "
        f"[{goldfish['status']}]"
    )
    lines.append(
        f"  keepable {goldfish['keepable_rate']:.0%} "
        f"(need ≥ {goldfish['keepable_threshold']:.0%})   "
        f"3 lands by turn 3: {goldfish['turn3_land_rate']:.0%}"
    )
    lines.append(
        "  play by turn: "
        + "  ".join(f"T{t} {r:.0%}" for t, r in goldfish["play_by_turn"].items())
    )

    lines.append(f"Coverage:  [{coverage['status']}]")
    for cls, info in coverage["classes"].items():
        if info["status"] == "OK":
            lines.append(f"  OK        {cls}: " + ", ".join(info["cards"]))
        elif info["status"] == "CONCEDED":
            lines.append(f"  CONCEDED  {cls}: {info['conceded']}")
        else:
            lines.append(f"  FAIL      {cls}")
    for f in coverage["flags"]:
        lines.append(f"  FAIL  {f['rule']}: {f['detail']}")

    return "\n".join(lines)

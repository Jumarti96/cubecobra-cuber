"""Mana audit utilities: pip demand, land production, formula-based land targets, color balance."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from .effective_cost import best_mode


_PIP_RE = re.compile(r"\{([WUBRG])\}")
_ADD_SINGLE_RE = re.compile(r"Add \{([WUBRG])\}", re.IGNORECASE)
_ADD_ANY_RE = re.compile(
    r"Add (?:one mana of any color|[a-z]+ mana of any color|mana of any (?:one )?color)",
    re.IGNORECASE,
)
# Conditional any-color: e.g. Plaza of Heroes "Add one mana of any color. This ability costs {1} less..."
_CONDITIONAL_ANY_RE = re.compile(
    r"Add (?:one mana of any color|[a-z]+ mana of any color|mana of any (?:one )?color).*?(?:costs?|unless|if|only)",
    re.IGNORECASE,
)

_BASIC_TYPE_TO_COLOR = {
    "Plains": "W",
    "Island": "U",
    "Swamp": "B",
    "Mountain": "R",
    "Forest": "G",
}


def pip_demand(cards: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count colored pips (W/U/B/R/G) across non-land mana costs."""
    counts: Counter = Counter()
    for card in cards:
        if "land" in (card.get("type_line") or "").lower():
            continue
        cost = card.get("mana_cost") or ""
        for pip in _PIP_RE.findall(cost):
            counts[pip] += 1
    return dict(counts)


def land_color_production(lands: List[Dict[str, Any]]) -> Dict[str, int]:
    """Infer color production from land type_line and oracle_text.

    Unconditional any-color lands (e.g. Crystal Grotto) count as 1 for each color.
    Conditional any-color lands (e.g. Plaza of Heroes) count as 0.5 for each color.
    """
    counts: Counter = Counter()
    for land in lands:
        type_line = land.get("type_line") or ""
        oracle = land.get("oracle_text") or ""
        produced: set = set()
        weight = 1.0

        for basic_type, color in _BASIC_TYPE_TO_COLOR.items():
            if basic_type in type_line:
                produced.add(color)

        for line in oracle.splitlines():
            if "add" in line.lower():
                for m in re.finditer(r"\{([WUBRG])\}", line):
                    produced.add(m.group(1).upper())

        if _ADD_ANY_RE.search(oracle):
            if _CONDITIONAL_ANY_RE.search(oracle):
                weight = 0.5
            produced.update("WUBRG")

        for color in produced:
            counts[color] += weight

    # Round to nearest int for downstream compatibility
    return {k: round(v) for k, v in counts.items()}


# Tags the tagger actually emits for cards that accelerate mana. These must match
# tagger.MECHANICAL_FUNCTIONS_BASE verbatim (plus "Fast Mana", which the tagger emits
# in practice). Comparison is case-insensitive on the whole tag, not a substring search:
# an earlier version tested `"ramp" in tags`, which never matched "Mana Ramp" and so
# silently reported ramp_count == 0 for every deck.
RAMP_TAGS = frozenset({
    "mana ramp",
    "mana rock",
    "mana dork",
    "land fetch",
    "fast mana",
})


def is_ramp_card(card: Dict[str, Any]) -> bool:
    """True if the card carries any tagger tag denoting mana acceleration."""
    return any((t or "").strip().lower() in RAMP_TAGS for t in (card.get("tags") or []))


def burgess_formula(color_count: int, commander_cmc: float, deck_size: int) -> int:
    """Burgess commander land count: round((31 + color_count + commander_cmc) * deck_size / 100)."""
    return round((31 + color_count + commander_cmc) * deck_size / 100)


def karsten_adjustment(ramp_count: int, deck_size: int) -> int:
    """Karsten land count: round(max(36, 42 - floor(ramp_count / 2.5)) * deck_size / 100)."""
    return round(max(36, 42 - math.floor(ramp_count / 2.5)) * deck_size / 100)


# ── Land-count model: hypergeometric base + curve/accel adjustment ───────────
#
#   base(N) = argmax_L  P(2 <= lands <= 4 in an opening hand of 7)
#   target  = base(N) + [ 2*(avg_mv - 2.5) - 0.25*accel + delta ] * (N / 60)
#
# The old model was `round(24 * deck_size / 60)` — 60-card constructed proportions
# scaled linearly. That is wrong across deck sizes: the opening hand is a fixed 7
# cards regardless of deck size, so the land *fraction* producing a good opener is
# not scale-invariant. Solving the opening-hand problem per deck size gives 17/40
# (42.5%) but 25/60 (41.7%) — neither is the 40% the old baseline assumed.
#
# The load-bearing property of this shape: the BASE carries the deck-size effect and
# has no free parameters. An earlier draft made the curve term absolute
# (`N/3 + 2*avg_mv`), but an absolute card count contributes the same ~5.6 lands to a
# 40-card and a 60-card deck, which is a far bigger share of the smaller one.
# Everything that is not the base is therefore scaled by N/60. The land count is a
# function of deck size, curve and acceleration only — there is no per-archetype term;
# average mana value already carries how fast or slow a deck plays.

# The opening-hand land window the base solves for. 2 lands is the floor for a
# keepable hand; past 4 the extra land is a blank.
BASE_WINDOW = (2, 4)

# The curve the base implicitly assumes; the adjustment reads avg MV as a deviation
# from this, so a deck on this exact curve gets no curve adjustment at all.
REFERENCE_AVG_MV = 2.5

# Guardrail only, for extreme inputs (a deck whose projected curve is far outside
# anything playable). The clamp is FLAGGED in the trace rather than applied
# silently, because a clamped result means an input needs re-checking.
LAND_FRACTION_CLAMP = (0.33, 0.475)

# One-mana card-flow effects. Compared as whole tags, case-insensitively — see the
# RAMP_TAGS comment above for why a substring test is a silent-zero bug.
CANTRIP_TAGS = frozenset({
    "card draw",
    "card selection",
    "looting",
})


def hypergeom_window(
    deck_size: int, lands: int, lo: int, hi: int, draws: int = 7
) -> float:
    """P(lo <= lands drawn <= hi) in an opening hand of `draws` cards."""
    if deck_size <= 0 or draws > deck_size:
        return 0.0
    total = math.comb(deck_size, draws)
    hits = 0
    for k in range(max(lo, 0), min(hi, draws, lands) + 1):
        if draws - k > deck_size - lands:
            continue
        hits += math.comb(lands, k) * math.comb(deck_size - lands, draws - k)
    return hits / total


def is_cantrip_card(card: Dict[str, Any]) -> bool:
    """True if the card is a one-mana nonland that replaces or filters itself."""
    if "land" in (card.get("type_line") or "").lower():
        return False
    if float(card.get("cmc") or 0) > 1:
        return False
    return any((t or "").strip().lower() in CANTRIP_TAGS for t in (card.get("tags") or []))


def accel_count(non_lands: List[Dict[str, Any]]) -> int:
    """Count cards that accelerate or smooth mana — the `A` term in the formula.

    A union, not a sum: a card that is both a cantrip and ramp counts once.
    """
    return sum(1 for c in non_lands if is_ramp_card(c) or is_cantrip_card(c))


def hypergeometric_base(deck_size: int, window: Optional[tuple] = None) -> int:
    """Land count maximizing P(lands in the opening 7 falls inside `window`).

    This is the deck-size-aware anchor and has no free parameters: it is solved per
    deck size rather than scaled from a 60-card percentage. Ties go to the lower
    count. Gives 17 for N=40 (42.5%) and 25 for N=60 (41.7%).
    """
    lo, hi = window or BASE_WINDOW
    return max(
        range(deck_size + 1),
        key=lambda n: (hypergeom_window(deck_size, n, lo, hi), -n),
    )


def land_adjustment(deck_size: int, avg_mv: float, accel: int) -> float:
    """Curve + acceleration shift, scaled to deck size.

    Scaled by N/60 because these are all *proportional* effects: a curve one point
    above reference should move a 40-card deck by two thirds of what it moves a
    60-card deck, not by the same absolute number of cards.
    """
    raw = 2 * (avg_mv - REFERENCE_AVG_MV) - 0.25 * accel
    return raw * (deck_size / 60)


def land_target(deck_size: int, avg_mv: float, accel: int) -> Dict[str, Any]:
    """Recommended land count, with the full derivation trace.

    The returned dict IS the record the deck builder stores as `land_math.target`;
    nothing downstream should re-derive or hand-copy these numbers. The count is a
    function of deck size, curve and acceleration only — there is no archetype term.
    """
    base = hypergeometric_base(deck_size)
    adjustment = land_adjustment(deck_size, avg_mv, accel)
    raw_target = base + adjustment

    lo_bound = math.ceil(LAND_FRACTION_CLAMP[0] * deck_size)
    hi_bound = math.floor(LAND_FRACTION_CLAMP[1] * deck_size)
    # Half-UP, not Python's round(): banker's rounding sends both 23.5 and 24.5 to
    # 24, so a deck with a strictly lower target could tie one with a higher target
    # and the model stopped being monotonic in the adjustment.
    rounded = math.floor(raw_target + 0.5)
    recommended = max(lo_bound, min(hi_bound, rounded))

    return {
        "base_lands": base,
        "base_window": BASE_WINDOW,
        "base_p_window": round(hypergeom_window(deck_size, base, *BASE_WINDOW), 4),
        "avg_mv": avg_mv,
        "reference_avg_mv": REFERENCE_AVG_MV,
        "accel": accel,
        "adjustment": round(adjustment, 3),
        "raw_target": round(raw_target, 3),
        "clamped": recommended != rounded,
        "recommended_land_count": recommended,
        "p_window_at_recommended": round(
            hypergeom_window(deck_size, recommended, *BASE_WINDOW), 4
        ),
    }


def color_balance(
    pip_demand_dict: Dict[str, int],
    land_production_dict: Dict[str, int],
    total_lands: int,
) -> Dict[str, Any]:
    """Compare pip demand % vs land production % per color.

    Gaps > 10pp → WARN, > 15pp → FAIL.
    """
    all_colors = sorted(set(pip_demand_dict) | set(land_production_dict))
    total_pips = sum(pip_demand_dict.values()) or 1
    flags = []
    per_color: Dict[str, Any] = {}

    for color in all_colors:
        pip_pct = round(pip_demand_dict.get(color, 0) / total_pips * 100, 1)
        prod = land_production_dict.get(color, 0)
        prod_pct = round(prod / total_lands * 100, 1) if total_lands else 0.0
        gap = round(pip_pct - prod_pct, 1)
        if gap > 15:
            cstatus = "FAIL"
        elif gap > 10:
            cstatus = "WARN"
        else:
            cstatus = "OK"
        per_color[color] = {
            "pip_pct": pip_pct,
            "prod_pct": prod_pct,
            "gap": gap,
            "status": cstatus,
        }
        if cstatus != "OK":
            flags.append({"color": color, "status": cstatus, "gap": gap})

    if any(f["status"] == "FAIL" for f in flags):
        overall = "FAIL"
    elif any(f["status"] == "WARN" for f in flags):
        overall = "WARN"
    else:
        overall = "PASS"

    return {"per_color": per_color, "flags": flags, "overall": overall}


def splash_requirements(
    splash_cards: List[Dict[str, Any]], total_lands: int
) -> Dict[str, Any]:
    """Compute required sources for each splash color.

    Formulas (proportional to deck size):
      - 1 splash card at CMC 4+: ceil(total_lands * 0.18)
      - 1 splash card at CMC 3:   ceil(total_lands * 0.24)
      - N splash cards:             ceil(total_lands * (0.18 + 0.06 * (N - 1)))
      - Never exceed ceil(total_lands * 0.15) per splash color
    """
    splash_counts: Counter = Counter()
    splash_max_cmc: Dict[str, int] = {}
    for card in splash_cards:
        ci = card.get("color_identity") or []
        if not ci or len(ci) > 1:
            continue  # only single-color splash cards
        color = ci[0]
        splash_counts[color] += 1
        cmc = int(card.get("cmc", 0))
        splash_max_cmc[color] = max(splash_max_cmc.get(color, 0), cmc)

    per_color: Dict[str, Any] = {}
    flags = []
    for color, count in splash_counts.items():
        max_cmc = splash_max_cmc.get(color, 0)
        if max_cmc >= 4:
            base = 0.18
        else:
            base = 0.24
        required = math.ceil(total_lands * min(base + 0.06 * (count - 1), 0.15))
        per_color[color] = {
            "splash_card_count": count,
            "max_cmc": max_cmc,
            "required_sources": required,
        }
        # We don't flag here; splash check is advisory (greedy by design)
    return {"per_color": per_color, "flags": flags, "overall": "PASS"}


def mana_audit(
    deck_cards: List[Dict[str, Any]],
    format: str,
    commander_cards: Optional[List[Dict[str, Any]]] = None,
    core_colors: Optional[List[str]] = None,
    splash_colors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run full mana audit and return structured result dict.

    format: one of "40-card", "60-card", "commander-60", "commander-100"
    core_colors: primary deck colors (subset of all card color identities)
    splash_colors: off-color splash colors (≤ 3 cards each)
    """
    lands = [c for c in deck_cards if "land" in (c.get("type_line") or "").lower()]
    non_lands = [c for c in deck_cards if "land" not in (c.get("type_line") or "").lower()]
    ramp = [c for c in non_lands if is_ramp_card(c)]
    cantrips = [c for c in non_lands if is_cantrip_card(c)]
    accel = accel_count(non_lands)
    deck_size = len(deck_cards)
    land_count = len(lands)

    core_colors = core_colors or []
    splash_colors = splash_colors or []

    def _effective(card: Dict[str, Any]):
        """The pips (with multiplicity) and mana value the deck actually pays for
        this card, using the mode it is played by. A colorless cycler like Street
        Wraith contributes no colored pips and ~0 mana value instead of the
        phantom ``{B}{B}`` / cmc 5 of its unused printed cast."""
        m = best_mode(card, core_colors, splash_colors)
        if m is None:  # unusable even with splash -- fall back to the printed cost
            return _PIP_RE.findall(card.get("mana_cost") or ""), float(card.get("cmc") or 0)
        return list(m["pips"]), float(m["cmc"])

    cmc_vals = [_effective(c)[1] for c in non_lands]
    avg_cmc = round(sum(cmc_vals) / len(cmc_vals), 2) if cmc_vals else 0.0

    land_target_trace = None
    if format in ("commander-60", "commander-100"):
        # Commander keeps the Burgess + Karsten average: the new formula is not
        # calibrated for singleton 100-card decks or commander tax.
        cmd = commander_cards[0] if commander_cards else {}
        color_count = len(set(cmd.get("color_identity") or ["W", "B"]))
        commander_cmc = float(cmd.get("cmc") or 4)
        rec_burgess = burgess_formula(color_count, commander_cmc, deck_size)
        rec_karsten = karsten_adjustment(len(ramp), deck_size)
        recommended_land_count = round((rec_burgess + rec_karsten) / 2)
    else:
        land_target_trace = land_target(deck_size, avg_cmc, accel)
        recommended_land_count = land_target_trace["recommended_land_count"]

    land_diff = abs(land_count - recommended_land_count)
    if land_diff <= 1:
        land_count_status = "PASS"
    elif land_diff <= 2:
        land_count_status = "WARN"
    else:
        land_count_status = "FAIL"

    # Core color balance. Classify by the mode a card is actually played by, not
    # its printed identity: a card whose usable mode needs a splash colour is a
    # real splash card, while one usable within the core (including a colorless
    # cycler that happens to have an off-colour printed identity) is a core card.
    core_set = set(core_colors)
    core_cards = []
    splash_cards = []
    for c in deck_cards:
        m = best_mode(c, core_colors, splash_colors)
        if m is None:
            # Unusable even with splash: preserve the old identity-based bucket.
            if set(c.get("color_identity") or []).issubset(core_set):
                core_cards.append(c)
            else:
                splash_cards.append(c)
            continue
        if set(m["cost_pips"]) - core_set:
            splash_cards.append(c)   # the mode we'd play needs a splash colour
        else:
            core_cards.append(c)

    # Core pip demand from each core card's *effective* pips (multiplicity kept),
    # restricted to core colours. A colorless cycler adds nothing here.
    core_pips_counter: Counter = Counter()
    for c in core_cards:
        if "land" in (c.get("type_line") or "").lower():
            continue
        for pip in _effective(c)[0]:
            if pip in core_set:
                core_pips_counter[pip] += 1
    core_pips = dict(core_pips_counter)
    all_land_prod = land_color_production(lands)
    core_lands_prod = {k: v for k, v in all_land_prod.items() if k in core_colors}
    core_balance = color_balance(core_pips, core_lands_prod, land_count)

    # Splash check
    splash_check = splash_requirements(splash_cards, land_count)
    for color, info in splash_check.get("per_color", {}).items():
        actual = all_land_prod.get(color, 0)
        required = info["required_sources"]
        if actual < required:
            splash_check["flags"].append({
                "color": color,
                "status": "WARN",
                "actual": actual,
                "required": required,
            })
            splash_check["overall"] = "WARN"

    overall_statuses = [land_count_status, core_balance["overall"], splash_check["overall"]]
    if "FAIL" in overall_statuses:
        overall = "FAIL"
    elif "WARN" in overall_statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "land_count": land_count,
        "recommended_land_count": recommended_land_count,
        "land_count_status": land_count_status,
        "ramp_count": len(ramp),
        "cantrip_count": len(cantrips),
        "accel_count": accel,
        "land_target_trace": land_target_trace,
        "avg_cmc": avg_cmc,
        "pip_demand": core_pips,
        "land_color_production": all_land_prod,
        "color_balance_status": core_balance["overall"],
        "color_balance_flags": core_balance["flags"],
        "color_balance_per_color": core_balance["per_color"],
        "splash_colors": splash_colors,
        "splash_check": splash_check,
        "overall_status": overall,
    }


def format_audit_report(audit: Dict[str, Any]) -> str:
    """Return human-readable audit text with PASS/WARN/FAIL per section."""
    lines = [
        f"── Mana Audit: {audit['overall_status']} {'─' * 40}",
        f"Land Count:  {audit['land_count']} / {audit['recommended_land_count']} recommended  "
        f"[{audit['land_count_status']}]",
        f"Avg CMC:     {audit['avg_cmc']}   Ramp cards: {audit['ramp_count']}"
        f"   Cantrips: {audit.get('cantrip_count', 0)}",
    ]

    trace = audit.get("land_target_trace")
    if trace:
        lo, hi = trace["base_window"]
        lines.append(
            f"  Derivation: base {trace['base_lands']}"
            f" (argmax P({lo}-{hi} in 7) = {trace['base_p_window']:.3f})"
            f"  {trace['adjustment']:+.2f} adj"
            f" [MV {trace['avg_mv']} vs {trace['reference_avg_mv']},"
            f" {trace['accel']} accel, scaled N/60]"
            f"  ->  {trace['recommended_land_count']} lands"
            f"  (P({lo}-{hi} in 7) = {trace['p_window_at_recommended']:.3f})"
            + ("  [CLAMPED]" if trace["clamped"] else "")
        )

    lines += [
        "",
        f"Color Balance (core):  [{audit['color_balance_status']}]",
    ]
    for color, info in sorted(audit.get("color_balance_per_color", {}).items()):
        lines.append(
            f"  {color}  demand {info['pip_pct']:5.1f}%  prod {info['prod_pct']:5.1f}%  "
            f"gap {info['gap']:+5.1f}pp  [{info['status']}]"
        )
    if audit["color_balance_flags"]:
        lines.append("")
        lines.append("Flags:")
        for f in audit["color_balance_flags"]:
            lines.append(f"  {f['status']:4}  {f['color']}  gap {f['gap']:+.1f}pp")

    splash = audit.get("splash_check")
    if splash and splash.get("per_color"):
        lines.append("")
        lines.append(f"Splash Check: [{splash['overall']}]")
        for color, info in sorted(splash["per_color"].items()):
            actual = audit.get("land_color_production", {}).get(color, 0)
            req = info["required_sources"]
            status = "OK" if actual >= req else "WARN"
            lines.append(
                f"  {color}  {info['splash_card_count']} card(s), max CMC {info['max_cmc']}  "
                f"sources {actual}/{req}  [{status}]"
            )
        for f in splash.get("flags", []):
            lines.append(
                f"  WARN  {f['color']}  actual {f['actual']} < required {f['required']}"
            )
    return "\n".join(lines)

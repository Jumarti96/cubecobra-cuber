"""Mana audit utilities: pip demand, land production, formula-based land targets, color balance."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional


_PIP_RE = re.compile(r"\{([WUBRG])\}")
_ADD_SINGLE_RE = re.compile(r"Add \{([WUBRG])\}", re.IGNORECASE)
_ADD_ANY_RE = re.compile(
    r"Add (?:one mana of any color|[a-z]+ mana of any color|mana of any (?:one )?color)",
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
    """Infer color production from land type_line and oracle_text."""
    counts: Counter = Counter()
    for land in lands:
        type_line = land.get("type_line") or ""
        oracle = land.get("oracle_text") or ""
        produced: set = set()

        for basic_type, color in _BASIC_TYPE_TO_COLOR.items():
            if basic_type in type_line:
                produced.add(color)

        for m in _ADD_SINGLE_RE.finditer(oracle):
            produced.add(m.group(1).upper())

        if _ADD_ANY_RE.search(oracle):
            produced.update("WUBRG")

        for color in produced:
            counts[color] += 1

    return dict(counts)


def burgess_formula(color_count: int, commander_cmc: float, deck_size: int) -> int:
    """Burgess commander land count: round((31 + color_count + commander_cmc) * deck_size / 100)."""
    return round((31 + color_count + commander_cmc) * deck_size / 100)


def karsten_adjustment(ramp_count: int, deck_size: int) -> int:
    """Karsten land count: round(max(36, 42 - floor(ramp_count / 2.5)) * deck_size / 100)."""
    return round(max(36, 42 - math.floor(ramp_count / 2.5)) * deck_size / 100)


def constructed_land_target(ramp_count: int, avg_cmc: float, deck_size: int) -> int:
    """Baseline 24 for 60-card constructed, scaled; adjusted for ramp and curve.

    Clamp: [14, 18] for 40-card, [20, 27] for 60-card.
    """
    baseline = round(24 * deck_size / 60)
    adjusted = baseline - math.floor(ramp_count / 3)
    if avg_cmc <= 2.0:
        adjusted -= 1
    elif avg_cmc >= 4.0:
        adjusted += 1
    if deck_size <= 40:
        return max(14, min(18, adjusted))
    return max(20, min(27, adjusted))


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


def mana_audit(
    deck_cards: List[Dict[str, Any]],
    format: str,
    commander_cards: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run full mana audit and return structured result dict.

    format: one of "40-card", "60-card", "commander-60", "commander-100"
    """
    lands = [c for c in deck_cards if "land" in (c.get("type_line") or "").lower()]
    non_lands = [c for c in deck_cards if "land" not in (c.get("type_line") or "").lower()]
    ramp = [c for c in non_lands if "ramp" in [t.lower() for t in (c.get("tags") or [])]]
    deck_size = len(deck_cards)
    land_count = len(lands)

    cmc_vals = [float(c.get("cmc") or 0) for c in non_lands]
    avg_cmc = round(sum(cmc_vals) / len(cmc_vals), 2) if cmc_vals else 0.0

    if format in ("commander-60", "commander-100"):
        cmd = commander_cards[0] if commander_cards else {}
        color_count = len(set(cmd.get("color_identity") or ["W", "B"]))
        commander_cmc = float(cmd.get("cmc") or 4)
        rec_burgess = burgess_formula(color_count, commander_cmc, deck_size)
        rec_karsten = karsten_adjustment(len(ramp), deck_size)
        recommended_land_count = round((rec_burgess + rec_karsten) / 2)
    else:
        recommended_land_count = constructed_land_target(len(ramp), avg_cmc, deck_size)

    land_diff = abs(land_count - recommended_land_count)
    if land_diff <= 1:
        land_count_status = "PASS"
    elif land_diff <= 2:
        land_count_status = "WARN"
    else:
        land_count_status = "FAIL"

    pips = pip_demand(deck_cards)
    prod = land_color_production(lands)
    balance = color_balance(pips, prod, land_count)

    if "FAIL" in (land_count_status, balance["overall"]):
        overall = "FAIL"
    elif "WARN" in (land_count_status, balance["overall"]):
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "land_count": land_count,
        "recommended_land_count": recommended_land_count,
        "land_count_status": land_count_status,
        "ramp_count": len(ramp),
        "avg_cmc": avg_cmc,
        "pip_demand": pips,
        "land_color_production": prod,
        "color_balance_status": balance["overall"],
        "color_balance_flags": balance["flags"],
        "color_balance_per_color": balance["per_color"],
        "overall_status": overall,
    }


def format_audit_report(audit: Dict[str, Any]) -> str:
    """Return human-readable audit text with PASS/WARN/FAIL per section."""
    lines = [
        f"── Mana Audit: {audit['overall_status']} {'─' * 40}",
        f"Land Count:  {audit['land_count']} / {audit['recommended_land_count']} recommended  "
        f"[{audit['land_count_status']}]",
        f"Avg CMC:     {audit['avg_cmc']}   Ramp cards: {audit['ramp_count']}",
        "",
        f"Color Balance:  [{audit['color_balance_status']}]",
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
    return "\n".join(lines)

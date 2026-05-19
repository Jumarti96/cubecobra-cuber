"""Statistics engine — color, CMC, rarity, type, and tag density reports."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from .cube import CUBES_DIR, Cube, cube_dir

COLOR_LABELS = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
BAR_WIDTH = 30


def compute_stats(cube: Cube) -> Dict[str, Any]:
    cards = [c for c in cube.cards if c.board == "mainboard"]

    color_dist = _color_distribution(cards)
    cmc_curve = _cmc_curve(cards)
    rarity = _rarity_breakdown(cards)
    card_types = _card_type_breakdown(cards)

    return {
        "cube_short_id": cube.short_id,
        "cube_title": cube.title,
        "total_cards": len(cards),
        "color_distribution": color_dist,
        "cmc_curve": cmc_curve,
        "rarity_breakdown": rarity,
        "card_type_breakdown": card_types,
    }


def compute_tag_density(cube: Cube) -> Dict[str, Any]:
    cards = [c for c in cube.cards if c.board == "mainboard"]
    tag_counts: Counter = Counter()
    for card in cards:
        for tag in card.tags:
            if tag:
                tag_counts[tag] += 1

    low_density = [t for t, n in tag_counts.items() if n < 3]
    return {
        "tag_counts": dict(tag_counts.most_common()),
        "low_density_tags": low_density,
        "has_tags": bool(tag_counts),
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _color_distribution(cards: list) -> Dict[str, Any]:
    counts: Dict[str, int] = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "M": 0, "C": 0}
    for card in cards:
        ci = card.color_identity
        if not ci:
            counts["C"] += 1
        elif len(ci) > 1:
            counts["M"] += 1
        else:
            counts[ci[0]] = counts.get(ci[0], 0) + 1
    total = len(cards) or 1
    return {
        k: {"count": v, "pct": round(v / total * 100, 1)}
        for k, v in counts.items()
    }


def _cmc_curve(cards: list) -> Dict[str, Any]:
    creature_curve: Counter = Counter()
    noncreature_curve: Counter = Counter()
    for card in cards:
        cmc_bucket = min(int(card.cmc), 7)
        label = f"{cmc_bucket}+" if cmc_bucket == 7 else str(cmc_bucket)
        if "Creature" in card.type_line or "Vehicle" in card.type_line:
            creature_curve[label] += 1
        else:
            noncreature_curve[label] += 1
    buckets = [str(i) for i in range(7)] + ["7+"]
    return {
        "buckets": buckets,
        "creature": {b: creature_curve.get(b, 0) for b in buckets},
        "noncreature": {b: noncreature_curve.get(b, 0) for b in buckets},
    }


def _rarity_breakdown(cards: list) -> Dict[str, Any]:
    counts: Counter = Counter()
    for card in cards:
        counts[card.rarity or "unknown"] += 1
    total = len(cards) or 1
    order = ["common", "uncommon", "rare", "mythic", "special", "bonus", "unknown"]
    return {
        r: {"count": counts.get(r, 0), "pct": round(counts.get(r, 0) / total * 100, 1)}
        for r in order
        if r in counts or r in ("common", "uncommon", "rare", "mythic")
    }


def _card_type_breakdown(cards: list) -> Dict[str, Any]:
    order = ["Creature", "Instant", "Sorcery", "Enchantment", "Artifact",
             "Planeswalker", "Land", "Other"]
    counts: Dict[str, int] = {t: 0 for t in order}
    for card in cards:
        tl = card.type_line
        assigned = False
        for t in order[:-1]:
            if t in tl:
                counts[t] += 1
                assigned = True
                break
        if not assigned:
            counts["Other"] += 1
    total = len(cards) or 1
    return {
        t: {"count": counts[t], "pct": round(counts[t] / total * 100, 1)}
        for t in order
    }


# ── Formatting ────────────────────────────────────────────────────────────────

def _bar(count: int, max_count: int) -> str:
    if max_count == 0:
        return ""
    filled = int(count / max_count * BAR_WIDTH)
    return "#" * filled + "." * (BAR_WIDTH - filled)


def format_stats_report(stats: Dict[str, Any]) -> str:
    lines = []
    total = stats["total_cards"]
    lines.append(f"\n{'=' * 56}")
    lines.append(f"  {stats['cube_title']}  ({total} mainboard cards)")
    lines.append(f"{'=' * 56}\n")

    # Color distribution
    lines.append("COLOR IDENTITY")
    lines.append("-" * 40)
    cd = stats["color_distribution"]
    label_map = {"W": "White", "U": "Blue", "B": "Black",
                 "R": "Red", "G": "Green", "M": "Multi", "C": "Colorless"}
    max_count = max((v["count"] for v in cd.values()), default=1)
    for k, label in label_map.items():
        v = cd.get(k, {"count": 0, "pct": 0})
        bar = _bar(v["count"], max_count)
        lines.append(f"  {label:<10} {bar} {v['count']:>4} ({v['pct']:>5.1f}%)")

    # CMC curve
    lines.append("\nCMC CURVE (creatures / non-creatures)")
    lines.append("-" * 40)
    curve = stats["cmc_curve"]
    max_combined = max(
        (curve["creature"].get(b, 0) + curve["noncreature"].get(b, 0)
         for b in curve["buckets"]),
        default=1,
    )
    for b in curve["buckets"]:
        cr = curve["creature"].get(b, 0)
        nc = curve["noncreature"].get(b, 0)
        combined = cr + nc
        bar = _bar(combined, max_combined)
        lines.append(f"  CMC {b:>2}  {bar} {combined:>3}  (cr:{cr} nc:{nc})")

    # Rarity
    lines.append("\nRARITY")
    lines.append("-" * 40)
    rb = stats["rarity_breakdown"]
    max_r = max((v["count"] for v in rb.values()), default=1)
    for rarity, v in rb.items():
        bar = _bar(v["count"], max_r)
        lines.append(f"  {rarity.capitalize():<12} {bar} {v['count']:>4} ({v['pct']:>5.1f}%)")

    # Card types
    lines.append("\nCARD TYPES")
    lines.append("-" * 40)
    ct = stats["card_type_breakdown"]
    max_t = max((v["count"] for v in ct.values()), default=1)
    for t, v in ct.items():
        bar = _bar(v["count"], max_t)
        lines.append(f"  {t:<14} {bar} {v['count']:>4} ({v['pct']:>5.1f}%)")

    lines.append("")
    return "\n".join(lines)


def format_tag_density_report(tag_data: Dict[str, Any]) -> str:
    if not tag_data["has_tags"]:
        return "\nNo tags found. Run /tag-cube (or `python -m cuber tag <id>`) to tag cards.\n"
    lines = ["\nARCHETYPE TAG DENSITY", "-" * 40]
    counts = tag_data["tag_counts"]
    max_c = max(counts.values(), default=1)
    for tag, count in counts.items():
        bar = _bar(count, max_c)
        note = " * (< 3 cards)" if count < 3 else ""
        lines.append(f"  {tag:<22} {bar} {count:>3}{note}")
    lines.append("")
    return "\n".join(lines)


def write_analysis_json(stats: Dict[str, Any], short_id: str) -> str:
    path = os.path.join(cube_dir(short_id), "analysis.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    return path

"""Statistics engine — color, CMC, rarity, type, guild, cross-breakdown, tag density, and archetype clusters."""

from __future__ import annotations

import json
import os
import shutil
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .cube import Cube, cube_dir
from .tagger import SPEED_TAGS, ENGINE_TAGS

COLOR_LABELS = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}

GUILD_PAIRS = [
    ("WU", "Azorius"), ("WB", "Orzhov"), ("WR", "Boros"), ("WG", "Selesnya"),
    ("UB", "Dimir"), ("UR", "Izzet"), ("UG", "Simic"),
    ("BR", "Rakdos"), ("BG", "Golgari"), ("RG", "Gruul"),
]

_GUILD_KEY_SET: Dict[frozenset, str] = {frozenset(k): k for k, _ in GUILD_PAIRS}

CROSS_DIMENSIONS = {"color", "color-category", "rarity", "type", "creature", "guild"}
CROSS_METRICS = {"cmc", "power", "toughness"}


# ── Bar rendering ─────────────────────────────────────────────────────────────

def _bar_width() -> int:
    try:
        cols = shutil.get_terminal_size().columns
        return min(40, max(20, cols - 30))
    except Exception:
        return 30


def _bar(count: int, max_count: int, width: Optional[int] = None) -> str:
    if width is None:
        width = _bar_width()
    if max_count == 0:
        return "░" * width
    filled = round(count / max_count * width)
    return "█" * filled + "░" * (width - filled)


def _numeric_summary(values: List[float]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return f"mean={values[0]:.2f}  median={values[0]:.2f}  stdev=0.00"
    mean = statistics.mean(values)
    median = statistics.median(values)
    try:
        stdev = statistics.stdev(values)
    except statistics.StatisticsError:
        stdev = 0.0
    return f"mean={mean:.2f}  median={median:.2f}  stdev={stdev:.2f}"


# ── Compute ───────────────────────────────────────────────────────────────────

def compute_stats(cube: Cube) -> Dict[str, Any]:
    cards = [c for c in cube.cards if c.board == "mainboard"]
    return {
        "cube_id": cube.cube_id or cube.short_id,
        "cube_title": cube.title,
        "total_cards": len(cards),
        "color_distribution": _color_distribution(cards),
        "cmc_curve": _cmc_curve(cards),
        "rarity_breakdown": _rarity_breakdown(cards),
        "card_type_breakdown": _card_type_breakdown(cards),
        "guild_breakdown": _compute_guild_breakdown(cards),
    }


def compute_tag_density(cube: Cube) -> Dict[str, Any]:
    cards = [c for c in cube.cards if c.board == "mainboard"]
    tag_counts: Counter = Counter()
    for card in cards:
        for tag in card.tags:
            if tag:
                tag_counts[tag] += 1
    return {
        "tag_counts": dict(tag_counts.most_common()),
        "low_density_tags": [t for t, n in tag_counts.items() if n < 3],
        "has_tags": bool(tag_counts),
    }


def compute_archetype_clusters(cube: Cube) -> Dict[str, Any]:
    """Compute (speed, engine) archetype pairs from card tags.

    An archetype is a (speed_tag, engine_tag) pair.
    A card contributes to an archetype if it has BOTH the speed tag AND the engine tag.

    Support thresholds (proportional to total mainboard cards):
      - Sparse:   <  5% of pool
      - Supported:  5% to < 10%
      - Strong:    ≥ 10%
    """
    cards = [c for c in cube.cards if c.board == "mainboard"]
    total = len(cards) or 1

    # Gather all (speed, engine) pairs found on individual cards
    archetype_counts: Dict[str, Dict[str, Any]] = {}
    for card in cards:
        card_speeds = [t for t in card.tags if t in SPEED_TAGS]
        card_engines = [t for t in card.tags if t in ENGINE_TAGS]
        for speed in card_speeds:
            for engine in card_engines:
                key = f"{speed}-{engine}"
                if key not in archetype_counts:
                    archetype_counts[key] = {"speed": speed, "engine": engine, "count": 0}
                archetype_counts[key]["count"] += 1

    # Classify support level
    clusters = []
    for key, data in archetype_counts.items():
        count = data["count"]
        pct = count / total * 100
        if pct >= 10:
            support = "strong"
        elif pct >= 5:
            support = "supported"
        else:
            support = "sparse"
        clusters.append({
            "name": key,
            "speed": data["speed"],
            "engine": data["engine"],
            "count": count,
            "pct": round(pct, 1),
            "support": support,
        })

    # Sort by count descending
    clusters.sort(key=lambda x: -x["count"])

    return {
        "clusters": clusters,
        "speed_distribution": _speed_distribution(cards),
        "engine_distribution": _engine_distribution(cards),
    }


def _speed_distribution(cards: list) -> Dict[str, int]:
    counts: Dict[str, int] = {s: 0 for s in SPEED_TAGS}
    for card in cards:
        for tag in card.tags:
            if tag in counts:
                counts[tag] += 1
    return counts


def _engine_distribution(cards: list) -> Dict[str, int]:
    counts: Dict[str, int] = {e: 0 for e in ENGINE_TAGS}
    for card in cards:
        for tag in card.tags:
            if tag in counts:
                counts[tag] += 1
    return counts


def compute_cross_breakdown(cards: list, dimension: str, metric: str) -> Dict[str, Any]:
    """Group cards by dimension and compute mean/median/stdev/count/sum of metric."""
    groups: Dict[str, List[float]] = defaultdict(list)
    for card in cards:
        key = _card_dimension_key(card, dimension)
        if key is None:
            continue
        value = _card_metric_value(card, metric)
        if value is None:
            continue
        groups[key].append(value)

    result: Dict[str, Any] = {}
    for key, vals in groups.items():
        mean = statistics.mean(vals)
        median = statistics.median(vals)
        stdev = statistics.stdev(vals) if len(vals) > 1 else 0.0
        result[key] = {
            "mean": round(mean, 2),
            "median": round(median, 2),
            "stdev": round(stdev, 2),
            "count": len(vals),
            "sum": round(sum(vals), 2),
        }
    return {"dimension": dimension, "metric": metric, "groups": result}


def _card_dimension_key(card: Any, dimension: str) -> Optional[str]:
    if dimension == "color":
        ci = card.color_identity
        if not ci:
            return "C"
        if len(ci) > 1:
            return "M"
        return ci[0]
    if dimension == "color-category":
        return card.color_category or "?"
    if dimension == "rarity":
        return (card.rarity or "unknown").lower()
    if dimension == "type":
        tl = card.type_line
        for t in ("Creature", "Instant", "Sorcery", "Enchantment", "Artifact", "Planeswalker", "Land"):
            if t in tl:
                return t
        return "Other"
    if dimension == "creature":
        tl = card.type_line
        return "Creature" if ("Creature" in tl or "Vehicle" in tl) else "Non-Creature"
    if dimension == "guild":
        ci = sorted(card.color_identity)
        if len(ci) < 2:
            return None
        if len(ci) > 2:
            return "3+"
        return _GUILD_KEY_SET.get(frozenset(ci)) or "".join(ci)
    return None


def _card_metric_value(card: Any, metric: str) -> Optional[float]:
    if metric == "cmc":
        return float(card.cmc) if card.cmc is not None else None
    if metric == "power":
        try:
            return float(card.power) if card.power is not None else None
        except (TypeError, ValueError):
            return None
    if metric == "toughness":
        try:
            return float(card.toughness) if card.toughness is not None else None
        except (TypeError, ValueError):
            return None
    return None


# ── Private distribution helpers ──────────────────────────────────────────────

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
    return {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in counts.items()}


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
    return {t: {"count": counts[t], "pct": round(counts[t] / total * 100, 1)} for t in order}


def _compute_guild_breakdown(cards: list) -> Dict[str, int]:
    result: Dict[str, int] = {pair: 0 for pair, _ in GUILD_PAIRS}
    result["3+"] = 0
    for card in cards:
        ci = sorted(card.color_identity)
        if len(ci) < 2:
            continue
        if len(ci) > 2:
            result["3+"] += 1
            continue
        pair_key = _GUILD_KEY_SET.get(frozenset(ci))
        if pair_key:
            result[pair_key] += 1
    return result


# ── Individual chart formatters ───────────────────────────────────────────────

def _format_color_chart(cd: Dict[str, Any]) -> str:
    label_map = {"W": "White", "U": "Blue", "B": "Black",
                 "R": "Red", "G": "Green", "M": "Multi", "C": "Colorless"}
    max_count = max((v["count"] for v in cd.values()), default=0) or 1
    w = _bar_width()
    lines = ["COLOR IDENTITY", "-" * 40]
    for k, label in label_map.items():
        v = cd.get(k, {"count": 0, "pct": 0})
        lines.append(f"  {label:<10} {_bar(v['count'], max_count, w)} {v['count']:>4} ({v['pct']:>5.1f}%)")
    return "\n".join(lines)


def _format_cmc_chart(curve: Dict[str, Any], cmc_values: Optional[List[float]] = None) -> str:
    buckets = curve["buckets"]
    totals = {b: curve["creature"].get(b, 0) + curve["noncreature"].get(b, 0) for b in buckets}
    max_count = max(totals.values(), default=0) or 1
    w = _bar_width()
    lines = ["CMC DISTRIBUTION", "-" * 40]
    for b in buckets:
        combined = totals[b]
        cr = curve["creature"].get(b, 0)
        nc = curve["noncreature"].get(b, 0)
        lines.append(f"  CMC {b:>2}  {_bar(combined, max_count, w)} {combined:>3}  (cr:{cr} nc:{nc})")
    if cmc_values is None:
        lines.append("  (summary stats require cuber enrich)")
    elif cmc_values:
        summary = _numeric_summary(cmc_values)
        if summary:
            lines.append(f"  {summary}")
    return "\n".join(lines)


def _format_rarity_chart(rb: Dict[str, Any]) -> str:
    max_r = max((v["count"] for v in rb.values()), default=0) or 1
    w = _bar_width()
    lines = ["RARITY", "-" * 40]
    for rarity, v in rb.items():
        lines.append(f"  {rarity.capitalize():<12} {_bar(v['count'], max_r, w)} {v['count']:>4} ({v['pct']:>5.1f}%)")
    return "\n".join(lines)


def _format_type_chart(ct: Dict[str, Any]) -> str:
    max_t = max((v["count"] for v in ct.values()), default=0) or 1
    w = _bar_width()
    lines = ["CARD TYPES", "-" * 40]
    for t, v in ct.items():
        lines.append(f"  {t:<14} {_bar(v['count'], max_t, w)} {v['count']:>4} ({v['pct']:>5.1f}%)")
    return "\n".join(lines)


def _format_creature_split_chart(ct: Dict[str, Any], total: int) -> str:
    creature_count = ct.get("Creature", {}).get("count", 0)
    noncreature_count = total - creature_count
    max_count = max(creature_count, noncreature_count, 1)
    w = _bar_width()
    pct_cr = round(creature_count / (total or 1) * 100, 1)
    pct_nc = round(noncreature_count / (total or 1) * 100, 1)
    lines = ["CREATURE SPLIT", "-" * 40]
    lines.append(f"  {'Creature':<14} {_bar(creature_count, max_count, w)} {creature_count:>4} ({pct_cr:>5.1f}%)")
    lines.append(f"  {'Non-Creature':<14} {_bar(noncreature_count, max_count, w)} {noncreature_count:>4} ({pct_nc:>5.1f}%)")
    return "\n".join(lines)


def _format_guild_chart(guild_data: Dict[str, int]) -> str:
    guild_names = {
        "WU": "Azorius (WU)", "WB": "Orzhov (WB)", "WR": "Boros (WR)",
        "WG": "Selesnya (WG)", "UB": "Dimir (UB)", "UR": "Izzet (UR)",
        "UG": "Simic (UG)", "BR": "Rakdos (BR)", "BG": "Golgari (BG)",
        "RG": "Gruul (RG)", "3+": "3+ color",
    }
    max_count = max(guild_data.values(), default=0) or 1
    w = _bar_width()
    lines = ["GUILD BREAKDOWN (multicolor)", "-" * 40]
    for key, label in guild_names.items():
        count = guild_data.get(key, 0)
        lines.append(f"  {label:<16} {_bar(count, max_count, w)} {count:>4}")
    return "\n".join(lines)


def _format_archetype_clusters(clusters: List[Dict[str, Any]], total: int) -> str:
    lines = ["\nARCHETYPE CLUSTERS (speed + engine)", "-" * 50]
    max_c = max((c["count"] for c in clusters), default=1)
    w = _bar_width()
    for c in clusters:
        note = f" [{c['support']}]"
        lines.append(
            f"  {c['name']:<28} {_bar(c['count'], max_c, w)} {c['count']:>3} ({c['pct']:>5.1f}%){note}"
        )
    lines.append("")
    lines.append("Support thresholds: strong ≥10%, supported 5-9.9%, sparse <5%")
    lines.append("")
    return "\n".join(lines)


# ── Report assembly ───────────────────────────────────────────────────────────

_DEFAULT_CHARTS = ("color", "cmc", "rarity", "types", "creature")


def format_stats_report(
    stats: Dict[str, Any],
    cmc_values: Optional[List[float]] = None,
    charts: Optional[List[str]] = None,
) -> str:
    """
    Render the stats report.

    charts=None → show the 5 default charts (color, cmc, rarity, types, creature).
    charts=[...] → show only the specified charts.
    Valid chart names: 'color', 'cmc', 'rarity', 'types', 'creature', 'guild'.
    """
    total = stats["total_cards"]
    lines: List[str] = []
    lines.append(f"\n{'=' * 56}")
    lines.append(f"  {stats['cube_title']}  ({total} mainboard cards)")
    lines.append(f"{'=' * 56}\n")

    show = set(charts) if charts is not None else set(_DEFAULT_CHARTS)

    if "color" in show:
        lines.append(_format_color_chart(stats["color_distribution"]))
        lines.append("")
    if "cmc" in show:
        lines.append(_format_cmc_chart(stats["cmc_curve"], cmc_values))
        lines.append("")
    if "rarity" in show:
        lines.append(_format_rarity_chart(stats["rarity_breakdown"]))
        lines.append("")
    if "types" in show:
        lines.append(_format_type_chart(stats["card_type_breakdown"]))
        lines.append("")
    if "creature" in show:
        lines.append(_format_creature_split_chart(stats["card_type_breakdown"], total))
        lines.append("")
    if "guild" in show and "guild_breakdown" in stats:
        lines.append(_format_guild_chart(stats["guild_breakdown"]))
        lines.append("")

    return "\n".join(lines)


def format_cross_breakdown(data: Dict[str, Any], dimension: str, metric: str) -> str:
    groups = data.get("groups", {})
    if not groups:
        return f"\nNo data for --by {dimension} --metric {metric}\n"

    lines = [f"\nCROSS-BREAKDOWN: {metric.upper()} by {dimension.upper()}", "-" * 70]
    lines.append(
        f"  {'Group':<18}  {'Mean':>7}  {'Median':>7}  {'StdDev':>7}  {'Count':>6}  {'Sum':>8}"
    )
    lines.append("  " + "-" * 62)

    total_count = 0
    total_sum = 0.0
    for key, row in sorted(groups.items()):
        lines.append(
            f"  {str(key):<18}  {row['mean']:>7.2f}  {row['median']:>7.2f}"
            f"  {row['stdev']:>7.2f}  {row['count']:>6}  {row['sum']:>8.2f}"
        )
        total_count += row["count"]
        total_sum += row["sum"]

    lines.append("  " + "-" * 62)
    total_mean = total_sum / total_count if total_count else 0.0
    lines.append(
        f"  {'TOTAL':<18}  {total_mean:>7.2f}  {'—':>7}  {'—':>7}  {total_count:>6}  {total_sum:>8.2f}"
    )
    lines.append("")
    return "\n".join(lines)


def format_tag_density_report(tag_data: Dict[str, Any]) -> str:
    if not tag_data["has_tags"]:
        return "\nNo tags found. Run /tag-cube (or `python -m cuber tag <id>`) to tag cards.\n"
    lines = ["\nARCHETYPE TAG DENSITY", "-" * 40]
    counts = tag_data["tag_counts"]
    max_c = max(counts.values(), default=1)
    w = _bar_width()
    for tag, count in counts.items():
        note = " * (< 3 cards)" if count < 3 else ""
        lines.append(f"  {tag:<22} {_bar(count, max_c, w)} {count:>3}{note}")
    lines.append("")
    return "\n".join(lines)


# ── File output ───────────────────────────────────────────────────────────────

def write_analysis_json(stats: Dict[str, Any], short_id: str) -> str:
    exports_dir = os.path.join(cube_dir(short_id), "exports")
    os.makedirs(exports_dir, exist_ok=True)
    path = os.path.join(exports_dir, "analysis.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    return path


def write_analysis_md(stats: Dict[str, Any], short_id: str) -> str:
    """Write exports/analysis.md with YAML frontmatter and Markdown tables."""
    exports_dir = os.path.join(cube_dir(short_id), "exports")
    os.makedirs(exports_dir, exist_ok=True)
    path = os.path.join(exports_dir, "analysis.md")

    lines: List[str] = []
    lines.append("---")
    lines.append(f"cube_id: {stats.get('cube_id', short_id)}")
    lines.append(f'cube_title: "{stats.get("cube_title", "")}"')
    lines.append(f"generated_at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append(f"total_cards: {stats.get('total_cards', 0)}")
    lines.append("---")
    lines.append("")

    label_map = {"W": "White", "U": "Blue", "B": "Black",
                 "R": "Red", "G": "Green", "M": "Multi", "C": "Colorless"}

    lines.append("## Color Identity")
    lines.append("")
    lines.append("| Color | Count | % |")
    lines.append("|-------|------:|--:|")
    cd = stats.get("color_distribution", {})
    for k, label in label_map.items():
        v = cd.get(k, {"count": 0, "pct": 0})
        lines.append(f"| {label} | {v['count']} | {v['pct']}% |")
    lines.append("")

    lines.append("## CMC Distribution")
    lines.append("")
    lines.append("| CMC | Total | Creatures | Non-Creatures |")
    lines.append("|-----|------:|----------:|--------------:|")
    curve = stats.get("cmc_curve", {})
    for b in curve.get("buckets", []):
        cr = curve["creature"].get(b, 0)
        nc = curve["noncreature"].get(b, 0)
        lines.append(f"| {b} | {cr + nc} | {cr} | {nc} |")
    lines.append("")

    lines.append("## Rarity")
    lines.append("")
    lines.append("| Rarity | Count | % |")
    lines.append("|--------|------:|--:|")
    rb = stats.get("rarity_breakdown", {})
    for rarity, v in rb.items():
        lines.append(f"| {rarity.capitalize()} | {v['count']} | {v['pct']}% |")
    lines.append("")

    lines.append("## Card Types")
    lines.append("")
    lines.append("| Type | Count | % |")
    lines.append("|------|------:|--:|")
    ct = stats.get("card_type_breakdown", {})
    for t, v in ct.items():
        lines.append(f"| {t} | {v['count']} | {v['pct']}% |")
    lines.append("")

    guild = stats.get("guild_breakdown")
    if guild:
        guild_names = {
            "WU": "Azorius (WU)", "WB": "Orzhov (WB)", "WR": "Boros (WR)",
            "WG": "Selesnya (WG)", "UB": "Dimir (UB)", "UR": "Izzet (UR)",
            "UG": "Simic (UG)", "BR": "Rakdos (BR)", "BG": "Golgari (BG)",
            "RG": "Gruul (RG)", "3+": "3+ color",
        }
        lines.append("## Guild Breakdown")
        lines.append("")
        lines.append("| Guild | Count |")
        lines.append("|-------|------:|")
        for key, label in guild_names.items():
            lines.append(f"| {label} | {guild.get(key, 0)} |")
        lines.append("")

    # Archetype clusters
    archetypes = stats.get("archetype_clusters")
    if archetypes and archetypes.get("clusters"):
        lines.append("## Archetype Clusters")
        lines.append("")
        lines.append("| Archetype | Count | % | Support |")
        lines.append("|-----------|------:|--:|:--------|")
        for c in archetypes["clusters"]:
            lines.append(f"| {c['name']} | {c['count']} | {c['pct']}% | {c['support']} |")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path

"""Cube dossier — deck-independent facts about a cube, computed once and cached.

The dossier answers "what is true about this cube", never "what is good in this deck".
It is built before any deck exists, so it structurally cannot carry a finding about one.
Card-quality verdicts are a property of the (card, list) pair and belong to whoever owns
the list; they never appear here.

Copy-count agnostic: pool rules (multipliers, exclusions) vary per run, so the dossier
describes the cube mainboard itself and leaves copy math to the caller.

The `interaction_chains` key is the one section no script can produce — it is authored
during cube investigation and merged into this file. Regenerating the census preserves it.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from .cube import Card, Cube, cube_dir, load_enriched, load_meta

DOSSIER_FILENAME = "dossier.json"

# Bump whenever census semantics change: a cached dossier built under older semantics
# is invalid even if the cube itself has not changed (load_dossier discards it).
DOSSIER_VERSION = 4

# A regex census can prove presence. It cannot prove absence. Every consumer of this
# file must read pool_limits through this caveat.
CENSUS_CAVEAT = (
    "Every census entry is a regex probe over oracle text. A probe that matched 0 cards proves "
    "nothing: no-match is not the same as does-not-exist. Only positive matches, with the oracle "
    "text they matched, are facts. Never treat a 0-match line as a hard constraint on what a deck "
    "can do — verify against the actual oracle text in your pool before relying on it."
)

# The same asymmetry applies to the authored layer: a chain proves an engine exists;
# no chain proves nothing.
CHAINS_CAVEAT = (
    "interaction_chains is an authored, known-incomplete list. Absence of a chain is not absence "
    "of an engine — the cube may contain engines no chain records. Derive card compositions from "
    "oracle text first; use chains as recorded evidence of engines that exist, never as the "
    "boundary of what exists."
)

# ── Oracle-text probes ────────────────────────────────────────────────────────
# Every probe below is a syntactic match on oracle text. None of them judges a card.

_ADD_MANA_RE = re.compile(r"Add ((?:\{[^}]+\})+)", re.IGNORECASE)
_ADD_X_MANA_RE = re.compile(r"Add [X\d]+ mana", re.IGNORECASE)
_ACTIVATED_RE = re.compile(r"\{T\}[,:]|^\{[^}]+\}[,:]", re.MULTILINE)
_COST_REDUCER_RE = re.compile(r"cost \{[^}]+\} less to cast", re.IGNORECASE)
_SWEEPER_RE = re.compile(
    r"(destroy all|destroy each|deals? [\w\s]*damage to each [^.]*creature|"
    r"each creature gets -\d+/-\d+|all creatures get -\d+/-\d+)",
    re.IGNORECASE,
)
_GRANTS_HASTE_RE = re.compile(r"(gains? haste|have haste|has haste)", re.IGNORECASE)
# Hate exiles somebody ELSE's graveyard. Exiling your own cards as an activation cost
# (Grim Lavamancer, Body Snatcher) is fuel, not hate — do not count it.
_GY_HATE_RE = re.compile(
    r"exile (?:target (?:player|opponent)'?s?|all|each (?:player|opponent)'?s?) graveyards?",
    re.IGNORECASE,
)
_TUTOR_RE = re.compile(r"search your library", re.IGNORECASE)
# A Lair swaps a land rather than adding one — it does not raise your battlefield land count.
_SELF_BOUNCE_LAND_RE = re.compile(r"sacrifice it unless you return a[^.]*land", re.IGNORECASE)
_MANA_IN_COST_RE = re.compile(r"\{[WUBRGCXS0-9]")
_LIFEGAIN_RE = re.compile(r"gains? \d+ life|gain life", re.IGNORECASE)
_ENTERS_TAPPED_RE = re.compile(r"enters tapped|enters the battlefield tapped", re.IGNORECASE)
_CONDITIONAL_TAPPED_RE = re.compile(r"enters tapped unless", re.IGNORECASE)
_EVASION_RE = re.compile(r"\b(flying|shadow|fear|intimidate|menace)\b|can't be blocked", re.IGNORECASE)

_ARTIFACT_ANSWER_RE = re.compile(
    r"(destroy|exile) target (artifact|artifact or enchantment|permanent)", re.IGNORECASE
)
_ENCHANTMENT_ANSWER_RE = re.compile(
    r"(destroy|exile) target (enchantment|artifact or enchantment|permanent)", re.IGNORECASE
)

_MANA_SYMBOL_RE = re.compile(r"\{([^}]+)\}")

# `produces` (which colours a land can make) must capture alternation: "Add {U} or {R}" and
# "Add {U}, {B}, or {R}" list every option. This is deliberately different from _mana_added, which
# measures the AMOUNT of a single tap (a dual adds one mana, not two) and so must stay narrow.
# The clause span stops at the first sentence break so "Add {C}. {2}, {T}, Sacrifice..." reads {C}
# only. Known gap: "Add one mana of any color" (Gemstone Mine) carries no symbol and yields [].
_ADD_CLAUSE_RE = re.compile(r"Add ([^.\n;]*)", re.IGNORECASE)
_MANA_COLOR_RE = re.compile(r"\{([WUBRGC])\}")


def land_colors(oracle: str) -> List[str]:
    """Colours a land can add, in WUBRG(+C) order. Captures 'or'/comma alternation.

    Public and shared: `cuber.deck_counts.pip_sources` counts a deck's mana sources through this
    same function, so the census and the deck-count validator agree by construction.
    """
    colors = set()
    for clause in _ADD_CLAUSE_RE.finditer(oracle):
        colors.update(_MANA_COLOR_RE.findall(clause.group(1)))
    return [c for c in "WUBRGC" if c in colors]


def _text(card: Card) -> str:
    return card.oracle_text or ""


def _is_land(card: Card) -> bool:
    return "Land" in (card.type_line or "")


def _is_basic_land(card: Card) -> bool:
    return "Basic Land" in (card.type_line or "")


def _color_key(card: Card) -> str:
    """Colorless -> 'C'; otherwise WUBRG-ordered identity, e.g. 'BR'."""
    ci = card.color_identity or []
    if not ci:
        return "C"
    return "".join(c for c in "WUBRG" if c in ci)


def _mana_added(oracle: str) -> Optional[int]:
    """Max mana a single 'Add ...' clause produces. None if variable (Add X mana)."""
    if _ADD_X_MANA_RE.search(oracle):
        return None
    best = 0
    for match in _ADD_MANA_RE.finditer(oracle):
        best = max(best, len(_MANA_SYMBOL_RE.findall(match.group(1))))
    return best or None


def _sacrifice_outlets(card: Card) -> List[Dict[str, Any]]:
    """Activated abilities that sacrifice a permanent. `free` means no mana in the activation cost.

    Matches on the cost half of `<cost>: <effect>`, so 'Pay 1 life, Sacrifice another creature:'
    is recognised as free while '{1}{R}, Sacrifice a Goblin:' is not.
    """
    outlets = []
    for line in _text(card).split("\n"):
        if ":" not in line:
            continue
        cost = line.split(":", 1)[0]
        if not re.search(r"Sacrifice (?:a|an|another|two|three) ", cost, re.IGNORECASE):
            continue
        outlets.append({
            "name": card.name,
            "cost": cost.strip(),
            "free": not bool(_MANA_IN_COST_RE.search(cost)),
        })
    return outlets


def _subtypes(card: Card) -> List[str]:
    """Creature subtypes after the em-dash, e.g. 'Creature — Zombie Goblin' -> [Zombie, Goblin]."""
    tl = card.type_line or ""
    if "Creature" not in tl or "—" not in tl:
        return []
    return tl.split("—", 1)[1].strip().split()


# ── Census sections ───────────────────────────────────────────────────────────

def _environment(cards: List[Card]) -> Dict[str, Any]:
    nonland = [c for c in cards if not _is_land(c)]
    dist: Counter = Counter()
    for c in nonland:
        ci = c.color_identity or []
        dist["C" if not ci else (ci[0] if len(ci) == 1 else "Multi")] += 1

    tags: Counter = Counter()
    for c in cards:
        for t in c.tags:
            tags[t] += 1

    n = len(nonland) or 1
    signals = {}
    for mech in ("domain", "kicker", "converge", "sunburst", "vivid"):
        hits = sum(1 for c in nonland if mech in _text(c).lower())
        signals[mech] = {"count": hits, "density": round(hits / n, 4)}

    return {
        "total_cards": len(cards),
        "nonland_cards": len(nonland),
        "color_distribution": dict(dist),
        "top_tags": dict(tags.most_common(12)),
        "multicolor_reward_signals": signals,
    }


def _mana_infrastructure(cards: List[Card]) -> Dict[str, Any]:
    lands = [c for c in cards if _is_land(c)]
    by_identity: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for c in lands:
        oracle = _text(c)
        by_identity[_color_key(c)].append({
            "name": c.name,
            "rarity": c.rarity,
            "type_line": c.type_line,
            "enters_tapped": bool(_ENTERS_TAPPED_RE.search(oracle)),
            "conditionally_tapped": bool(_CONDITIONAL_TAPPED_RE.search(oracle)),
            # A Lair returns a land to hand to stay — it swaps a land rather than adding one,
            # so it does not raise your battlefield land count.
            "self_bounce": bool(_SELF_BOUNCE_LAND_RE.search(oracle)),
            "produces": land_colors(oracle),
        })

    # Dual availability per colour pair — the fixing question, stated as counts only.
    # `free` excludes self-bouncing Lairs: they fix, but at the cost of a land drop.
    pairs: Dict[str, Dict[str, Any]] = {}
    for a_i, a in enumerate("WUBRG"):
        for b in "WUBRG"[a_i + 1:]:
            pair = a + b
            matches = [
                land for key, group in by_identity.items()
                for land in group
                if a in key and b in key
            ]
            free = [m for m in matches if not m["self_bounce"]]
            pairs[pair] = {
                "total": len(matches),
                "free": len(free),
                "self_bouncing": len(matches) - len(free),
                "by_rarity": dict(Counter(m["rarity"] for m in free)),
                "untapped_capable": sum(
                    1 for m in free if not m["enters_tapped"] or m["conditionally_tapped"]
                ),
                "names": sorted(m["name"] for m in free),
                "lair_names": sorted(m["name"] for m in matches if m["self_bounce"]),
            }

    return {
        "basics_in_pool": any(_is_basic_land(c) for c in cards),
        "total_lands": len(lands),
        "lands_by_identity": {k: v for k, v in sorted(by_identity.items())},
        "duals_by_pair": pairs,
        "three_plus_color_lands": sorted(
            c.name for c in lands if len(c.color_identity or []) >= 3
        ),
    }


def _structural_census(cards: List[Card]) -> Dict[str, Any]:
    nonland = [c for c in cards if not _is_land(c)]

    mana_producers, rituals = [], []
    for c in nonland:
        oracle = _text(c)
        if not (_ADD_MANA_RE.search(oracle) or _ADD_X_MANA_RE.search(oracle)):
            continue
        added = _mana_added(oracle)
        repeatable = bool(_ACTIVATED_RE.search(oracle))
        entry = {
            "name": c.name, "cmc": c.cmc, "type_line": c.type_line,
            "mana_added": added, "repeatable": repeatable,
            "net_mana": (added - c.cmc) if added is not None else None,
        }
        mana_producers.append(entry)
        # A ritual nets you mana on the turn you spend it. Repeatable sources are not rituals.
        if added is not None and not repeatable and added > c.cmc:
            rituals.append(entry)

    def _names(pred) -> List[str]:
        return sorted(c.name for c in nonland if pred(c))

    cost_reducers = [
        {"name": c.name, "cmc": c.cmc,
         "clause": _COST_REDUCER_RE.search(_text(c)).group(0),
         "restricted": "spells cost" not in _text(c).lower().split("\n")[0]}
        for c in nonland if _COST_REDUCER_RE.search(_text(c))
    ]

    outlets: List[Dict[str, Any]] = []
    for c in nonland:
        outlets.extend(_sacrifice_outlets(c))

    return {
        "rituals": {"count": len(rituals), "cards": rituals},
        "mana_producers": {"count": len(mana_producers), "cards": mana_producers},
        "cost_reducers": {"count": len(cost_reducers), "cards": cost_reducers},
        "sacrifice_outlets": {
            "count": len(outlets),
            "free_count": sum(1 for o in outlets if o["free"]),
            "cards": outlets,
        },
        "tutors": _names(lambda c: _TUTOR_RE.search(_text(c))),
        "sweepers": _names(lambda c: _SWEEPER_RE.search(_text(c))),
        "haste_granters": _names(lambda c: _GRANTS_HASTE_RE.search(_text(c))),
        "graveyard_hate": _names(lambda c: _GY_HATE_RE.search(_text(c))),
    }


def _tribal_rosters(cards: List[Card], min_members: int = 4) -> Dict[str, Any]:
    """Creature-type rosters, split by colour identity — 'how many Goblins, and in which colours'."""
    by_type: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    for c in cards:
        for st in _subtypes(c):
            by_type[st][_color_key(c)].append(c.name)

    out = {}
    for tribe, by_color in by_type.items():
        total = sum(len(v) for v in by_color.values())
        if total >= min_members:
            out[tribe] = {
                "total": total,
                "by_color": {k: sorted(v) for k, v in sorted(by_color.items())},
            }
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["total"]))


def _threat_profile(cards: List[Card]) -> Dict[str, Any]:
    """What the cube's OTHER decks can do. This is what a sideboard is built against."""
    nonland = [c for c in cards if not _is_land(c)]
    n = len(nonland) or 1

    def _bucket(pred) -> Dict[str, Any]:
        hits = [c for c in nonland if pred(c)]
        by_color: Counter = Counter(_color_key(c) for c in hits)
        return {
            "count": len(hits),
            "density": round(len(hits) / n, 4),
            "by_color": dict(sorted(by_color.items())),
            "names": sorted(c.name for c in hits),
        }

    return {
        "graveyard_interaction": _bucket(lambda c: "graveyard" in _text(c).lower()),
        "artifacts": _bucket(lambda c: "Artifact" in (c.type_line or "")),
        "enchantments": _bucket(lambda c: "Enchantment" in (c.type_line or "")),
        "sweepers": _bucket(lambda c: _SWEEPER_RE.search(_text(c))),
        "lifegain": _bucket(lambda c: _LIFEGAIN_RE.search(_text(c))),
        "evasion": _bucket(lambda c: _EVASION_RE.search(_text(c))),
        "artifact_answers": _bucket(lambda c: _ARTIFACT_ANSWER_RE.search(_text(c))),
        "enchantment_answers": _bucket(lambda c: _ENCHANTMENT_ANSWER_RE.search(_text(c))),
    }


def _pool_limits(census: Dict[str, Any], mana: Dict[str, Any], threat: Dict[str, Any]) -> List[str]:
    """Probe results a deck would otherwise re-derive badly.

    Positive findings (cards named, oracle-backed) are facts. Zero-match findings are
    reported as exactly that — which probe matched nothing — never as an impossibility:
    the ritual probe cannot see untap-lands effects, mana multipliers, or free spells,
    and asserting "storm cannot be accelerated" from it once poisoned a whole session.
    """
    limits: List[str] = []

    if census["rituals"]["count"] == 0:
        limits.append(
            "Ritual probe (a nonland 'Add ...' clause producing more mana than the card's cost, "
            "non-repeatable) matched 0 cards. No-match is not does-not-exist: this probe cannot "
            "see untap-lands effects, mana multipliers, cost reducers, or free spells, which can "
            "accelerate mana just as well. Check the pool's oracle text before treating "
            "acceleration as unavailable."
        )
    if not census["haste_granters"]:
        limits.append(
            "Haste-grant probe ('gains/have/has haste') matched 0 cards. No-match is not "
            "does-not-exist: effects phrased differently (e.g. 'can attack as though it had "
            "haste', unearth, dash) are invisible to this probe."
        )

    lairs = sorted({
        land["name"]
        for group in mana["lands_by_identity"].values()
        for land in group if land["self_bounce"]
    })
    if lairs:
        limits.append(
            f"{len(lairs)} lands are Lairs ({', '.join(lairs)}): each returns a land you control to "
            "your hand, so it swaps a land rather than adding one and does not raise your "
            "battlefield land count."
        )

    if not mana["basics_in_pool"]:
        limits.append(
            "The cube list contains no basic lands. Basics are format-supplied and exempt from "
            "copy limits; every nonbasic land in the pool is listed under lands_by_identity."
        )

    # Answer gaps by colour — the probe result that drives sideboard construction.
    for label, key in (("artifact", "artifact_answers"), ("enchantment", "enchantment_answers")):
        colors_with = {c for k in threat[key]["by_color"] for c in k if c != "C"}
        missing = sorted(set("WUBRG") - colors_with)
        if missing:
            limits.append(
                f"{label.capitalize()}-removal probe ('destroy/exile target {label}...') matched "
                f"0 mono-colour cards in: {', '.join(missing)}. No-match is not does-not-exist: "
                f"sacrifice effects, bounce, theft, or -X/-X are invisible to this probe. Verify "
                f"before concluding those colours cannot answer {label}s."
            )
    return limits


# ── Public API ────────────────────────────────────────────────────────────────

def dossier_path(short_id: str) -> str:
    return os.path.join(cube_dir(short_id), DOSSIER_FILENAME)


def _fingerprint(short_id: str) -> Dict[str, Any]:
    meta = load_meta(short_id)
    return {"card_count": meta.get("card_count"), "fetched_at": meta.get("fetched_at")}


def build_dossier(id_or_slug: str) -> Dict[str, Any]:
    """Compute the machine census. Preserves any authored interaction_chains already on disk."""
    cube: Cube = load_enriched(id_or_slug)
    cards = [c for c in cube.cards if (c.board or "mainboard") == "mainboard"]

    environment = _environment(cards)
    mana = _mana_infrastructure(cards)
    census = _structural_census(cards)
    threat = _threat_profile(cards)

    existing = load_dossier(id_or_slug, validate=False) or {}

    return {
        "dossier_version": DOSSIER_VERSION,
        "cube_fingerprint": _fingerprint(id_or_slug),
        "census_caveat": CENSUS_CAVEAT,
        "environment": environment,
        "mana_infrastructure": mana,
        "structural_census": census,
        "tribal_rosters": _tribal_rosters(cards),
        "threat_profile": threat,
        "pool_limits": _pool_limits(census, mana, threat),
        # Authored during cube investigation; no script can derive these. Preserved on rebuild.
        "chains_caveat": CHAINS_CAVEAT,
        "interaction_chains": existing.get("interaction_chains", []),
        # Set by the seed authoring pass (an agent reading the cube's oracle text); preserved here.
        "chains_seeded_at": existing.get("chains_seeded_at"),
    }


def save_dossier(dossier: Dict[str, Any], id_or_slug: str) -> str:
    path = dossier_path(id_or_slug)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dossier, f, ensure_ascii=False, indent=1)
    return path


def load_dossier(id_or_slug: str, validate: bool = True) -> Optional[Dict[str, Any]]:
    """Return the cached dossier, or None if absent or (when validate) stale against meta.json."""
    path = dossier_path(id_or_slug)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        dossier = json.load(f)
    if validate and (
        dossier.get("cube_fingerprint") != _fingerprint(id_or_slug)
        or dossier.get("dossier_version") != DOSSIER_VERSION
    ):
        return None
    return dossier


def format_dossier_summary(dossier: Dict[str, Any]) -> str:
    env = dossier["environment"]
    mana = dossier["mana_infrastructure"]
    census = dossier["structural_census"]
    lines = [
        "── Cube Dossier ────────────────────────────────────────────",
        f"Cards: {env['total_cards']}  ({env['nonland_cards']} nonland, {mana['total_lands']} lands)",
        f"Colors: {env['color_distribution']}",
        f"Basics in pool: {mana['basics_in_pool']}",
        "",
        f"Rituals: {census['rituals']['count']}   "
        f"Cost reducers: {census['cost_reducers']['count']}   "
        f"Sweepers: {len(census['sweepers'])}   "
        f"Haste granters: {len(census['haste_granters'])}",
        f"Sac outlets: {census['sacrifice_outlets']['count']} "
        f"({census['sacrifice_outlets']['free_count']} free)   "
        f"Tutors: {len(census['tutors'])}   "
        f"GY hate: {len(census['graveyard_hate'])}",
        "",
        "Tribes (>=4):",
    ]
    for tribe, data in list(dossier["tribal_rosters"].items())[:8]:
        colors = " ".join(f"{k}:{len(v)}" for k, v in data["by_color"].items())
        lines.append(f"  {tribe:<14} {data['total']:>2}   {colors}")

    lines += ["", "Dual lands by pair (free = excludes self-bouncing Lairs):"]
    for pair, d in dossier["mana_infrastructure"]["duals_by_pair"].items():
        if d["total"]:
            rar = " ".join(f"{k[0].upper()}{v}" for k, v in sorted(d["by_rarity"].items())) or "-"
            lines.append(
                f"  {pair}  free: {d['free']} ({rar})  untapped-capable: {d['untapped_capable']}"
                f"  +{d['self_bouncing']} Lair"
            )

    lines += ["", "Pool limits (probe results — see census_caveat; 0-match proves nothing):"]
    lines += [f"  - {lim}" for lim in dossier["pool_limits"]]
    seeded = dossier.get("chains_seeded_at") or "never"
    lines += ["", f"Interaction chains authored: {len(dossier['interaction_chains'])} "
                  f"(seeded: {seeded}; a floor, not coverage — see chains_caveat)"]
    return "\n".join(lines)

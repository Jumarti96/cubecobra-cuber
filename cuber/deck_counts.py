"""Deterministic count predicates over a deck-card list — the single source of truth for
every count a build cites.

The build computes its quantitative-verdict numerators/denominators by calling these functions,
and records the *recipe* (`numerator_spec` / `denominator_spec`) next to each stored integer.
The Phase 5D validator recomputes with the SAME functions via `check_verdicts` and asserts equality.
Build and validator therefore cannot disagree, and a count lives in exactly one place — it is never
hand-typed into a `role`, `reason`, or `claim` string.

A "deck card" is a dict with at least: `name`, `type_line`, `oracle_text`, `mana_cost`, `colors`,
`cmc`. Precomputed `pips` / `has_generic` / `subtypes` are used when present and derived from
`mana_cost` / `type_line` otherwise, so every function works on both `legal_pool` records and
synthesised basic lands.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Sequence

from cuber.dossier import land_colors  # shared colour extraction; fixes dual-land truncation

Card = Dict[str, Any]

_GENERIC_RE = re.compile(r"\{(?:\d+|X)\}")
_PIP_RE = re.compile(r"\{([WUBRGC])\}")
_SUBTYPE_DASH = "—"  # em-dash


# ── field access (precomputed when available, derived otherwise) ──────────────

def _is_land(c: Card) -> bool:
    return "Land" in (c.get("type_line") or "")


def _mana_cost(c: Card) -> str:
    return c.get("mana_cost") or ""


def _has_generic(c: Card) -> bool:
    if "has_generic" in c and c["has_generic"] is not None:
        return bool(c["has_generic"])
    return bool(_GENERIC_RE.search(_mana_cost(c)))


def _pips(c: Card) -> Dict[str, int]:
    if isinstance(c.get("pips"), dict):
        return c["pips"]
    d: Dict[str, int] = {}
    for p in _PIP_RE.findall(_mana_cost(c)):
        d[p] = d.get(p, 0) + 1
    return d


def _subtypes(c: Card) -> List[str]:
    if isinstance(c.get("subtypes"), list):
        return c["subtypes"]
    tl = c.get("type_line") or ""
    if _SUBTYPE_DASH not in tl:
        return []
    return tl.split(_SUBTYPE_DASH, 1)[1].strip().split()


# ── predicates ────────────────────────────────────────────────────────────────
# Each returns an int. Syntactic predicates (types, subtypes, pips, generic component) are exact.
# `oracle_matches` lets a build express a text-based count as a shared regex both callers run
# identically — the count is then reproducible even where the notion is interpretive.

def nonland(deck: Sequence[Card]) -> int:
    return sum(1 for c in deck if not _is_land(c))


def lands(deck: Sequence[Card]) -> int:
    return sum(1 for c in deck if _is_land(c))


def zero_cost(deck: Sequence[Card]) -> int:
    """Nonland cards that cost nothing (mv 0) — the cards Helm-style reducers cannot discount."""
    return sum(1 for c in deck if not _is_land(c) and (c.get("cmc") or 0) == 0)


def instants_sorceries(deck: Sequence[Card]) -> int:
    return sum(1 for c in deck
               if any(t in (c.get("type_line") or "") for t in ("Instant", "Sorcery")))


def subtype_count(deck: Sequence[Card], sub: str) -> int:
    """Cards whose creature/land subtypes include `sub` (e.g. 'Goblin')."""
    return sum(1 for c in deck if sub in _subtypes(c))


def type_typed_lands(deck: Sequence[Card], t: str) -> int:
    """Lands whose type line carries the land type `t` (e.g. 'Island', 'Mountain')."""
    return sum(1 for c in deck if _is_land(c) and t in (c.get("type_line") or ""))


def generic_reducible(deck: Sequence[Card], exclude: Sequence[str] = ()) -> int:
    """Nonland cards a `{1}`-less cost reducer can actually discount: a generic component AND mv > 0.

    The `cmc > 0` guard is the Ornithopter case — a `{0}` cost cannot be reduced below zero even
    though its mana cost technically contains no colored pip. `exclude` drops the reducer itself.
    """
    ex = set(exclude)
    return sum(1 for c in deck
               if not _is_land(c) and c.get("name") not in ex
               and _has_generic(c) and (c.get("cmc") or 0) > 0)


def color_cards(deck: Sequence[Card], color: str) -> int:
    """Nonland cards whose base cost colours include `color` (e.g. Force of Will pitch fodder)."""
    return sum(1 for c in deck if not _is_land(c) and color in (c.get("colors") or []))


def pip_sum(deck: Sequence[Card], color: str) -> int:
    return sum(_pips(c).get(color, 0) for c in deck if not _is_land(c))


def pip_sources(deck: Sequence[Card], color: str) -> int:
    """Lands that can add `color`, counting a dual in every colour it makes (via `land_colors`)."""
    return sum(1 for c in deck if _is_land(c) and color in land_colors(c.get("oracle_text") or ""))


def oracle_matches(deck: Sequence[Card], pattern: str) -> int:
    rx = re.compile(pattern, re.IGNORECASE)
    return sum(1 for c in deck if rx.search(c.get("oracle_text") or ""))


# ── dispatch + verdict checking ───────────────────────────────────────────────

_REGISTRY: Dict[str, Callable[..., int]] = {
    "nonland": nonland,
    "lands": lands,
    "zero_cost": zero_cost,
    "instants_sorceries": instants_sorceries,
    "subtype_count": subtype_count,
    "type_typed_lands": type_typed_lands,
    "generic_reducible": generic_reducible,
    "color_cards": color_cards,
    "pip_sum": pip_sum,
    "pip_sources": pip_sources,
    "oracle_matches": oracle_matches,
}


def resolve(deck: Sequence[Card], spec: Any) -> int:
    """Resolve a count spec to an int.

    `spec` is either a bare int (a literal denominator like a fixed deck size) or a dict:
      {"predicate": <name>, "args": [...], "offset": <int>}
    `offset` expresses a count relative to a predicate, e.g. nonland - 1 (cards other than this one).
    """
    if isinstance(spec, int):
        return spec
    if not isinstance(spec, dict):
        raise TypeError(f"count spec must be int or dict, got {type(spec).__name__}")
    name = spec["predicate"]
    fn = _REGISTRY.get(name)
    if fn is None:
        raise KeyError(f"unknown count predicate: {name!r}")
    return fn(deck, *spec.get("args", [])) + spec.get("offset", 0)


def compute(deck: Sequence[Card], specs: Dict[str, Any]) -> Dict[str, int]:
    """Resolve a {label: spec} map to {label: int}."""
    return {label: resolve(deck, spec) for label, spec in specs.items()}


def check_verdicts(deck: Sequence[Card], verdicts: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Recompute each verdict's numerator/denominator from its spec and compare to the stored int.

    Returns a list of mismatch dicts (empty means every verdict reproduces). A verdict may carry
    `numerator_spec` / `denominator_spec`; a side without a spec is skipped (nothing to check).
    """
    problems: List[Dict[str, Any]] = []
    for v in verdicts:
        for side in ("numerator", "denominator"):
            spec = v.get(side + "_spec")
            if spec is None:
                continue
            recomputed = resolve(deck, spec)
            if recomputed != v.get(side):
                problems.append({
                    "card": v.get("card"),
                    "side": side,
                    "stated": v.get(side),
                    "recomputed": recomputed,
                    "spec": spec,
                })
    return problems


# ── prose count-digit guard (Phase 5D check 8) ────────────────────────────────
# Catches the RATIO frames where stale counts actually appeared ("17 of the other 25",
# "8 Island-typed", "out of 16 lands"). These are false-positive-free: intrinsic card numbers
# ({R}{R}, "4 damage", "2 extra turns", "2/2", copy counts like "x2") never take these shapes.
# A bare "N noun" ("10 Goblins", "5 lands") is deliberately NOT matched — it is ambiguous between a
# list count and a card-intrinsic quantity (tokens made, lands untapped). The primary guarantee is
# check 6 (every load-bearing count is a spec-backed verdict recomputed by `check_verdicts`); this
# guard is the secondary net for ratio prose.
_COUNT_FRAME_RE = re.compile(
    r"\b\d+\s+of\s+(?=\w)"                  # "17 of ", "16 of the ", "5 of 14"
    r"|\bout\s+of\s+\d+\b"                  # "out of 16"
    r"|\b\d+\s+\w+-typed\b"                 # "8 Island-typed"
)


def count_digits_in_prose(text: str) -> List[str]:
    """Return every ratio-style count frame in `text` (empty means clean).

    Used by the validator to reject ratio counts hand-typed into `role` / `reason` / `claim`
    strings: such counts belong in a quantitative verdict (recomputed by `check_verdicts`), never
    inline prose.
    """
    return _COUNT_FRAME_RE.findall(text or "")

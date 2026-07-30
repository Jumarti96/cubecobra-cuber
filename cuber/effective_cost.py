"""Effective color/cost model for alternate-cost cards.

A card's printed ``color_identity`` is a blunt proxy for "can I use this card in
my colors." It misfires for cards whose *usable mode* costs different (or no)
colored mana than the printed cost:

  * **Street Wraith** (``{3}{B}{B}``, identity ``B``) is never cast -- its only
    used mode is ``Cycling--Pay 2 life``, a colorless ability. It is a fine
    cycler in any deck, yet the raw-identity gate excludes it from every non-black
    one.
  * **Orim's Thunder** (``{2}{W}``, kicker ``{R}`` -> identity ``WR``) is castable
    in mono-white by declining the kicker, yet the raw-identity gate treats it as
    a two-color card.

``usable_modes(card)`` enumerates every way the card can be put to use, each with
the colored pips that mode actually demands. ``best_mode(card, core, splash)``
picks the mode that makes the card usable in a given colour set, *preferring the
normal cast* so an in-colour card that merely also cycles is not mislabeled a
"cycler". Both the pool eligibility gate (``cube_search.search_pool``) and the
mana audit (``deck_audit.mana_audit``) call these, so the two gates cannot drift
apart -- there is one definition of "usable here", not a scatter of per-mechanic
special cases.

First cut: only **unconditional** modes gate eligibility (base cast, cycling,
kicker-decline). Conditional modes -- flashback / madness / escape / evoke, which
need a graveyard or a discard outlet before they can be used -- are still parsed
and returned with ``conditional=True``, but ``best_mode`` ignores them. They are
the documented extension point for a later *valuation* pass (e.g. counting Deep
Analysis's flashback re-cast in a storm deck); admitting them by default would let
a card in on a mode it can only sometimes reach, which is exactly the false-
inclusion risk we want to avoid for now.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

_COLORS = frozenset("WUBRG")

# A single colored pip: {W}, {U}, ... Deliberately does NOT match generic ({2}),
# variable ({X}), or hybrid ({W/U}) symbols -- those demand no one fixed colour.
# Hybrid is a known first-cut gap (none of the cards this targets use it).
_PIP_RE = re.compile(r"\{([WUBRG])\}")

# Any mana symbol, for computing a cost's mana value.
_SYMBOL_RE = re.compile(r"\{([^}]+)\}")

# A cost clause is a run of mana symbols, optionally preceded by an em-dash or
# hyphen (``Flashback--{1}{U}``, ``Escape--{3}{B}{B}``). A non-mana alternative
# cost (``Cycling--Pay 2 life``) simply yields zero symbols -> no colored pips.
_COST = r"(?P<cost>(?:\{[^}]+\}\s*)*)"

# Cycling / typecycling: a *replacement* mode used instead of casting. ``\w*``
# absorbs the land-type prefix of typecycling (``Forestcycling``); plain
# ``Cycling`` matches with an empty prefix.
_CYCLING_RE = re.compile(r"\b\w*cycling\b[\s—-]*" + _COST, re.IGNORECASE)

# Conditional alternate modes -- parsed but NOT admitted in the first cut.
_CONDITIONAL_RES = [
    ("madness", re.compile(r"\bmadness\b[\s—-]*" + _COST, re.IGNORECASE)),
    ("flashback", re.compile(r"\bflashback\b[\s—-]*" + _COST, re.IGNORECASE)),
    ("escape", re.compile(r"\bescape\b[\s—-]*" + _COST, re.IGNORECASE)),
    ("evoke", re.compile(r"\bevoke\b[\s—-]*" + _COST, re.IGNORECASE)),
]


def _strip_reminders(text: str) -> str:
    """Drop parenthetical reminder text.

    Reminder text routinely *repeats* the pips of the ability it explains
    (``Cycling {1}{W} ({1}{W}, Discard this card: Draw a card.)``). Parsing it
    would double-count, and it can also smuggle an unrelated cost into the wrong
    clause, so remove it before reading any cost.
    """
    return re.sub(r"\([^)]*\)", "", text)


def _pip_list(cost: str) -> List[str]:
    """Colored pips of a cost string, WITH multiplicity ({R}{R} -> ['R','R'])."""
    return _PIP_RE.findall(cost)


def _cost_mana_value(cost: str) -> float:
    """Mana value of a cost string: generic numbers plus one per colored/hybrid
    symbol. ``{X}`` counts 0; a non-mana cost (no symbols) is 0."""
    total = 0
    for sym in _SYMBOL_RE.findall(cost):
        s = sym.strip()
        if s.isdigit():
            total += int(s)
        elif s in ("X", "Y", "Z"):
            total += 0
        else:  # colored, hybrid, phyrexian, snow -- one mana each
            total += 1
    return float(total)


def colored_pips(mana_cost: str) -> Set[str]:
    """Set of colored pips in a printed mana cost (display / subset tests)."""
    return set(_PIP_RE.findall(mana_cost or ""))


def _mode(name: str, cost: str, cmc: float, conditional: bool) -> Dict[str, Any]:
    pips = _pip_list(cost)
    return {
        "mode": name,
        "pips": pips,                 # with multiplicity, for pip-demand math
        "cost_pips": set(pips),       # deduped, for subset eligibility tests
        "cmc": cmc,
        "conditional": conditional,
    }


def usable_modes(card: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every mode by which ``card`` can be put to use, cheapest info attached.

    Each mode is ``{mode, pips, cost_pips, cmc, conditional}``. The first entry is
    always the base cast (a land's is its produced identity). Replacement and
    optional-additional modes follow.
    """
    type_line = card.get("type_line") or ""
    printed_cmc = float(card.get("cmc") or 0)

    # Lands are played, not cast: their "requirement" is the colour they produce,
    # i.e. their identity. Keeping the raw-identity behaviour for lands is what
    # stops an off-colour dual (empty mana_cost -> no pips) from looking free.
    if "land" in type_line.lower():
        return [{
            "mode": "land",
            "pips": list(card.get("color_identity") or []),
            "cost_pips": set(card.get("color_identity") or []),
            "cmc": printed_cmc,
            "conditional": False,
        }]

    # Base cast. ``mana_cost`` is already the base cost -- optional additional
    # costs (kicker / multikicker / buyback / entwine) live only in the oracle
    # text, so declining them is automatic and we never add the kicked mode.
    modes = [_mode("cast", card.get("mana_cost") or "", printed_cmc, False)]

    oracle = _strip_reminders(card.get("oracle_text") or "")

    for m in _CYCLING_RE.finditer(oracle):
        cost = m.group("cost") or ""
        modes.append(_mode("cycler", cost, _cost_mana_value(cost), False))

    for label, rx in _CONDITIONAL_RES:
        for m in rx.finditer(oracle):
            cost = m.group("cost") or ""
            modes.append(_mode(label, cost, _cost_mana_value(cost), True))

    return modes


def _tagged(mode: Dict[str, Any]) -> Dict[str, Any]:
    """Attach ``usable_as``: None for a normal cast/land, else the mode name."""
    out = dict(mode)
    out["usable_as"] = None if mode["mode"] in ("cast", "land") else mode["mode"]
    return out


def best_mode(
    card: Dict[str, Any],
    core_colors,
    splash_colors=None,
) -> Optional[Dict[str, Any]]:
    """The mode that makes ``card`` usable within ``core ∪ splash``, or None.

    Prefers a fully-usable **cast/land** mode over any alternate mode, so a normal
    in-colour card is never tagged as a "cycler" just because it happens to cycle.
    Only when the cast is off-colour does it fall back to the cheapest eligible
    alternate mode. Conditional modes never gate eligibility here.
    """
    allowed = set(core_colors) | set(splash_colors or [])
    eligible = [
        m for m in usable_modes(card)
        if not m["conditional"] and m["cost_pips"] <= allowed
    ]
    if not eligible:
        return None
    for m in eligible:
        if m["mode"] in ("cast", "land"):
            return _tagged(m)
    return _tagged(min(eligible, key=lambda x: x["cmc"]))


def effective_color_requirement(card: Dict[str, Any]) -> Set[str]:
    """The globally smallest colored footprint across unconditional modes.

    Display / reporting convenience only -- it collapses a multi-mode card to one
    set and so cannot express "usable in W via mode A, in R via mode B". The gate
    quantifies over ``usable_modes`` via ``best_mode``; never use this set as the
    gate.
    """
    modes = [m for m in usable_modes(card) if not m["conditional"]]
    if not modes:
        return set()
    return set(min(modes, key=lambda m: len(m["cost_pips"]))["cost_pips"])


# ── Keyword-mechanic tagging ──────────────────────────────────────────────────
#
# The LLM tagger already models a keyword ability as a `mechanical_function`
# (e.g. it tags a cycler with "Cycling" alongside "Card Draw") -- but it does so
# unreliably, catching only some cyclers and missing the rest. Keywords are
# mechanically exact strings, so a rule-based pass detects them with full
# coverage and *completes that same pillar* for the cards the LLM missed. It adds
# nothing the LLM's own convention wouldn't -- it just fills the gaps -- so it
# needs no change to the LLM prompt or the cluster vocabulary.
#
# Scope: this detects keyword *bearers* (a card that HAS cycling). It deliberately
# does NOT try to detect *payoffs* that reward a keyword (a card that triggers off
# "whenever you cycle") -- that remains a synergy judgment left to the LLM.

KEYWORD_TO_FUNCTION = {
    "cycling": "Cycling",
    "madness": "Madness",
    "kicker": "Kicker",
    "flashback": "Flashback",
    "escape": "Escape",
    "evoke": "Evoke",
}

# (keyword, presence detector). Reuses the cost-parsing regexes where they exist;
# detection only needs the keyword to appear (the cost clause is irrelevant here).
# Extend by adding a row plus a KEYWORD_TO_FUNCTION entry.
_KEYWORD_DETECT = [
    ("cycling", _CYCLING_RE),  # \w*cycling also catches typecycling (Forestcycling, ...)
    ("madness", re.compile(r"\bmadness\b", re.IGNORECASE)),
    ("kicker", re.compile(r"\b(?:multikicker|kicker)\b", re.IGNORECASE)),
    ("flashback", re.compile(r"\bflashback\b", re.IGNORECASE)),
    ("escape", re.compile(r"\bescape\b", re.IGNORECASE)),
    ("evoke", re.compile(r"\bevoke\b", re.IGNORECASE)),
]


def keyword_mechanics(card: Dict[str, Any]) -> Set[str]:
    """Mechanical-function labels for the keyword mechanics this card bears.

    These are the same free-form ``mechanical_functions`` values the LLM tagger
    emits for keyword abilities (``Cycling``, ``Madness``, ...). Reminder text is
    stripped first so a parenthetical ``(... Discard this card: Draw a card.)``
    cannot cause a false positive. Returns an empty set for a card with no keyword
    mechanic.
    """
    oracle = _strip_reminders(card.get("oracle_text") or "")
    found = set()
    for keyword, rx in _KEYWORD_DETECT:
        if rx.search(oracle):
            found.add(KEYWORD_TO_FUNCTION[keyword])
    return found

"""Commander eligibility detection and candidate finder."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .cube import load_enriched


_PARTNER_RE = re.compile(r"\bPartner\b(?! with)", re.IGNORECASE)
_PARTNER_WITH_RE = re.compile(r"\bPartner with ([\w ,'\-]+?)(?:\n|$|\()", re.IGNORECASE)
_FRIENDS_FOREVER_RE = re.compile(r"\bFriends forever\b", re.IGNORECASE)
_DOCTORS_COMPANION_RE = re.compile(r"\bDoctor's companion\b", re.IGNORECASE)
_BACKGROUND_RE = re.compile(r"\bChoose a Background\b", re.IGNORECASE)
_CAN_BE_COMMANDER_RE = re.compile(r"can be your commander", re.IGNORECASE)


def is_commander_eligible(card: Any) -> Dict[str, Any]:
    """Return eligibility dict for a Card object."""
    type_line = (card.type_line or "").lower()
    oracle = card.oracle_text or ""
    if "legendary creature" in type_line:
        return {"eligible": True, "reason": "Legendary Creature"}
    if _CAN_BE_COMMANDER_RE.search(oracle):
        return {"eligible": True, "reason": "oracle: can be your commander"}
    return {"eligible": False, "reason": "not a Legendary Creature or commander-eligible card"}


def _is_partner(oracle: str) -> bool:
    return bool(_PARTNER_RE.search(oracle))


def _partner_with_target(oracle: str) -> Optional[str]:
    m = _PARTNER_WITH_RE.search(oracle)
    return m.group(1).strip() if m else None


def _has_background(oracle: str) -> bool:
    return bool(_BACKGROUND_RE.search(oracle))


def _is_friends_forever(oracle: str) -> bool:
    return bool(_FRIENDS_FOREVER_RE.search(oracle))


def _is_doctors_companion(oracle: str) -> bool:
    return bool(_DOCTORS_COMPANION_RE.search(oracle))


def find_commanders(
    id_or_slug: str,
    color_identity: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Return commander-eligible cards from enriched.json, optionally filtered by color identity.

    color_identity: if given, only include commanders whose CI is a subset of these colors.
    """
    cube = load_enriched(id_or_slug)
    results = []
    for card in cube.cards:
        if card.board != "mainboard":
            continue
        eligibility = is_commander_eligible(card)
        if not eligibility["eligible"]:
            continue
        oracle = card.oracle_text or ""
        ci = card.color_identity or []

        if color_identity is not None:
            if not set(ci).issubset(set(color_identity)):
                continue

        partner_with = _partner_with_target(oracle)
        results.append({
            "name": card.name,
            "color_identity": ci,
            "cmc": card.cmc,
            "type_line": card.type_line,
            "oracle_text": oracle,
            "is_partner": _is_partner(oracle),
            "partner_with": partner_with,
            "has_background": _has_background(oracle),
            "is_friends_forever": _is_friends_forever(oracle),
            "is_doctors_companion": _is_doctors_companion(oracle),
        })

    results.sort(key=lambda c: c["name"])
    return results


def format_commanders_table(candidates: List[Dict[str, Any]]) -> str:
    """Return an ASCII table of commander candidates with partner flags."""
    if not candidates:
        return "No eligible commanders found in this cube."

    rows = []
    for c in candidates:
        ci_str = "".join(c["color_identity"]) or "C"
        flags = []
        if c["is_partner"]:
            flags.append("Partner")
        if c["partner_with"]:
            flags.append(f"Partner with {c['partner_with']}")
        if c["has_background"]:
            flags.append("Choose a Background")
        if c["is_friends_forever"]:
            flags.append("Friends Forever")
        if c["is_doctors_companion"]:
            flags.append("Doctor's Companion")
        flags_str = "; ".join(flags)
        type_short = (
            c["type_line"]
            .replace("Legendary ", "")
            .replace("Creature — ", "")
            .strip()
        )[:28]
        rows.append((c["name"], ci_str, str(int(c["cmc"])), type_short, flags_str))

    name_w = min(max(len(r[0]) for r in rows), 34)
    name_w = max(name_w, 4)

    header = (
        f"{'Name':<{name_w}}  {'CI':<6}  {'CMC':<3}  {'Type':<28}  Partner Flags"
    )
    sep = "-" * (name_w + 6 + 3 + 28 + 20)
    lines = [header, sep]
    for name, ci, cmc, type_s, flags in rows:
        lines.append(
            f"{name[:name_w]:<{name_w}}  {ci:<6}  {cmc:<3}  {type_s:<28}  {flags}"
        )
    return "\n".join(lines)

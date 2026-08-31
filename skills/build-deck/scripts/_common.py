"""Shared helpers for the build-deck phase scripts.

Every script in this directory is driven by `_workspace/<run-token>/run_config.json`,
written once at Phase 0. Nothing here may hardcode a cube, a deck size, a pool rule or
a card name — those are exactly the assumptions that made the previous generation of
throwaway per-run scripts unusable on a second cube or a non-40-card format.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

# Deck size and default sideboard per format. `deck_size` COUNTS the commander for
# commander formats (SKILL.md "Supported Formats": commander-60 is 61 = 60 + 1).
FORMATS: Dict[str, Dict[str, Any]] = {
    "40-card":       {"deck_size": 40,  "sideboard": 8,  "commanders": 0},
    "60-card":       {"deck_size": 60,  "sideboard": 15, "commanders": 0},
    "commander-60":  {"deck_size": 61,  "sideboard": 0,  "commanders": 1},
    "commander-100": {"deck_size": 101, "sideboard": 0,  "commanders": 1},
}

BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest"}
BASIC_COLOR = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}


def utf8() -> None:
    """cp1252 consoles mangle card names and box-drawing output. Always call this first."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_dir(run_token: str) -> str:
    return os.path.join("_workspace", run_token)


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj: Any, path: str, compact: bool = False) -> int:
    """Write JSON. `compact` drops all insignificant whitespace.

    Pretty-printing the Phase 8 bundle costs ~24% of its bytes in indentation, and
    nothing downstream parses these files by line — the grill agents json.load them.
    Artifacts a human reads stay indented; agent payloads are written compact.
    """
    kw: Dict[str, Any] = {"ensure_ascii": False, "default": str}
    if compact:
        kw["separators"] = (",", ":")
    else:
        kw["indent"] = 1
    # Create the per-deck subdirectory on demand. Every script writes into
    # <run>/<deck-dir>/, and requiring the orchestrator to mkdir it first makes the
    # first scripted phase of a fresh run fail on an instruction it can skip.
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, **kw)
    return os.path.getsize(path)


def load_config(run_token: str) -> Dict[str, Any]:
    """Load run_config.json and fill format-derived defaults."""
    cfg = load_json(os.path.join(run_dir(run_token), "run_config.json"))
    fmt = cfg.get("format")
    if fmt not in FORMATS:
        raise SystemExit(
            f"run_config.format must be one of {sorted(FORMATS)}, got {fmt!r}"
        )
    spec = FORMATS[fmt]
    cfg.setdefault("deck_size", spec["deck_size"])
    cfg.setdefault("sideboard_size", spec["sideboard"])
    cfg.setdefault("commander", [] if spec["commanders"] else None)
    cfg.setdefault("card_pool_rules", {})
    return cfg


def is_commander_format(cfg: Dict[str, Any]) -> bool:
    return FORMATS[cfg["format"]]["commanders"] > 0


def pool_path(run_token: str) -> str:
    return os.path.join(run_dir(run_token), "working_pool.json")


def load_pool(run_token: str) -> Dict[str, Dict[str, Any]]:
    """The working pool cache, keyed by exact card name."""
    return {c["name"]: c for c in load_json(pool_path(run_token))}


def deck_path(run_token: str, deck_dir: str) -> str:
    return os.path.join(run_dir(run_token), deck_dir, "deck.json")


def load_deck(run_token: str, deck_dir: str) -> Dict[str, Any]:
    return load_json(deck_path(run_token, deck_dir))


def is_land(card: Dict[str, Any]) -> bool:
    return "land" in (card.get("type_line") or "").lower()


def expand(entries: List[Dict[str, Any]], pool: Dict[str, Dict[str, Any]]
           ) -> List[Dict[str, Any]]:
    """qty-expand deck entries into one pool card dict per copy.

    Uses the POOL row, not the deck row, so `tags` is present — deck_audit derives
    ramp_count/cantrip_count from card["tags"] and silently reports 0 without it.
    """
    out: List[Dict[str, Any]] = []
    for e in entries:
        card = pool.get(e["name"])
        if card is None:
            raise SystemExit(f"card not in working pool: {e['name']!r}")
        out.extend([card] * int(e.get("qty", 1)))
    return out


def commander_cards(cfg: Dict[str, Any], pool: Dict[str, Dict[str, Any]]
                    ) -> Optional[List[Dict[str, Any]]]:
    """Commander card dicts, or None for non-commander formats.

    mana_audit branches on format and reads commander_cards[0].cmc for the Burgess
    term, so passing None on a commander format silently defaults the commander to
    mana value 4.
    """
    names = cfg.get("commander") or []
    if not names:
        return None
    return [pool[n] for n in names]


def color_str(card: Dict[str, Any]) -> str:
    """CubeCobra single-letter colour notation from the card's own cost.

    enriched.json leaves `colors` empty on transform/modal DFCs, so fall back to the
    front-face mana cost that Phase 0 backfilled.
    """
    if card["name"] in BASIC_COLOR:
        return BASIC_COLOR[card["name"]]
    cols = set(card.get("colors") or [])
    if not cols:
        cols = set(re.findall(r"\{([WUBRG])\}", card.get("mana_cost") or ""))
    return "".join(c for c in "WUBRG" if c in cols) or "C"


def land_note(card: Dict[str, Any]) -> str:
    """Describe a nonbasic land from its ORACLE TEXT, never a card-name lookup.

    A hardcoded name->note table is cube-locked; this works on any cube.
    """
    if card["name"] in BASICS:
        return ""
    txt = (card.get("oracle_text") or "")
    low = txt.lower()
    bits: List[str] = []
    produces = sorted({c for c in re.findall(r"add \{([WUBRG])\}", low.replace("add {", "add {"))}
                      | set(re.findall(r"\{([WUBRG])\}", txt.split("Add")[-1] if "Add" in txt else "")))
    subtypes = (card.get("type_line") or "").split("—")[-1].strip() if "—" in (card.get("type_line") or "") else ""
    if subtypes:
        bits.append(subtypes)
    if "add one mana of any color" in low:
        bits.append("any colour")
    elif produces:
        bits.append("taps for " + "".join(produces))
    if "search your library for a basic land" in low:
        bits.append("fetches a basic")
    if "enters tapped unless" in low or "unless you control" in low:
        bits.append("conditionally tapped")
    elif "enters tapped" in low:
        bits.append("enters tapped")
    return ", ".join(bits)


def base_parser(description: str, need_deck: bool = True) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--run", required=True, help="run token, e.g. run-2026...")
    if need_deck:
        p.add_argument("--deck", required=True, help="per-deck subdirectory, e.g. deck1")
    return p

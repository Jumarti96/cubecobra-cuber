"""AI tagger — assigns functional tags to cards based on oracle text."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from . import llm
from .cube import Card, Cube

FUNCTIONAL_TAGS = [
    # Card selection & economy
    "card-draw", "card-advantage", "looting", "tutor", "discard",
    # Interaction
    "removal", "creature-removal", "artifact-removal", "enchantment-removal",
    "board-wipe", "counterspell", "bounce", "protection",
    # Mana
    "ramp", "land-fetch", "mana-rock", "mana-dork",
    # Threats & payoffs
    "evasion", "haste-enabler", "lord", "lifegain", "mill",
    # Enablers
    "graveyard", "sacrifice", "token", "engine", "land",
]

ARCHETYPE_TAGS = [
    # Core strategies
    "aggro",        # fast damage, low curve — haste creatures, burn, early attackers
    "control",      # board wipes, hard counters, mass removal, late-game answers
    "combo",        # assembles a specific synergy to win
    "storm",        # storm count or cast-many-spells payoffs
    "tempo",        # cheap threats + bounce/counter disruption

    # Graveyard strategies
    "reanimator",   # puts fatties in graveyard; resurrects them
    "flashback",    # casting spells from graveyard (flashback, escape, aftermath)
    "delirium",     # four or more card types in graveyard matter

    # Synergy / engine archetypes
    "blink",        # ETB triggers; flicker/blink effects
    "aristocrats",  # sacrifice outlets + death triggers + payoffs
    "stax",         # taxing effects, symmetrical hate, resource denial
    "spells-matter", # prowess, magecraft, or triggers on noncreature spells
    "lands-matter", # landfall, land count payoffs
    "artifacts-matter", # metalcraft, affinity, artifact count payoffs
    "enchantress",  # enchantments matter; draw on enchantment cast/ETB
    "counters",     # +1/+1 counters, proliferate, modular
    "wheels",       # wheel effects (draw 7, discard hand)
    "voltron",      # equip/aura a single creature to win via combat
    "domain",       # basic land types among lands you control matter
    "historic",     # artifacts, legendaries, and sagas matter together
    "sagas",        # Saga enchantments or chapter-trigger payoffs
    "morph",        # face-down creatures; morph / megamorph / manifest
    "kicker",       # kicker or multikicker; scales with mana investment

    # Tribal (generic + most common cube subtypes)
    "tribal",       # creature-type synergy not covered by a subtype below
    "dragons",      # dragon tribal
    "vampires",     # vampire tribal
    "zombies",      # zombie tribal
    "spirits",      # spirit tribal
    "werewolves",   # werewolf / transform tribal
    "humans",       # human tribal
    "elves",        # elf tribal
    "goblins",      # goblin tribal
    "faeries",      # faerie tribal
    "angels",       # angel tribal
    "elementals",   # elemental tribal
    "merfolk",      # merfolk tribal
]

CANONICAL_TAGS = FUNCTIONAL_TAGS + ARCHETYPE_TAGS

_archetype_groups = """  Core: aggro, control, combo, storm, tempo
  Graveyard: reanimator, flashback, delirium
  Synergy/engine: blink, aristocrats, stax, spells-matter, lands-matter,
    artifacts-matter, enchantress, counters, wheels, voltron,
    domain, historic, sagas, morph, kicker
  Tribal (use specific type when applicable, "tribal" otherwise):
    tribal, dragons, vampires, zombies, spirits, werewolves,
    humans, elves, goblins, faeries, angels, elementals, merfolk"""

SYSTEM_PROMPT = f"""You are a Magic: The Gathering card tagger.

IRON RULE: Never assume what a card does from prior knowledge.
All tagging decisions MUST be grounded in the oracle text provided in the input.

Assign tags from two categories:

FUNCTIONAL TAGS — what the card does mechanically:
{', '.join(FUNCTIONAL_TAGS)}

ARCHETYPE TAGS — which draft archetypes this card enables or fits into:
{_archetype_groups}

Guidelines:
- A card may carry tags from both categories (e.g. Gravecrawler: ["aggro", "aristocrats", "graveyard"])
- Assign archetype tags liberally — a card can fit multiple archetypes
- Only assign an archetype tag when oracle text clearly supports that strategy, not just because the card is generically good
- For tribal tags: use the specific subtype tag (e.g. "zombies") when the card references that type explicitly; use "tribal" for generic typal support
- flashback covers any mechanic that casts from the graveyard (escape, aftermath, retrace, jump-start)
- delirium: assign when oracle text says "four or more card types" or "delirium"
- domain: assign when oracle text rewards having multiple basic land types
- historic: assign when oracle text says "historic" (artifacts + legendaries + sagas)
- You may add a tag not in the list if strongly warranted by oracle text

aggro — STRICT: only assign when oracle text shows at least one of:
  • A creature with haste at CMC ≤ 3 (attacks the turn it enters)
  • A creature at CMC ≤ 2 with first strike, double strike, or menace
  • A spell that deals direct damage to players or "any target" (burn)
  • A combat trick granting +power AND evasion or haste at CMC ≤ 2
  • An effect that grants haste to multiple creatures you control

control — STRICT: only assign when oracle text shows at least one of:
  • A board wipe (destroys or exiles multiple permanents simultaneously)
  • An unconditional counterspell (no "unless they pay {{X}}" clause)
  • Draws 3 or more cards as the primary effect
  • Mass removal or resource denial affecting all opponents
  • Gains control of one or more permanents

Respond ONLY with a JSON object mapping card names to arrays of tags.
Example:
{{
  "Lightning Bolt": ["removal", "creature-removal", "aggro", "tempo"],
  "Llanowar Elves": ["ramp", "mana-dork", "elves"],
  "Gravecrawler": ["aggro", "aristocrats", "graveyard", "zombies"]
}}

If a card's oracle text is empty or does not clearly map to any tag, return an empty array for that card.
Do NOT add any explanation outside the JSON object.
"""


def build_tagging_prompt(cards_batch: List[Card]) -> List[Dict[str, str]]:
    """Build system + user messages for a batch of cards."""
    card_lines = []
    for card in cards_batch:
        # For DFCs, include all face oracle texts
        if card.card_faces:
            oracle = " // ".join(
                f"[{f.name}] {f.oracle_text}" for f in card.card_faces
            )
        else:
            oracle = card.oracle_text or "(no oracle text)"
        card_lines.append(
            f"Card: {card.name}\n"
            f"Type: {card.type_line}\n"
            f"Oracle: {oracle}\n"
        )
    user_content = "Tag the following cards:\n\n" + "\n---\n".join(card_lines)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _parse_response(response: str, batch: List[Card]) -> Dict[str, List[str]]:
    """Parse LLM JSON response into {name: [tags]} dict."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", response).strip().rstrip("`").strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {k: [t.lower().strip() for t in v] for k, v in data.items() if isinstance(v, list)}
    except json.JSONDecodeError:
        pass
    # Fallback: log warning, return empty for all cards in batch
    print(f"  WARNING: Could not parse LLM response as JSON. Skipping batch of {len(batch)} cards.")
    return {}


def tag_cards(cube: Cube, overwrite: bool = False) -> Cube:
    """Tag all cards in cube via LLM. Merges with existing tags unless overwrite=True."""
    mainboard = [c for c in cube.cards if c.board == "mainboard"]
    batches = [mainboard[i : i + 50] for i in range(0, len(mainboard), 50)]

    # Cost preview
    sample_messages = build_tagging_prompt(batches[0] if batches else [])
    est_tokens_per_batch = llm.estimate_tokens(sample_messages)
    total_est = est_tokens_per_batch * len(batches)
    print(f"\nTagging {len(mainboard)} cards in {len(batches)} batch(es).")
    print(f"Estimated input tokens: ~{total_est:,}")
    print("(Output tokens vary. Check your provider's pricing.)")
    confirm = input("Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted — no changes made.")
        return cube

    all_tags: Dict[str, List[str]] = {}
    for i, batch in enumerate(batches, 1):
        print(f"  Batch {i}/{len(batches)} ({len(batch)} cards)...")
        messages = build_tagging_prompt(batch)
        try:
            response = llm.chat(messages, temperature=0.1)
            batch_tags = _parse_response(response, batch)
            all_tags.update(batch_tags)
        except llm.LLMError as e:
            print(f"  WARNING: LLM error on batch {i}: {e}")

    # Apply tags to cards
    tag_index = {c.name: c for c in cube.cards}
    for name, new_tags in all_tags.items():
        card = tag_index.get(name)
        if card is None:
            continue
        if overwrite:
            card.tags = new_tags
        else:
            existing = set(card.tags)
            card.tags = card.tags + [t for t in new_tags if t not in existing]

    print(f"  Tagged {len(all_tags)} cards.")
    return cube

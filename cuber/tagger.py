"""AI tagger — assigns taxonomic_profile to cards based on oracle text."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from . import llm
from .cube import Card, Cube

# ── Taxonomy Vocabulary ───────────────────────────────────────────────────────

MACRO_ARCHETYPES = ["Aggro", "Tempo", "Midrange", "Control", "Combo"]

SYNERGY_CLUSTERS = [
    "Aristocrats/Sacrifice",
    "Artifacts",
    "Spellslinger",
    "Storm",
    "Graveyard",
    "Reanimator",
    "Self-Mill",
    "Flashback/GY-Cast",
    "Delirium",
    "Counters (+1/+1)",
    "Tribal/Kindred",
    "Tokens",
    "Landfall",
    "Lands-Matter",
    "Domain",
    "Lifegain",
    "Blink/ETB",
    "Enchantress",
    "Voltron/Equipment",
    "Wheels",
    "Stax/Taxing",
    "Historic",
    "Sagas",
    "Kicker/Scaling",
    "Morph/Manifest",
    "Infect/Poison",
]

STRUCTURAL_ROLES = [
    "Enabler/Fodder",
    "Engine/Outlet",
    "Payload/Payoff",
    "Interaction/Disruption",
    "Infrastructure/Consistency",
    "Standalone Threat",
]

MECHANICAL_FUNCTIONS_BASE = [
    "Card Draw", "Card Selection", "Looting", "Tutor",
    "Targeted Removal", "Sweeper/Board Wipe", "Counterspell", "Bounce",
    "Mana Ramp", "Mana Rock", "Mana Dork", "Land Fetch",
    "Token Generation", "Life Drain", "Self-Mill", "Sacrifice Outlet",
    "Direct Damage", "Combat Trick", "Protection", "Tax Effect",
    "Alternate Win Condition",
]

# ── Prompt helpers ────────────────────────────────────────────────────────────

_macro_archetype_list = ", ".join(MACRO_ARCHETYPES)
_synergy_cluster_list = "\n".join(f"  {c}" for c in SYNERGY_CLUSTERS)
_structural_role_list = "\n".join(f"  {r}" for r in STRUCTURAL_ROLES)
_mech_functions_list = ", ".join(MECHANICAL_FUNCTIONS_BASE)

SYSTEM_PROMPT = f"""You are a rigorous, deterministic MTG data-extraction engine operating within a card analysis pipeline.

IRON RULE: Never assume what a card does from prior knowledge.
All tagging decisions MUST be grounded in the oracle text provided in the input.
If oracle text is absent or unclear, output empty arrays for that card.

OUTPUT FORMAT:
Respond ONLY with a valid JSON array. Each element covers one card:
[
  {{
    "card_name": "<exact card name>",
    "taxonomic_profile": {{
      "macro_archetypes": [...],
      "synergy_clusters": [...],
      "structural_roles": [...],
      "mechanical_functions": [...]
    }}
  }},
  ...
]
Do not include markdown fences, introductory text, or explanations outside the JSON array.

════════════════════════════════════════════════════════════
PILLAR 1 — macro_archetypes
════════════════════════════════════════════════════════════
Select from: {_macro_archetype_list}
Multiple values permitted. Empty array [] if no speed clearly applies.

### Aggro (Resource-to-Damage Conversion)
Cards that prioritize raw damage output and mathematical clocks over long-term value.
- Cost-to-Power Ratio: Creature where MV ≤ 2 and printed Power ≥ MV.
- Syntactical Keywords: Haste, Menace, Trample, or First Strike in oracle text.
- Direct Conversion: Spell with MV ≤ 3 that explicitly states "deals damage to target player or planeswalker."
- Drawback Filter: Cards paying alternative costs (life, discard, sacrifice) for immediate board presence or damage.
- Exclusion: CMC ≥ 6 cards are never Aggro. CMC ≥ 4 cards are only Aggro if they have Haste or deal mass damage.

### Tempo (Stack Manipulation & Asymmetric Disruption)
Cheap threats protected by interaction that bottlenecks the opponent's mana curve.
- Disruptive Efficiency: Instant with MV ≤ 2 that delays rather than permanently destroys. Syntax: "Return target nonland permanent," "Tap target creature," or "Counter target spell unless its controller pays."
- Evasive Payloads: Creature MV ≤ 3 with Flying or Unblockable, especially when paired with Flash or ETB disruption.
- Tax Engines: Permanents that say "Spells your opponents cast cost {{1}} more" or equivalent.
- Exclusion: CMC ≥ 5 cards are never Tempo.

### Midrange (The Autonomous Value Engine)
Stat-efficient cards and 2-for-1 engines that function without external synergy.
- The 2-for-1 Audit: Permanent where ETB or death trigger generates a secondary resource. Syntax: "Create a token," "Draw a card," "Destroy target creature or planeswalker," "Return target card from your graveyard."
- Flexible Interaction: Modal spells or removal handling multiple card types without conditions, MV 3–4.
- Scalable Threats: Cards with mana sinks. A 2-MV card with an activated ability costing 4+ mana is structurally Midrange.
- Exclusion: CMC ≤ 2 creatures without explicit value text or a value-generating tag are not Midrange.

### Control (Inevitability and Mass Equalization)
Cards that refuse early combat, prioritizing card advantage and complete neutralization.
- Mass Equalization (Sweepers): Spell MV ≥ 4 with syntax "Destroy all creatures," "Exile all," or "All creatures get -X/-X."
- Unconditional Removal: Instant saying "Counter target spell" without "unless." Single-target removal that permanently exiles without restrictions.
- Resource Accumulation: Spell that increases hand size by 2+ (e.g., "Draw two cards," "Look at the top four").
- The Finisher: Permanent MV ≥ 6 with inherent self-protection (Hexproof, Ward) or game-ending abilities if unanswered for two turns.
- Exclusion: CMC ≤ 2 creatures are never Control.

### Combo (The Synergistic Lock-In)
Cards that bypass fundamental resource systems through mechanical anomalies.
- Resource Cheating: Syntax "without paying its mana cost," "Add mana equal to," or effects enabling infinite loops (e.g., "Untap target permanent").
- Extraction Algorithms: Syntax "Search your library for a card" — tutors are Combo glue.
- Zone Manipulation: Engines rapidly moving cards between zones. Syntax: "Return all," rapid self-mill, or "Whenever you cast an instant or sorcery."
- Alternate Win Conditions: Any card containing "You win the game" or "Target opponent loses the game" based on a non-damage threshold.

════════════════════════════════════════════════════════════
PILLAR 2 — synergy_clusters
════════════════════════════════════════════════════════════
Select strictly relevant canonical values from:
{_synergy_cluster_list}

Assign only when oracle text clearly connects the card to that ecosystem.
Use [] if the card belongs to no specific synergy.
Free-form values are allowed ONLY when no canonical cluster applies.

Cluster definitions (key ones):
- Aristocrats/Sacrifice: sacrifice outlets, death triggers, drain payoffs
- Spellslinger: prowess, magecraft, or explicitly triggered by noncreature spells
- Storm: explicitly cares about spell count or creates copies based on storm count
- Reanimator: specifically puts large creatures into play from the graveyard
- Self-Mill: mills its controller as a resource or win enabler
- Flashback/GY-Cast: can be cast from graveyard (escape, aftermath, retrace, jump-start)
- Delirium: oracle text says "four or more card types" or "delirium"
- Blink/ETB: ETB triggers + flicker/blink effects that re-trigger them
- Enchantress: draws cards on enchantment cast or ETB; enchantments-matter payoffs
- Voltron/Equipment: equips or attaches auras to a single creature as primary win strategy
- Wheels: symmetrical draw-7 effects; hand disruption via wheel
- Stax/Taxing: oracle text imposes costs on opponents ("costs {{1}} more," "can't untap unless")
- Domain: oracle text rewards having multiple basic land types
- Kicker/Scaling: kicker, multikicker, overload, escalate mechanics
- Infect/Poison: deals damage as -1/-1 counters or poison counters

════════════════════════════════════════════════════════════
PILLAR 3 — structural_roles
════════════════════════════════════════════════════════════
Select one or more from:
{_structural_role_list}

At least one role MUST be assigned to every tagged card. Multiple roles permitted.

Role definitions:
- Enabler/Fodder: provides resources (tokens, creatures, mana) for an engine to consume
- Engine/Outlet: the repeatable mechanism that converts enablers into value (e.g., sacrifice outlet, loot outlet, tap outlet)
- Payload/Payoff: wins the game or generates dominant, game-altering value when the engine runs
- Interaction/Disruption: removes, counters, bounces, or delays opponent's threats or plans
- Infrastructure/Consistency: draws cards, tutors, fixes mana, cantrips — keeps the deck functioning
- Standalone Threat: wins or dominates the board by itself with no synergy or setup required

════════════════════════════════════════════════════════════
PILLAR 4 — mechanical_functions
════════════════════════════════════════════════════════════
List the specific mechanical actions this card performs.
Use canonical strings when applicable:
{_mech_functions_list}

Free-form additions are allowed for actions outside this list (e.g., "Damage Prevention Override").

════════════════════════════════════════════════════════════
FEW-SHOT CALIBRATION EXAMPLES
════════════════════════════════════════════════════════════

Input:
Card: Viscera Seer
Type: Creature — Vampire Wizard
Oracle: Sacrifice a creature: Scry 1.

Card: Bonecrusher Giant // Stomp
Type: Creature — Giant // Instant — Adventure
Oracle: [Stomp] Damage can't be prevented this turn. Stomp deals 2 damage to any target. // [Bonecrusher Giant] Whenever Bonecrusher Giant becomes the target of a spell, it deals 2 damage to that spell's controller.

Output:
[
  {{
    "card_name": "Viscera Seer",
    "taxonomic_profile": {{
      "macro_archetypes": ["Combo", "Midrange"],
      "synergy_clusters": ["Aristocrats/Sacrifice", "Graveyard", "Tribal/Kindred"],
      "structural_roles": ["Engine/Outlet"],
      "mechanical_functions": ["Sacrifice Outlet", "Card Selection"]
    }}
  }},
  {{
    "card_name": "Bonecrusher Giant // Stomp",
    "taxonomic_profile": {{
      "macro_archetypes": ["Aggro", "Tempo", "Midrange"],
      "synergy_clusters": ["Spellslinger"],
      "structural_roles": ["Interaction/Disruption", "Standalone Threat"],
      "mechanical_functions": ["Targeted Removal", "Direct Damage", "Damage Prevention Override"]
    }}
  }}
]
"""


def build_tagging_prompt(cards_batch: List[Card]) -> List[Dict[str, str]]:
    """Build system + user messages for a batch of cards."""
    card_lines = []
    for card in cards_batch:
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


def _parse_response(response: str, batch: List[Card]) -> Dict[str, Dict]:
    """Parse LLM JSON array response into {name: taxonomic_profile} dict."""
    text = re.sub(r"```(?:json)?\s*", "", response).strip().rstrip("`").strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            result = {}
            for item in data:
                if isinstance(item, dict) and "card_name" in item and "taxonomic_profile" in item:
                    profile = item["taxonomic_profile"]
                    if isinstance(profile, dict):
                        result[item["card_name"]] = profile
            return result
    except json.JSONDecodeError:
        pass
    print(f"  WARNING: Could not parse LLM response as JSON. Skipping batch of {len(batch)} cards.")
    return {}


def tag_cards(cube: Cube, overwrite: bool = False) -> Cube:
    """Tag all mainboard cards in cube via LLM, writing taxonomic_profile to each card."""
    mainboard = [c for c in cube.cards if (c.board or "mainboard") == "mainboard"]
    batches = [mainboard[i : i + 50] for i in range(0, len(mainboard), 50)]

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

    all_profiles: Dict[str, Dict] = {}
    for i, batch in enumerate(batches, 1):
        print(f"  Batch {i}/{len(batches)} ({len(batch)} cards)...")
        messages = build_tagging_prompt(batch)
        try:
            response = llm.chat(messages, temperature=0.1)
            batch_profiles = _parse_response(response, batch)
            all_profiles.update(batch_profiles)
        except llm.LLMError as e:
            print(f"  WARNING: LLM error on batch {i}: {e}")

    tag_index = {c.name: c for c in cube.cards}
    tagged = 0
    for name, profile in all_profiles.items():
        card = tag_index.get(name)
        if card is None:
            continue
        if overwrite or card.taxonomic_profile is None:
            card.taxonomic_profile = profile
            tagged += 1

    print(f"  Tagged {tagged} cards.")
    return cube

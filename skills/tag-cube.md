---
name: tag-cube
description: Tag every card in a locally cached cube by functional role
---
# /tag-cube — AI Taxonomic Tagger

Tag every card in a locally cached cube using the five-pillar `taxonomic_profile` taxonomy. Oracle text is the only source of truth. Writes `tagged.csv` ready to upload to CubeCobra, and updates `enriched.json` with full `taxonomic_profile` data.

---

## IRON RULE

**Never assume what a card does from prior knowledge.**
Every tagging decision MUST be justified by the card's oracle text as it appears in `enriched.json`.
If oracle text is absent or unclear, assign empty arrays for all pillars.

---

## Prerequisites

The cube must already be fetched and enriched:
```
cuber fetch <id>
cuber enrich <id>
```

**Finding the cube folder:** Run `cuber list` to see the slug for your cube. Use `cubes/<slug>/` for all file path operations.

---

## Workflow

### Step 1 — Locate enriched.json

Run `cuber list` to find `<slug>`, then read `cubes/<slug>/enriched.json`. If it does not exist, stop and instruct the user:
> "enriched.json not found. Run: cuber enrich <id>"

---

### Step 2 — Assign `taxonomic_profile` from oracle text

For each card in `cards[]` where `board == "mainboard"`:

1. Read `oracle_text` from enriched.json (never from training data).
2. For DFCs, read all faces: `card_faces[*].oracle_text`.
3. Assign all five pillars. Each pillar is an array of strings.

---

#### Pillar 1 — `macro_archetypes`

Select from: `Aggro`, `Tempo`, `Midrange`, `Control`, `Combo`

Multiple values permitted. Empty array `[]` if no speed clearly applies.

| Value | When to assign |
|-------|---------------|
| Aggro | MV ≤ 2 creature with power ≥ MV; oracle text has Haste/Menace/Trample; MV ≤ 3 spell that deals direct damage to player/planeswalker |
| Tempo | MV ≤ 2 instant that bounces, taps, or counters conditionally; MV ≤ 3 evasive creature with flash or ETB disruption; taxing permanents |
| Midrange | ETB or death trigger creating a secondary resource; modal removal MV 3–4; card with mana sink ability |
| Control | Sweeper (MV ≥ 4, destroys/exiles all creatures); unconditional counter; draws 2+ cards; MV ≥ 6 threat with inherent protection |
| Combo | Casts without paying mana cost; tutors ("Search your library"); enables infinite loops; wins the game via alternate condition |

---

#### Pillar 2 — `synergy_clusters`

Select from the canonical list below. Use `[]` if no synergy applies. Free-form values allowed only when no canonical cluster fits.

```
Aristocrats/Sacrifice   — sacrifice outlets, death triggers, drain payoffs
Artifacts               — metalcraft, affinity, artifact count payoffs
Spellslinger            — prowess, magecraft, triggered by noncreature spells
Storm                   — cares about spell count; creates copies (storm mechanic)
Graveyard               — general GY recursion, threshold, GY matters
Reanimator              — cheats large creatures from GY into play
Self-Mill               — mills its controller as resource or win enabler
Flashback/GY-Cast       — cast from GY (escape, aftermath, retrace, jump-start)
Delirium                — oracle text says "four or more card types" or "delirium"
Counters (+1/+1)        — +1/+1 counters, proliferate, modular, graft, undying
Tribal/Kindred          — creature-type synergy (reference creature type in oracle text or type line)
Tokens                  — creates, buffs, or sacrifices token permanents
Landfall                — triggered by lands entering the battlefield
Lands-Matter            — rewards high land count or specific land types generally
Domain                  — oracle text rewards having multiple basic land types
Lifegain                — gaining life as a resource or trigger
Blink/ETB               — ETB triggers; flicker/blink/bounce-own effects that re-trigger ETBs
Enchantress             — draws cards on enchantment cast or ETB; enchantments-matter
Voltron/Equipment       — equips or attaches auras to a single creature as win strategy
Wheels                  — symmetrical draw-7 effects; hand disruption via wheel
Stax/Taxing             — imposes costs on opponents ("costs {1} more," "can't untap unless")
Historic                — artifacts + legendaries + sagas together (oracle text says "historic")
Sagas                   — Saga chapter triggers or Saga count payoffs
Kicker/Scaling          — kicker, multikicker, overload, escalate mechanics
Morph/Manifest          — face-down creatures; morph, megamorph, manifest
Infect/Poison           — deals damage as -1/-1 counters or gives poison counters
```

**Keyword-Ability Matters (generalizing Tribal/Kindred to keyword abilities).** Tribal/Kindred
covers creature-TYPE synergy. The same logic applies to creature-ABILITY synergy, which has no
canonical cluster of its own. When a payoff explicitly counts or rewards a keyword ability shared
by other creatures (e.g. "for each creature with defender you control"), or a creature's identity
centers on an uncommon, build-around keyword (a vanilla Wall whose only text is "Defender" — not a
universally-common keyword like Vigilance or Trample), assign a free-form synergy_cluster named
`"<Keyword> Matters"` (e.g. `"Defender Matters"`) to both the payoff and every bearer card. This is
the identical rule and worked example (`Wingmantle Chaplain` + `Academy Wall`) used by the `cuber
tag` LLM prompt in `cuber/tagger.py` — keep the two in sync if either changes.

---

#### Pillar 3 — `structural_roles`

Select one or more. At least one role MUST be assigned to every tagged card.

| Role | Definition |
|------|-----------|
| Enabler/Fodder | Provides resources (tokens, creatures, mana) for an engine to consume |
| Engine/Outlet | The repeatable mechanism that converts enablers into value (sacrifice outlet, loot outlet, tap outlet) |
| Payload/Payoff | Wins the game or generates dominant value when the engine runs |
| Interaction/Disruption | Removes, counters, bounces, or delays opponent's threats or plans |
| Infrastructure/Consistency | Draws cards, tutors, fixes mana, cantrips — keeps the deck functioning |
| Standalone Threat | Wins or dominates the board by itself with no synergy or setup required |

---

#### Pillar 4 — `mechanical_functions`

List the specific mechanical actions this card performs. Use canonical strings when applicable:

`Card Draw`, `Card Selection`, `Looting`, `Tutor`, `Targeted Removal`, `Sweeper/Board Wipe`, `Counterspell`, `Bounce`, `Mana Ramp`, `Mana Rock`, `Mana Dork`, `Land Fetch`, `Token Generation`, `Life Drain`, `Self-Mill`, `Sacrifice Outlet`, `Direct Damage`, `Combat Trick`, `Protection`, `Tax Effect`, `Alternate Win Condition`

Free-form additions allowed for actions outside this list.

---

#### Pillar 5 — `resource_exchange`

The net resource ledger of playing the card, judged over its **full use from a single
card slot** (a flashback recast counts toward the same slot's total). Empty array `[]`
for resource-neutral cards — most cards are neutral. Multiple values across axes permitted.

| Label | When to assign |
|-------|---------------|
| `Mana: Net-Positive` | Resolving yields more mana than was paid (Dark Ritual, Black Lotus) |
| `Mana: Self-Replacing` | Refunds ≈ its own cost on resolution (Peregrine Drake, Frantic Search) |
| `Mana: Ongoing-Cost` | Demands mana after resolution — upkeep, cumulative upkeep, echo (Mystic Remora) |
| `Cards: Net-Positive` | Counting itself as spent, full use yields more cards than consumed (Deep Analysis, Night's Whisper) |
| `Cards: Self-Replacing` | Exactly replaces itself — cantrip, ETB draw, cycling (Baleful Strix) |
| `Cards: Extra-Cost` | Consumes additional cards from hand beyond itself (Lightning Axe, Gamble) |
| `Board: Sacrifice-Cost` | Casting requires sacrificing a permanent (Bone Splinters, evoke) |
| `Life: Cost` | Demands a life payment beyond mana (Thoughtseize, Phyrexian mana) |

**Boundary rules:** optional repeatable activated abilities are NOT resource_exchange
costs (a sac outlet's activation cost is Engine/Outlet territory); looting
(draw-then-discard) is selection, neutral on the Cards axis; symmetric effects imposed
on all players are effects, not costs. Free-form additions allowed for material
exchange properties outside the list — e.g. `Risk: Random-Discard` on Gamble, whose
random discard can hit a key card. This pillar's labels and boundary rules must stay
in sync with the `cuber tag` LLM prompt in `cuber/tagger.py` — keep the two aligned
if either changes.

---

### Step 3 — Show summary for review

Before writing any files, display:

| Pillar | Top values (by card count) |
|--------|--------------------------|
| macro_archetypes | Aggro: N, Midrange: N, ... |
| synergy_clusters | Top 5 clusters by count |
| structural_roles | All 6 roles by count |
| mechanical_functions | Top 5 functions by count |
| resource_exchange | All labels by count (+ count of neutral cards) |

List any "Needs Review" cards (missing or ambiguous oracle text).

If you are about to call an external LLM (token-cost path), ask once: **"Proceed with LLM tagging? Estimated ~N input tokens. [y/N]"**
If using deterministic rule-based tagging (free path), proceed directly to writing.

---

### Step 4 — Write all three artifacts

Write in this exact order:

1. **Update `enriched.json`** — write the full `taxonomic_profile` object to each card.
2. **Backfill `mainboard.csv`** — write the `tags` column for every card row. Use the same logic as `cuber tag`: union of `synergy_clusters` + `structural_roles` + `mechanical_functions` + `resource_exchange`, semicolon-separated, excluding `macro_archetypes`.
3. **Write `tagged.csv`** — audit log with `name,tags` columns.

Confirm: **"enriched.json, mainboard.csv, and tagged.csv updated in cubes/<slug>/"**

Then instruct the user to run:
```
cuber export <id>
```
This assembles `cubes/<slug>/exports/import-ready.csv` — the file to upload to CubeCobra.

---

## Tool Selection Table

| Task | How |
|------|-----|
| Resolve cube slug | `cuber list` |
| Read enriched.json | Read `cubes/<slug>/enriched.json` |
| Get oracle text | Read from enriched.json — never from training data |
| Write enriched.json | Use the Write tool → `cubes/<slug>/enriched.json` |
| Backfill mainboard.csv | Edit the `tags` column in `cubes/<slug>/mainboard.csv` |
| Write tagged.csv | Use the Write tool → `cubes/<slug>/tagged.csv` |
| Assemble export | `cuber export <id>` |

---

## CubeCobra Import Note

Run `cuber export <id>` after tagging to generate `cubes/<slug>/exports/import-ready.csv`.
To apply: **CubeCobra → your cube → List tab → Export → Replace with CSV Import → upload import-ready.csv**.

Note: `macro_archetypes` values (Aggro, Control, etc.) are intentionally excluded from the CubeCobra tags column — they are redundant with CMC, type line, and color for filtering purposes.

---
name: tag-cube
description: Tag every card in a locally cached cube by functional role
---
# /tag-cube — AI Taxonomic Tagger

Tag every card in a locally cached cube using the four-pillar `taxonomic_profile` taxonomy. Oracle text is the only source of truth. Writes `tagged.csv` ready to upload to CubeCobra, and updates `enriched.json` with full `taxonomic_profile` data.

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
3. Assign all four pillars. Each pillar is an array of strings.

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

### Step 3 — Show summary for review

Before writing any files, display:

| Pillar | Top values (by card count) |
|--------|--------------------------|
| macro_archetypes | Aggro: N, Midrange: N, ... |
| synergy_clusters | Top 5 clusters by count |
| structural_roles | All 6 roles by count |
| mechanical_functions | Top 5 functions by count |

List any "Needs Review" cards (missing or ambiguous oracle text).

Ask: **"Write taxonomic_profile data and tagged.csv with these assignments? [y/N]"**

Do not write files if the user says no.

---

### Step 4 — Write enriched.json and tagged.csv

On confirmation:
1. Update each card's `taxonomic_profile` field in `enriched.json` using the Write tool.
2. Write `cubes/<slug>/tagged.csv` using the Write tool — do NOT use shell echo or heredoc.

The `tags` column in `tagged.csv` is derived from the `taxonomic_profile`: the union of `synergy_clusters`, `structural_roles`, and `mechanical_functions`, joined by semicolons. `macro_archetypes` is excluded from the CubeCobra export.

Confirm: **"enriched.json and tagged.csv written to cubes/<slug>/"**

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
| Write tagged.csv | Use the Write tool → `cubes/<slug>/tagged.csv` |
| Assemble export | `cuber export <id>` |

---

## CubeCobra Import Note

Run `cuber export <id>` after tagging to generate `cubes/<slug>/exports/import-ready.csv`.
To apply: **CubeCobra → your cube → List tab → Export → Replace with CSV Import → upload import-ready.csv**.

Note: `macro_archetypes` values (Aggro, Control, etc.) are intentionally excluded from the CubeCobra tags column — they are redundant with CMC, type line, and color for filtering purposes.

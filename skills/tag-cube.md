---
name: tag-cube
description: Tag every card in a locally cached cube by functional role
---
# /tag-cube — AI Functional Tagger

Tag every card in a locally cached cube by functional role, using oracle text as the only source of truth. Writes a `tagged.csv` ready to upload to CubeCobra.

---

## IRON RULE

**Never assume what a card does from prior knowledge.**
Every tag assignment MUST be justified by the card's oracle text as it appears in `enriched.json`.
If oracle text is absent or unclear, assign no tags and add the card to a "Needs Review" list.

---

## Prerequisites

The cube must already be fetched and enriched:
```
cuber fetch <id>
cuber enrich <id>
```
Both commands are idempotent — safe to re-run.

**Finding the cube folder:** In v2, the folder name is the title slug, not the short ID. Run `cuber list` to see the slug for your cube. Use `cubes/<slug>/` for all file path operations below.

---

## Workflow

### Step 1 — Locate enriched.json

Run `cuber list` to find `<slug>`, then read `cubes/<slug>/enriched.json`. If it does not exist, stop and instruct the user:
> "enriched.json not found. Run: cuber enrich <id>"

### Step 2 — Assign tags from oracle text

For each card in `cards[]` where `board == "mainboard"`:

1. Read `oracle_text` from enriched.json (never from training data).
2. For DFCs, read all faces: `card_faces[*].oracle_text`.
3. Assign zero or more tags from the canonical vocabulary:

   **Functional** (what the card does mechanically):
   `card-draw`, `card-advantage`, `looting`, `tutor`, `discard`,
   `removal`, `creature-removal`, `artifact-removal`, `enchantment-removal`,
   `board-wipe`, `counterspell`, `bounce`, `protection`,
   `ramp`, `land-fetch`, `mana-rock`, `mana-dork`,
   `evasion`, `haste-enabler`, `lord`, `lifegain`, `mill`,
   `graveyard`, `sacrifice`, `token`, `engine`, `land`

   **Archetype** (which draft strategies the card enables or fits):

   *Core:* `aggro`, `midrange`, `control`, `combo`, `storm`, `tempo`

   *Graveyard:* `reanimator`, `flashback`, `delirium`
   (`flashback` covers any graveyard-cast mechanic: escape, aftermath, retrace, jump-start)
   (`delirium` = oracle text says "four or more card types" or "delirium")

   *Synergy/engine:* `blink`, `aristocrats`, `stax`, `spells-matter`, `lands-matter`,
   `artifacts-matter`, `enchantress`, `counters`, `wheels`, `voltron`,
   `domain`, `historic`, `sagas`, `morph`, `kicker`
   (`domain` = rewards multiple basic land types; `historic` = artifacts + legendaries + sagas)

   *Tribal:* `tribal` (generic), `dragons`, `vampires`, `zombies`, `spirits`, `werewolves`,
   `humans`, `elves`, `goblins`, `faeries`, `angels`, `elementals`, `merfolk`
   (use the specific subtype when the card references that type explicitly)

4. A card may carry tags from both categories (e.g. Gravecrawler: `aggro`, `aristocrats`, `graveyard`, `zombies`).
5. Assign archetype tags liberally — a card can fit multiple archetypes.
6. Only assign archetype tags when oracle text clearly supports that strategy, not just because the card is generically good.
7. Additional tags outside this list are allowed when clearly supported by oracle text.
5. Cards whose oracle text does not map to any tag get `tags: []` — this is correct, not an error.

### Step 3 — Show summary for review

Before writing any files, display:

| Tag | Card Count |
|-----|-----------|
| removal | N |
| card-draw | N |
| ... | ... |

List any "Needs Review" cards (missing or ambiguous oracle text).

Ask: **"Write tagged.csv with these tags? [y/N]"**

Do not write files if the user says no.

### Step 4 — Write tagged.csv and export

On confirmation:
1. Merge new tags with any existing tags in `enriched.json` (deduplicate).
2. Update `enriched.json` with the merged tags using the Write tool.
3. Write `cubes/<slug>/tagged.csv` using the Write tool — do NOT use shell echo or heredoc (apostrophes in card names break shell quoting).

Confirm: **"tagged.csv written to cubes/<slug>/tagged.csv"**

Then instruct the user to run:
```
cuber export <id>
```
This assembles `cubes/<slug>/exports/import-ready.csv`, which merges the working mainboard with the new tags — this is the file to upload to CubeCobra.

---

## Tool Selection Table

| Task | How |
|------|-----|
| Resolve cube slug | `cuber list` |
| Read enriched.json | Read `cubes/<slug>/enriched.json` |
| Get oracle text | Read from enriched.json — never from training data |
| Write tagged.csv | Use the Write tool → `cubes/<slug>/tagged.csv` |
| Update enriched.json | Use the Write tool → `cubes/<slug>/enriched.json` |
| Assemble export | `cuber export <id>` |

---

## CubeCobra Import Note

Run `cuber export <id>` after tagging to generate `cubes/<slug>/exports/import-ready.csv`.
To apply: **CubeCobra → your cube → List tab → Export → Replace with CSV Import → upload import-ready.csv**.

---
name: analyze-cube
description: Full stats dashboard + deep environmental analysis + optional primer generation for a locally cached cube
---
# /analyze-cube — Deep Cube Analysis

Produce a stats dashboard and full environmental read of a locally cached cube: color distribution, CMC curve, rarity, card types, archetype viability, per-color breakdown, mana inventory, interaction density, drafting signals, and notable cards. Optionally generate a formatted primer document. All metrics are **informational** — no distribution triggers a warning or error.

---

## IRON RULE

**Never assume what a card does from prior knowledge.**
Every card referenced in the analysis MUST cite `oracle_text` from `cubes/<slug>/enriched.json`.
Training-data knowledge of card effects is forbidden. If the oracle text does not support the stated role, do not claim that role.

---

## Balance Checks Are Informational

A mono-colored cube, a combo-focused cube, or a set with 80% blue cards is valid.
Never tell the user their cube is "unbalanced" or "broken" based on generic reference ranges.
Report what exists; let the user interpret it.

---

## Prerequisites

**Finding the cube folder:** In v2, the folder name is the title slug, not the short ID. Run `cuber list` to see all cubes with their slugs and short IDs. Use `cubes/<slug>/` for all file path operations.

**enriched.json is required.** Before running the deep analysis, check that `cubes/<slug>/enriched.json` exists. If it does not:
```
enriched.json not found — run `cuber enrich <id>` first
```
Stop and wait for the user to enrich.

**Tags are optional but unlock more analysis.** Check whether any card in `enriched.json` has a non-null `taxonomic_profile`. If none do:
- Run: stats dashboard, environment characterization, per-color breakdown, mana and fixing inventory
- Skip: archetype viability matrix, interaction density, drafting signals (tag-dependent), notable cards
- Append: "Run `cuber tag <id>` to unlock archetype analysis"

---

## Workflow

### Step 1 — Run stats command

```
cuber stats <id>
```

This prints the human-readable report to stdout and writes `cubes/<slug>/analysis.json`.

### Step 2 — Stats Dashboard

Read `cubes/<slug>/analysis.json`. Present:

**Color Identity Distribution**
Counts and percentages for W / U / B / R / G / Multi / Colorless.

**CMC Curve**
Count by CMC bucket (0–7+), split by creature vs. non-creature.

**Rarity Breakdown**
Counts and percentages for Common / Uncommon / Rare / Mythic.

**Card Type Breakdown**
Creature / Instant / Sorcery / Enchantment / Artifact / Planeswalker / Land / Other.

**Archetype Tag Density** (only if tags exist)
Cards per tag, sorted descending. Tags with fewer than 3 cards get an informational note — not a warning.
If no tags: suggest running `/tag-cube <short-id>` first.

Confirm the file path: "Full analysis: cubes/<slug>/analysis.json"

---

### Step 3 — Environment Characterization

Read `cubes/<slug>/enriched.json`. Produce a single summary sentence capturing the cube's identity:
- Power level signal (powered, unpowered, cubetutor-style, etc. — inferred from card names and oracle texts)
- Dominant archetype themes (from top tags by card count if tagged; from oracle text patterns if not)
- Any multicolor-reward signals

Example form: "Balanced unpowered environment with strong graveyard and sacrifice themes; two-color strategies are well-supported, with black and green as the deepest colors."

If one color holds more than 40% of cards, name it and its primary mechanical identity.

---

### Step 4 — Archetype Viability Matrix

*Requires tags. Skip if no `taxonomic_profile` present.*

**Viability threshold:** `round(N × 0.05)` supporting cards, where N = total mainboard card count.

For each color pair (WU, WB, WR, WG, UB, UR, UG, BR, BG, RG), enumerate the synergy clusters that have cards in those colors. For each cluster:
- **Viable**: at least one Payoff card AND ≥ threshold Enabler/Fodder + Engine/Outlet cards in that cluster for this color pair
- **Partial**: Payoff cards exist but supporting cards are below threshold — show the count
- **None**: no Payoff cards

Display as a compact table or list. Include trios only if a synergy cluster is clearly tri-color.

---

### Step 5 — Per-Color Breakdown

Read oracle texts from `enriched.json`. For each color present in the cube, write a short paragraph:
1. What the color does mechanically — grounded in oracle text patterns (e.g., "most black cards reference sacrifice or graveyard")
2. Which archetypes it anchors (if tagged)
3. 2–4 representative cards that exemplify its role, each with a brief oracle text excerpt

For colors with mixed identity, describe the 2–3 strongest roles with one card example each.

---

### Step 6 — Mana and Fixing Inventory

Enumerate dual lands and mana fixers from `enriched.json`. Group by color pair. Assign a fixing score:
- **GOOD** — ≥ 2 common-rarity duals for this pair
- **THIN** — 1 common dual OR 1+ rare duals
- **NONE** — 0 accessible duals for at least one color in the pair

Present as a table: color pair | fixers | score.

If most pairs score GOOD: note that multi-color is well-supported.
If multiple pairs score NONE: name the unsupported color combinations.

---

### Step 7 — Interaction Density

*Requires tags. Skip if no `taxonomic_profile` present.*

Count from `taxonomic_profile.structural_roles` and `taxonomic_profile.mechanical_functions`:
- Targeted removal (destroy, exile, bounce targeting a permanent)
- Sweepers (board wipes)
- Counterspells

Express each as count and % of non-land cards.

- If interaction > 30% of non-land cards: note high interaction density and likely slower game pace.
- If interaction < 15% of non-land cards: note that threats will typically resolve and games will be decided by board presence.

---

### Step 8 — Drafting Signals

*Requires tags. Skip if no `taxonomic_profile` present.*

Identify 3–5 drafting signals specific to this cube:
1. **Open archetypes**: viable archetypes where the synergy cluster has room — not flooded with support cards
2. **Overdrafted colors**: colors with high card density that will be contested in most drafts
3. **Fixing traps**: color pairs that appear viable but score THIN or NONE on fixing
4. Any curve or tempo traps worth flagging

---

### Step 9 — Notable Cards

*Requires tags. Skip if no `taxonomic_profile` present.*

Identify 5–10 cards that behave unusually in this cube's context. Candidates:
- Cards in a structural role (Engine/Outlet, Enabler/Fodder) where that role has fewer than 3 other representatives in its cluster — irreplaceable role-fillers
- Cards that are stronger or weaker than their general reputation due to cube-specific synergies
- Cards that serve as key signals for an archetype

Each entry MUST include the card's `oracle_text` from `enriched.json`.

---

## Primer Offer

After completing the analysis, ask:

> **Write a primer for this cube? [y/N]**

If the user answers N or presses Enter (default no): end the skill without writing any files.

If the user answers Y: proceed to section selection.

---

### Section Selection

Present the 7 primer sections as a multi-select question. All sections are selected by default. The user may deselect any they do not want.

Use **AskUserQuestion** with `multiSelect: true`:

Sections:
1. Overview — cube identity, philosophy, power level, size, format note
2. The Archetypes — color-pair/trio breakdowns with synergy clusters and example cards
3. Color Breakdown — per-color description with key cards
4. The Environment — gameplay pace, interaction density, what's over/undervalued vs normal
5. Drafting the Cube — signals, open archetypes, fixing requirements, traps
6. Mana and Fixing — land inventory, multi-color viability, splash thresholds
7. Notable Cards — 5–10 cards with unusual roles in this environment

If the user selects The Archetypes (section 2) or Notable Cards (section 7) but no tags exist: write those sections with a note that tag-based detail is unavailable and `cuber tag <id>` should be run first.

---

### Overwrite Check

Before writing, check whether `cubes/<slug>/primer.md` already exists.

- If it **does not exist**: write directly to `primer.md` without asking.
- If it **exists**: ask "primer.md already exists — overwrite it? [y/N]"
  - Y → write to `primer.md` (overwrite)
  - N → write to `primer_ai.md`

---

### Writing the Primer

Write only the sections the user selected. Tone: **informational and celebratory**. Present what the cube does and highlight what is interesting about it. The primer MAY acknowledge what the cube does not aim to do, but MUST NOT frame anything as a flaw, mistake, or weakness.

All card names mentioned in the primer MUST cite an oracle text excerpt from `enriched.json`.

**Section guidelines:**

**1. Overview**
Introduce the cube: title, size, format (if set), power level, and the central design philosophy. Frame what makes this cube distinctive.

**2. The Archetypes**
Walk through each viable archetype from the viability matrix. For each: name it, describe the synergy cluster, name 2–3 key cards with oracle text excerpts. Frame partial archetypes as "emerging" or "build-around" rather than incomplete.

**3. Color Breakdown**
Adapt the per-color breakdown from the analysis into primer prose. For each color: its mechanical identity, which archetypes it anchors, 2–3 signature cards with oracle excerpts.

**4. The Environment**
Describe gameplay pace (fast/slow/grindy), how much interaction exists, and what tends to be over- or undervalued in this cube relative to generic draft environments. Grounded in interaction density and archetype data.

**5. Drafting the Cube**
Cover: which archetypes are typically open, which colors are contested, fixing requirements, and any common traps to avoid. Encourage drafters to follow signals.

**6. Mana and Fixing**
Walk through the fixing inventory. Which color pairs are well-supported, which need extra attention. Splash thresholds for this environment.

**7. Notable Cards**
Highlight 5–10 cards with their oracle text excerpts. Frame each as an insight: "In this cube, [Card] does X because Y."

---

### File Path Confirmation

After writing, output:
```
Primer written to: cubes/<slug>/primer.md
```
(or `primer_ai.md` as applicable)

---

## Tool Selection Table

| Task | How |
|------|-----|
| Resolve cube slug | `cuber list` |
| Compute all stats | `cuber stats <id>` |
| Read structured stats | Read `cubes/<slug>/analysis.json` |
| Check enriched.json exists | Read `cubes/<slug>/enriched.json` |
| Check if tags exist | `enriched.json` → any card with non-null `taxonomic_profile` |
| Read oracle texts | Read `cubes/<slug>/enriched.json` — never training data |
| Read archetype tags | `enriched.json` → `taxonomic_profile.synergy_clusters` |
| Count interaction cards | `enriched.json` → `taxonomic_profile.structural_roles` + `mechanical_functions` |
| Read mana fixers | `enriched.json` → cards with `type_line` containing "Land" or oracle text with "add {" |
| Section checklist | AskUserQuestion with multiSelect: true |
| Check primer.md exists | Check `cubes/<slug>/primer.md` |
| Write primer | Write tool → `cubes/<slug>/primer.md` or `primer_ai.md` |
| Export primer | `cuber export <id>` (copies primer.md to exports/) |

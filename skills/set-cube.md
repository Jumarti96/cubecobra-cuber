# /set-cube — Build a Cube from a Retail MTG Set

Create a cube from all (or a filtered subset of) cards in a given Magic: The Gathering retail set. Identifies mechanical themes, assesses draft viability, and optionally suggests cuts to reach a target size.

---

## IRON RULE

**Never assume a set's themes from prior knowledge.**
All mechanical identity analysis MUST come from reading oracle text of the fetched cards.
If you know what a set's mechanics are from training data, verify them against oracle text before stating them.

---

## Workflow

### Step 1 — Resolve the Set Code

If the user provides a full set name (e.g., "Edge of Eternities"), resolve it to a Scryfall set code:
- Check for obvious abbreviations (e.g., "EOE" → "eoe", "Edge of Eternities" → "eoe")
- If uncertain, ask: "Could you confirm the Scryfall set code? You can find it at scryfall.com/sets"

### Step 2 — Clarify Inclusion Preferences

Ask using AskUserQuestion (can be combined into one prompt):
1. Include basic lands? (default: No)
2. Include tokens? (default: No)
3. Restrict to specific rarities? (default: all rarities)

### Step 3 — Fetch the Set

```
cuber fetch-set <set-code>
```

Add flags based on Step 2 answers:
- `--include-basics` if user wants basics
- `--include-tokens` if user wants tokens

Then enrich:
```
cuber enrich <set-code>
```

### Step 4 — Identify Mechanical Identity

Read ALL oracle texts from `cubes/<set-code>/enriched.json`.

For each distinct mechanic keyword found in oracle text (e.g., "surveil", "cascade", "convoke"):
1. Count how many cards reference it.
2. Note the colors those cards appear in.
3. Do NOT state a mechanic is present unless oracle text evidence supports it.

Identify the top 5–8 mechanics by card count.

### Step 5 — Analyze for Draft Viability

Using oracle text data:

**Archetype coverage**: For each major mechanic, does the set provide:
- Enablers (cards that set up the mechanic)
- Payoffs (cards that reward having enabled it)
- At least one representation in multiple colors?

**Color balance**: Count cards by color identity. Note any color with significantly fewer cards.

**Removal density**: Count cards whose oracle text destroys, exiles, bounces, or deals damage to permanents.

**Curve assessment**: Note CMC distribution — is there a critical mass of 1–2 drops for aggro archetypes?

All assessments are **informational**. A set with only one viable archetype is a valid cube — just one with limited draft diversity.

### Step 6 — Report

Present:

**Set: <SET-CODE> — <N> cards**

| Theme | Cards | Primary Colors | Notes |
|-------|-------|----------------|-------|
| Surveil | 42 | U, B | Strong enabler + payoff density |
| ... | | | |

Color balance, removal count, curve summary.

**Draft Viability Assessment**: [your observation — not a grade]

### Step 7 — Optional Size Reduction

If the set has more cards than a target draft size, offer:
> "This set has <N> cards. Would you like me to suggest cuts to reach a target size (e.g., 360)?"

If yes, propose cuts prioritized by:
1. Duplicate effects (multiple cards that do the same thing — cut the weaker one, cite oracle text comparison)
2. Narrow/situational cards (oracle text applies in very few scenarios)
3. Low-power cards relative to the set's baseline

Apply self-grill before presenting cuts (same Proposer/Challenger pattern as `/suggest-cube`).

### Step 8 — Output Path

All data lives in `cubes/<set-code>/` (the set code acts as both short_id and slug):

```
cubes/<set-code>/
  remote/mainboard.csv   ← pristine Scryfall snapshot (never edit)
  mainboard.csv          ← working card list
  enriched.json          ← written by enrich
  meta.json              ← includes source: "scryfall-set:<code>"
  primer.md
  exports/               ← export destination
  decks/                 ← deck files
```

All v2 commands work identically on a set cube as on a CubeCobra-fetched cube:

```
cuber status <set-code>        # diff working vs. remote snapshot
cuber add-card <set-code> "X"  # add cards to the working list
cuber export <set-code>        # assemble exports/import-ready.csv
```

After this skill completes, all other skills (`/tag-cube`, `/analyze-cube`, `/build-deck`, `/suggest-cube`) work identically on the set cube.

---

## Tool Selection Table

| Task | Command |
|------|---------|
| Fetch set cards | `cuber fetch-set <code>` |
| Enrich with Scryfall data | `cuber enrich <code>` |
| Read oracle texts | `cubes/<code>/enriched.json` — never training data |
| Compute stats | `cuber stats <code>` |
| Status diff | `cuber status <code>` |
| Export import-ready CSV | `cuber export <code>` |

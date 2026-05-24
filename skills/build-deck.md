---
name: build-deck
description: Build a deck from a locally cached cube in any supported format
---
# /build-deck — Cube Deck Builder

Build a deck from a locally cached cube in any supported format. Cards must come only from the cube pool. A self-grill gate runs before the final list is shown. The deck is saved as deck.json, deck.csv, deck.mwDeck, and analysis.md in a per-deck subfolder when you confirm.

---

## IRON RULE

**Never assume what a card does from prior knowledge.**
Every inclusion and justification MUST cite `oracle_text` from `enriched.json`.
If the oracle text does not support the stated role, the card must be replaced.

---

## Prerequisites

```
cuber fetch <id>
cuber enrich <id>
cuber tag <id>      ← required; taxonomic_profile drives pipeline discovery
```

---

## Supported Formats

| Format | Deck Size | Commander | Sideboard default |
|--------|-----------|-----------|-------------------|
| `40-card` | 40 cards | No | 8 cards |
| `60-card` | 60 cards | No | 15 cards |
| `commander-60` | 61 cards (60 + 1 commander) | 1 or 2 partners | Optional |
| `commander-100` | 101 cards (100 + 1 commander) | 1 or 2 partners | Optional |

---

## Phase 0: Card Pool Definition

Before any analysis, establish what cards are available to the deck builder.

Ask the user (in natural language):
> "Are there any pool restrictions? For example: up to 2 copies of commons and uncommons, only certain rares, or specific cards to exclude. Press Enter to use the full cube mainboard."

If the user provides no restrictions, proceed immediately with the full cube mainboard.

From the user's answer, infer a `card_pool_rules` object:

```json
{
  "base": "cube_mainboard",
  "multipliers": { "common": 2, "uncommon": 2 },
  "only_from": { "rare": ["Card A", "Card B"] },
  "excluded": ["Oko, Thief of Crowns"]
}
```

- `base` is always `"cube_mainboard"` — only the mainboard is supported.
- `multipliers`: per-rarity max copy count (rarity not listed = 1 copy).
- `only_from`: per-rarity allowlist — all other cards of that rarity are excluded.
- `excluded`: specific card names excluded regardless of other rules.

**Display the inferred `card_pool_rules` and ask the user to confirm before proceeding.**

If the user corrects the inferred object, update it and re-display. Proceed only after explicit confirmation.

Once confirmed, pass `card_pool_rules` to `cube_search.load_merged_pool(id, card_pool_rules=...)`. All subsequent phases use this filtered pool exclusively.

---

## Phase 1: Interview

Use AskUserQuestion to collect decisions before any analysis. Ask in a single multi-part message where possible.

**Required:**
1. **Cube** — short ID or slug (or list available cubes from `cubes/*/meta.json`)
2. **Format** — 40-card / 60-card / Commander-60 / Commander-100
3. **Colors** *(optional)* — any color preference? Default is pool-derived; say "surprise me" or leave empty to let strategy discovery determine colors from the winning pipeline
4. **Intent** — how do you want to play? Choose one:
   - `Competitive` — maximize win consistency, interaction density
   - `Experimental` — unusual synergies, high variance, cross-archetype overlap
   - `Fun / Niche` — most distinctive or uncommon win condition in the pool
   - `Specific Constraint` — describe your constraint (e.g., "I want to play around Grapeshot")
5. **Power level** — casual / unpowered / powered / competitive

**Optional (ask but accept empty):**
6. **Sideboard size** — accept format default or specify

Note: card pool restrictions were collected in Phase 0. Do not re-ask them here.

---

## Phase 2: Deck Identity (Discovery)

Load the pool: `cube_search.load_merged_pool(id, card_pool_rules=...)`.

### Step 0: Environment Profile

**Run this first, before discovery.**

Check for an existing cube analysis file in either location (try both):
- `cubes/<slug>/exports/analysis.json`
- `cubes/<slug>/analysis.json`

If neither exists, run `cuber stats <id> --json` to generate it, then read the result.

From the analysis file, extract the following signals:

**Color distribution** — is the cube balanced across colors, or skewed toward certain identities? A cube with 30%+ colorless cards may have a strong artifacts theme regardless of color choice.

**Dominant archetype tags** — what are the top 5 tags by card count across the entire cube? These define what the environment rewards, independent of the user's color restrictions.

**Multicolor environment signals:**
- `domain` tag density ≥ 10% of non-land cards → **domain environment**: 4-5 color decks are potentially viable if fixing supports it
- Lands that produce 3 or more colors (filter `enriched.json` lands by `len(color_identity) >= 3`) → **universal fixing present**: 3+ color decks are structurally supported
- `kicker` tag density ≥ 10% → **kicker environment**: multicolor breadth matters less; prioritize on-color efficiency

Produce an **Environment Characterization** sentence before proceeding:
> "Balanced draft environment with strong graveyard and spells-matter themes; domain signal present (12% tag density) but universal fixing absent — 3-color is achievable, 4-5 requires explicit fixing."

---

### Step 1: Mana Infrastructure Inventory

**Run after the Environment Profile.** Read all lands from `enriched.json` where `board == "mainboard"`. Group non-basic lands by the number of colors they produce and their rarity.

Display a dual land table covering all color pairs present:

```
Dual Land Inventory
──────────────────────────────────────────────────────────────
Color Pair   Common Duals              Rare Duals (if any)
WU           Idyllic Beachfront        Adarkar Wastes
UR           Molten Tributary          Shivan Reef
...
3+ color     Crystal Grotto (C)        Thran Portal (R)
```

For each **candidate color combination** being evaluated:
- Count freely accessible duals at **common** rarity: 0 = no fixing, 1 = minimal, 2+ = solid
- Count duals at **rare** rarity: note whether available under the pool rules
- Count lands producing 3+ colors
- Assign a fixing score: **GOOD** (≥ 2 common duals per color pair), **THIN** (1 common dual or 1+ rare dual per pair), **NONE** (0 accessible duals for at least one pair)

Carry this fixing inventory forward — it informs pipeline color feasibility in Step 2.

---

### Step 2: Pipeline Discovery

**Find all Payoff candidates.**

Query the filtered pool for cards where `taxonomic_profile.structural_roles` contains `"Payload/Payoff"`. These are the win condition candidates.

If no cards have `"Payload/Payoff"`, fall back to cards with `"Standalone Threat"` as implicit payoffs and note this in the output.

**Validate each Payoff against its synergy cluster support.**

For each Payoff candidate:
1. Read its `taxonomic_profile.synergy_clusters`.
2. Count all cards in the pool whose `taxonomic_profile.synergy_clusters` overlap with the Payoff's clusters AND whose `taxonomic_profile.structural_roles` include `"Enabler/Fodder"` or `"Engine/Outlet"`.
3. Viability threshold: `round(N × 0.05)` supporting cards, where N is the target deck size.
4. If supporting card count ≥ threshold → pipeline is **viable**.
5. If supporting card count < threshold → pipeline is **non-viable** (exclude from shortlist).

**Apply color constraint if specified.**

If the user declared a color preference in Phase 1, also exclude Payoffs whose core pipeline cards (the Payoff + its primary support cards) fall outside the stated color identity.

**Build the shortlist.**

Collect all viable pipelines and rank them by intent (from Phase 1):
- `Competitive` → rank by highest count of Interaction/Disruption + Infrastructure/Consistency support cards in the pipeline's clusters
- `Experimental` → rank by highest cross-cluster overlap (Payoff shares synergy clusters with the most distinct card groups)
- `Fun / Niche` → rank by most unusual win condition (rarest synergy_cluster combination in the pool)
- `Specific Constraint` → rank by closest match to the user-stated constraint

Select the top 3–5 for the shortlist.

If fewer than 3 viable pipelines exist, include all viable ones without padding.

If no viable pipelines exist, report:
> "No viable pipelines found in the current pool."

Ask whether to lower the viability threshold or change pool rules (restart Phase 0).

Tag density is still shown as context (count of Enabler/Fodder and Engine/Outlet per synergy cluster), but strategy selection is driven by the pipeline shortlist, not tag density alone.

---

## Phase 3: Strategy Selection

Present the shortlist to the user.

For each pipeline entry display:
- Payoff card name and its synergy cluster(s)
- Supporting card count (Enabler/Fodder + Engine/Outlet in the cluster)
- Color identity of the pipeline's core cards
- Fixing score for that color combination (from Step 1)

**Highlight the top recommendation** (marked clearly, based on intent ranking). If the user had no color preference in Phase 1, show the recommended pipeline's color identity as the suggested default.

Ask the user to:
- Accept the top recommendation
- Pick a different pipeline from the shortlist
- Describe their own constraint (AI constructs and validates a pipeline anchored to it)

Lock the selected pipeline. **Carry the full shortlist forward — it will be used for re-evaluation in Phase 9 if needed.** The shortlist is never recomputed.

---

## Phase 4: Commander Selection (Commander formats only)

Skip this phase for 40-card and 60-card formats.

Run `commander_finder.find_commanders(id, color_identity=chosen_colors)`.

Display the formatted table using `commander_finder.format_commanders_table(candidates)`.

Ask the user to select:
- **1 commander** — any eligible card
- **2 partners** — both must have Partner / Friends forever / Doctor's companion / "Partner with" each other

On selection, derive the **binding color constraint**: the union of commanders' `color_identity`. All non-land cards must have color identity within this set.

---

## Phase 5: Deck Build

Use `cube_search.search_pool(pool, color_identity=..., ...)` to fill each slot category.

For each slot, read `oracle_text` from `enriched.json` before including any card. Do not rely on training-data knowledge of what the card does.

**Slot allocation — proportional to N.**

All slot counts are derived as proportions of the total deck size N. State every proportion as a percentage and the resulting absolute count: `round(N × proportion)`. Include a one-sentence rationale for each allocation explaining why the proportion fits this specific strategy type.

Required format for every allocation:
> "Lands: 15 (37.5% of N=40) — combo strategies run lean to fit more engine pieces; this deck generates additional mana via ritual effects."

**Reference proportions by strategy type (starting points, not fixed targets):**

| Slot | Combo / Storm | Aggro | Midrange | Control |
|------|--------------|-------|----------|---------|
| Lands | 32–38% | 35–40% | 38–42% | 40–45% |
| Interaction | 15–20% of non-land | 10–15% | 20–25% | 25–35% |
| Threats / Payoffs | 20–30% of non-land | 35–45% | 25–35% | 15–20% |
| Engine / Enablers | 25–35% of non-land | 10–20% | 20–30% | 20–30% |

The AI chooses proportions that fit the selected pipeline and defends them. These ranges are guidance; the rationale must justify any deviation.

**Mana source allocation — derived from pip demand.**

1. Count all colored pips in the deck's mana costs across all cards.
2. Calculate each color's share of total pips.
3. Distribute producing lands proportionally to pip share.
4. State the pip counts and the derived split explicitly.

Example:
> "14 blue pips, 8 black pips (64% / 36%). Targeting 11 blue sources and 6 black sources out of 17 total lands."

**Restrictions enforcement:** At every pick, verify the card does not violate `card_pool_rules`. Build a running compliance checklist.

**Verify before including any card:**
1. Card exists by name in enriched.json — hard check, no exceptions
2. Oracle text supports its assigned role — cite it explicitly
3. Color identity is within the chosen color constraint
4. `card_pool_rules` are not violated

---

## Phase 6: Mana Audit Gate

Convert the proposed deck to a list of card dicts (from `enriched.json` fields + merged tags).

Run `deck_audit.mana_audit(deck_cards, format, commander_cards)`.
Display the report using `deck_audit.format_audit_report(audit)`.

**If audit result is FAIL:**
- Adjust land count toward the recommended target
- Re-balance producing lands if a color gap > 15pp exists
- Replace non-producing utility lands with on-color dual lands from the pool
- Re-run the audit after adjustments
- Log all swaps made

**If audit result is WARN:** Note the issue, proceed without blocking.
**If audit result is PASS:** Proceed.

Do not show the deck to the user until the audit is at least WARN or PASS.

---

## Phase 7: Sideboard

Skip if the user opted out or if format does not normally use sideboards.

Default sizes: 8 (40-card), 15 (60-card), custom (commander).

Fill sideboard from the remaining cube pool (cards not already in the main deck):
- **Hate cards**: match likely opposing archetypes (graveyard hate, artifact removal, etc.) — cite oracle text for each
- **Flex slots**: cards that improve in certain matchups; explain what they answer

Challenger evaluates sideboard cohesion in Phase 9.

---

## Phase 8: Pre-Grill Check

Before the self-grill, perform hard verification:

1. **Cube membership**: every card in main deck + sideboard exists in `enriched.json` by exact name
2. **Oracle text coverage**: every card has a non-empty `oracle_text` in enriched.json
3. **Restrictions compliance**: full check against `card_pool_rules` — produce checklist
4. **Mana audit**: confirm audit result is not FAIL (re-run if deck changed since Phase 6)

Remove any card failing check 1. Replace from the pool. Flag any oracle text gaps.

---

## Phase 9: Self-Grill (Hard Gate)

Spawn two parallel Agent calls. Neither agent sees the other's output during generation.

### Proposer Agent

Defend the full deck list (main + sideboard). For every card:
- State its role in the strategy
- Quote `oracle_text` from enriched.json: `Oracle: "..."`
- Confirm it fits the selected pipeline from Phase 3
- Confirm it passes the `card_pool_rules` check
- Confirm color identity is within constraint

### Challenger Agent

Attack the deck independently:
1. **Cube membership** — verify each card exists in enriched.json; flag any phantom inclusions (MUST be removed)
2. **Oracle text** — read oracle text independently; does it actually do what Proposer claims?
3. **Restrictions** — check every card against `card_pool_rules`; flag violations
4. **Identity fit** — does each card contribute to the selected pipeline? Suggest cuts that don't
5. **Better alternatives** — is there a card in the cube pool that fills the slot more efficiently? Check enriched.json tags and oracle text
6. **Proportional validation** — verify each slot allocation is within accepted MTG deckbuilding ranges for the stated strategy type. Flag any proportion that deviates significantly from convention without adequate rationale
7. **Sideboard cohesion** — does the sideboard address realistic weaknesses? Are slots wasted?
8. **Mana audit re-run** — independently run mana_audit on the list; report discrepancies
9. **Pipeline viability** — can this pipeline actually achieve its stated win condition with the available card pool? If not, state explicitly: **"This pipeline cannot achieve its stated win condition with the available card pool."**

### Resolve Grill

- Proposer revises challenged slots using only cards from enriched.json
- Challenger confirms each revision
- Any card without confirmed cube membership must be removed
- Final list must satisfy: all cards in cube + oracle text supports all roles + audit ≥ WARN

### Re-evaluation Path

If the Challenger states **"This pipeline cannot achieve its stated win condition with the available card pool"** (this is the specific trigger — not a mana issue, not a ratio issue, not a card-swap issue):

1. Log the reason the current pipeline was rejected.
2. Select the **next pipeline** from the Phase 3 shortlist (do NOT re-run discovery or Phase 2).
3. Rebuild from **Phase 5 (Deck Build)** with the new pipeline.
4. Re-run Phases 6–9 for the new pipeline.

If the shortlist is exhausted (all shortlisted pipelines have been attempted and rejected by the Challenger):
> "All shortlisted pipelines were rejected. Options: (1) Restart Phase 0 to adjust pool rules. (2) Lower the viability threshold and rerun discovery."

Wait for user guidance before proceeding.

---

## Phase 10: Present Final Deck

Display the deck using the enforced format below. **Section order is strict — do not reorder.**

```
═══════════════════════════════════════════════════════════════════
DECK: {name}  |  {format}  |  {colors}  |  {N} cards
═══════════════════════════════════════════════════════════════════

{Deck identity — 2–4 sentences of prose describing strategy and key interactions.}

MAINBOARD ({spells} spells + {lands} lands = {total})
──────────────────────────────────────────────────────────────────

LANDS ({N})
  Nx BasicLand
  Nx DualLand          Brief note (e.g. "BR dual, enters tapped")
  ...

CREATURES ({N})
CMC  Card                    Qty   Role                    Rar
  1  Vexing Devil            x1    Turn-1 threat           R
  2  Asylum Visitor          x2    Card engine             U
  ...

INSTANTS & SORCERIES ({N})
CMC  Card                    Qty   Role                    Rar
  1  Lightning Axe           x2    Removal/Discard outlet  U
  ...

OTHER SPELLS ({N})
CMC  Card                    Qty   Role                    Rar
  3  Stensia Masquerade      x1    Combat pump             U
  ...

SIDEBOARD ({N})
──────────────────────────────────────────────────────────────────
Card                    Qty   Role / When to board in          Rar
Tragic Slip             x2    Recursive threats, morbid         C
Abrade                  x2    Artifacts + creatures             U
...

── ANALYSIS ───────────────────────────────────────────────────────
{Write freely here. No structure constraints. This is where you
surface the most interesting strategic observations about the deck:
synergy interactions, mechanical calculations (e.g. madness trigger
counts, flashback enabler counts), matchup notes, play patterns,
key card interactions. Use tables when they add clarity. Minimum
one substantive observation; there is no maximum.}

MANA AUDIT: {PASS/WARN/FAIL}
──────────────────────────────────────────────────────────────────
{format_audit_report output — use deck_audit.format_audit_report(audit)}

RESTRICTIONS COMPLIANCE
──────────────────────────────────────────────────────────────────
{checklist of each restriction with pass/fail}
═══════════════════════════════════════════════════════════════════
```

**Format rules:**
- `OTHER SPELLS` covers enchantments, artifacts, planeswalkers, sagas — omit the section if empty
- `INSTANTS & SORCERIES` is one section; do not split instants from sorceries
- No oracle excerpt column in any card table section
- The `── ANALYSIS ──` section is always present; write at least one observation even for simple decks
- Rarity abbreviation: C Common, U Uncommon, R Rare, M Mythic

Ask: **"Save this deck? [y/N]"**

---

## Phase 11: Save

On confirmation, prompt for a deck name if not already provided. Sanitize to a filesystem-safe slug (lowercase, alphanumeric + hyphens).

All four files go into a single subfolder: `cubes/<id>/decks/<name>/`

---

**Write deck.json** using the Write tool to `cubes/<id>/decks/<name>/deck.json`:
```json
{
  "deck_name": "bg-graveyard",
  "cube_id": "551c6382-d024-4039-8fce-1cf9c23135b3",
  "cube_slug": "innistrad-remastered-set-dmu-dual-lands",
  "built_at": "2026-05-20T14:30:00Z",
  "format": "40-card",
  "strategy": "graveyard midrange",
  "colors": "BG",
  "identity": "Black-Green graveyard midrange with strong threat density",
  "restrictions": { ... },
  "commander": null,
  "mana_audit": { ... },
  "mainboard": [ {card dicts, board: "mainboard"} ],
  "sideboard": [ {card dicts, board: "sideboard"} ]
}
```

JSON rules:
- `cube_id`: the UUID from `meta.json` (`id` field)
- `cube_slug`: the slug from `meta.json` (`slug` field)
- `built_at`: ISO 8601 UTC, second precision, Z suffix — `"2026-05-20T14:30:00Z"`
- Card `board` values: `"mainboard"` / `"sideboard"` (full words, never `"main"` or `"side"`)
- `mana_audit` must include: `land_count`, `recommended_land_count`, `land_count_status`, `ramp_count`, `avg_cmc`, `pip_demand`, `land_color_production`, `color_balance_status`, `color_balance_per_color`, `overall_status`

Use the Write tool (apostrophes in card names break shell quoting).

---

**Write deck.csv** using the Write tool to `cubes/<id>/decks/<name>/deck.csv`:
Use CUBECOBRA_CSV_COLUMNS column order. Mark mainboard cards with `board=mainboard`, sideboard with `board=sideboard`.

---

**Write deck.mwDeck** using `exporter.write_mwdeck(mainboard, sideboard, short_id, deck_name)`:
The function writes to `cubes/<id>/decks/<name>/deck.mwDeck` automatically.

---

**Write analysis.md** using `exporter.write_deck_analysis_md(analysis_text, short_id, deck_name, frontmatter)`:

The `analysis_text` is the full Phase 10 output reformatted as Markdown:
- Section headers use `##` (e.g. `## MAINBOARD`)
- Card tables are in fenced code blocks (``` ``` ```) to preserve monospace alignment
- The `── ANALYSIS ──` zone body is rendered as free Markdown (not in a code block)
- In the CREATURES / INSTANTS & SORCERIES / OTHER SPELLS / SIDEBOARD tables AND in the ANALYSIS zone, wrap non-basic card names as Scryfall search links: `[Card Name](https://scryfall.com/search?q=!"Card+Name")`
- Basic land names (Plains, Island, Swamp, Mountain, Forest, Wastes) are plain text — no links

The `frontmatter` dict:
```python
{
    "deck_name": deck_name,
    "cube_id": cube_id,       # UUID from meta.json
    "cube_slug": cube_slug,   # slug from meta.json
    "colors": colors,         # e.g. "BR"
    "format": format,         # e.g. "40-card"
    "built_at": built_at,     # same timestamp as deck.json
    "mana_audit_status": audit["overall_status"],    # "PASS" / "WARN" / "FAIL"
    "restrictions_status": "PASS",  # or "FAIL" if any check failed
}
```

---

Confirm all four paths:
```
Saved:
  cubes/<id>/decks/<name>/deck.json
  cubes/<id>/decks/<name>/deck.csv
  cubes/<id>/decks/<name>/deck.mwDeck
  cubes/<id>/decks/<name>/analysis.md
```

---

## Tool Selection Table

| Task | Tool / File |
|------|-------------|
| Load card pool (with pool rules) | `cube_search.load_merged_pool(id, card_pool_rules=...)` |
| Filter by color/type/tag/CMC | `cube_search.search_pool(pool, ...)` |
| Query Payoff candidates | Filter pool by `taxonomic_profile.structural_roles` containing `"Payload/Payoff"` |
| Query synergy support | Filter pool by `taxonomic_profile.synergy_clusters` overlap + `"Enabler/Fodder"` or `"Engine/Outlet"` in `structural_roles` |
| Find commander candidates | `commander_finder.find_commanders(id, color_identity)` |
| Display commander table | `commander_finder.format_commanders_table(candidates)` |
| Run mana audit | `deck_audit.mana_audit(deck_cards, format, commander_cards)` |
| Display audit report | `deck_audit.format_audit_report(audit)` |
| Verify card exists | Search `enriched.json` cards[] by exact name |
| Read oracle text | `card.oracle_text` from enriched.json — never training data |
| Write deck files | Write tool → `cubes/<id>/decks/<name>/deck.json` and `deck.csv`. `exporter.write_mwdeck()` → `deck.mwDeck`. `exporter.write_deck_analysis_md()` → `analysis.md` |

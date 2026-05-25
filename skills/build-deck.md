---
name: build-deck
description: Build a deck from a locally cached cube in any supported format
---
# /build-deck — Cube Deck Builder

Build a deck from a locally cached cube in any supported format. Cards must come only from the cube pool. A self-grill gate runs before the final list is shown. The deck is saved as deck.json, deck.tsv, deck.mwDeck, and analysis.md in a per-deck subfolder when you confirm.

---

## IRON RULE

**Never assume what a card does from prior knowledge.**
Every inclusion and justification MUST cite `oracle_text` from the working pool cache (`_workspace/<deck-slug>_working_pool.json`). Phase 9 agents cite oracle text from the grill input bundle (`_workspace/<deck-slug>_grill_input.json`).
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

### Workspace Setup

Run at the very start of Phase 0, before any user prompts or analysis:

1. Create `_workspace/` in the repo root if it does not exist
2. Delete all `_workspace/_tmp_*.py` files left over from any previous run

All temporary Python scripts written during this run go into `_workspace/` (e.g., `_workspace/_tmp_pool.py`, `_workspace/_tmp_audit.py`). No temp scripts are ever written to the repo root.

### Pool Restrictions

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

### Working Pool Cache

After loading the filtered pool, write `_workspace/<deck-slug>_working_pool.json`. Since the deck name is not yet known at Phase 0, derive a temporary slug from the color identity and current timestamp (e.g., `pool-multicolor-20260524143000`). Track this path — all subsequent phases reference it.

Include per-card fields: `name`, `oracle_text`, `colors`, `color_identity`, `taxonomic_profile`, `cmc`, `type_line`, `rarity`, `board`.

Exclude: `image URL`, `image Back URL`, `MTGO ID`, `Custom`, `Voucher`, `status`, `Finish`, `Set`, `Collector Number`, and any other display-only metadata.

**Do not read `enriched.json` after Phase 0 completes.** All card data for Phases 2–7 comes from the working pool cache.

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

Load card data from the working pool cache: `_workspace/<deck-slug>_working_pool.json`. Do not call `cube_search.load_merged_pool` or read `enriched.json`.

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
- Any of `domain`, `vivid`, `converge`, `sunburst` tag density ≥ 10% of non-land cards → **multicolor-reward environment**: cards in this cube get stronger the more colors you play; 3–5 color decks may be worth considering if fixing supports it. Note which mechanic(s) are present.
- Lands that produce 3 or more colors (filter working pool cache lands by `len(color_identity) >= 3`) → **universal fixing present**: 3+ color decks are structurally supported
- `kicker` tag density ≥ 10% → **kicker environment**: multicolor breadth matters less; prioritize on-color efficiency

Produce an **Environment Characterization** sentence before proceeding:
> "Balanced draft environment with strong graveyard and spells-matter themes; domain signal present (12% tag density) but universal fixing absent — 3-color is achievable, 4-5 requires explicit fixing."

**Color count escalation rules** — apply whenever evaluating or recommending color count. Skip only when the user locked a specific color identity in Phase 1, or when Phase 4 commander selection has bound the identity.

| Color count | Recommend when |
|-------------|----------------|
| 1 (Mono) | Pipeline is self-contained in one color; fixing is absent or the strategy gains nothing from off-color cards |
| 2 | Default starting point — evaluate before escalating |
| 3 | Fixing score is GOOD for all pairs in the trio |
| 4 | Multicolor-reward signal present AND fixing GOOD for most pairs, OR universal fixing present |
| 5 | Strong multicolor-reward signal AND universal fixing present, OR user explicitly requested it |

Never recommend a higher color count solely because the tag pool is larger. Fixing supportability must justify the jump.

---

### Step 1: Mana Infrastructure Inventory

**Run after the Environment Profile.** Read all lands from the working pool cache where `board == "mainboard"`. Group non-basic lands by the number of colors they produce and their rarity.

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

### Splash Evaluation

After locking the pipeline, scan the full pool for off-color cards whose `taxonomic_profile.synergy_clusters` overlap with the selected pipeline's clusters and whose `taxonomic_profile.structural_roles` include `"Payload/Payoff"` or `"Engine/Outlet"`. These are splash candidates — high-value cards that directly support the strategy but fall outside the core color identity.

For each candidate, check whether it qualifies as a splash:
- Its `color_identity` contains exactly 1 color not in `core_colors`
- No more than 3 cards of that off-color are being considered

If qualified candidates exist, note them and set `splash_colors` to the list of off-color letters (e.g., `["R"]`). Otherwise set `splash_colors = []`.

Do not present this evaluation to the user or ask for confirmation. Carry `core_colors` and `splash_colors` forward into Phase 5 and Phase 6.

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

Use `cube_search.search_pool(pool, color_identity=core_colors, splash_color_identity=splash_colors, ...)` to fill each slot category. Splash-eligible cards (single off-color CI, ≤ 2 off-color pips OR CMC ≥ 4 OR kicker) are automatically surfaced.

For each slot, read `oracle_text` from the working pool cache before including any card. Do not rely on training-data knowledge of what the card does.

**Slot allocation — proportional to N.**

All slot counts are derived as proportions of the total deck size N. State every proportion as a percentage and the resulting absolute count: `round(N × proportion)`. Include a one-sentence rationale for each allocation explaining why the proportion fits this specific strategy type.

Required format for every allocation:
> "Lands: 15 (37.5% of N=40) — combo strategies run lean to fit more engine pieces; this deck generates additional mana via ritual effects."

**Reference proportions by strategy type (starting points, not fixed targets).**

Classify the selected pipeline into one Macro-Archetype (matching the tagger's `macro_archetypes` field), then read proportions for all slot categories from the table. State the classification and projected Average MV explicitly before allocating:
> "Macro-Archetype: Midrange. Projected Avg MV: 2.4."

Land % is of total deck size N. Non-land proportions are % of non-land cards.

| Slot                  | Tempo   | Combo   | Aggro   | Midrange       | Control |
|-----------------------|---------|---------|---------|----------------|---------|
| Lands                 | 30–34%  | 30–36%  | 30–35%  | 38–42%         | 42–47%  |
| Interaction           | 25–35%  | 10–20%  | 10–15%  | 20–30%         | 35–45%  |
| Threats/Payoffs       | 10–18%  | 5–15%   | 45–55%  | 30–40%         | 5–10%   |
| Engine & Infra.       | 20–30%  | 40–50%  | 0–10%   | 0% (absorbed)  | 10–20%  |

**Midrange Engine & Infra. note:** Midrange does not reserve a separate Engine budget — the expectation is that Threats/Payoffs cards pull double duty. Prefer cards that generate value on their own, but don't reject a strong threat solely because it lacks explicit value text.

**Ontological Blur:** Assign each card to exactly one slot based on its primary function. Do not fractionalize multi-role cards. A Cryptic Command is logged fully under Interaction; its card draw is a bonus, not a separate Engine allocation. Fractionalizing inflates quotas and produces incoherent builds.

The AI chooses proportions that fit the selected pipeline and defends them. These ranges are guidance; the rationale must justify any deviation.

**Then adjust the raw land count with these modifiers (state each even when 0):**
- **Cantrips:** −1 land per 3 one-mana filtering/draw spells (e.g. Opt, Preordain, Brainstorm)
- **Mana dorks/rocks:** −0.5 land per 2 cheap non-land mana sources (MV ≤ 2)
- **MDFCs with a land back:** −0.5 if spell side is situational; −0.3 if spell side is a primary engine piece

State the final land count explicitly:
> "Baseline: 16 (40% of N=40). Modifiers: −1 cantrip, −0 infra, −0 MDFC. Final: 15 lands."

**Mana source allocation — derived from pip demand.**

1. Count all colored pips in the deck's mana costs across **core color cards only**.
2. Calculate each core color's share of total core pips.
3. Distribute producing lands proportionally to core pip share.
4. If `splash_colors` is non-empty, allocate 2–3 dedicated sources per splash color from the remaining land slots — do not include splash pips in the proportional calculation.
5. State the pip counts, derived core split, and any splash source allocation explicitly.

Example:
> "14 blue pips, 8 black pips (64% / 36%). Targeting 11 blue sources and 6 black sources out of 17 total lands."

**Restrictions enforcement:** At every pick, verify the card does not violate `card_pool_rules`. Build a running compliance checklist.

**Verify before including any card:**
1. Card exists by name in the working pool cache — hard check, no exceptions
2. Oracle text supports its assigned role — cite it from the working pool cache
3. Color identity is within the chosen color constraint
4. `card_pool_rules` are not violated

---

## Phase 6: Mana Audit Gate

Convert the proposed deck to a list of card dicts (from the working pool cache + merged tags).

Run `deck_audit.mana_audit(deck_cards, format, commander_cards, core_colors=core_colors, splash_colors=splash_colors)`.
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

## Phase 8: Grill Input Bundle

Before spawning Phase 9 agents, write `_workspace/<deck-slug>_grill_input.json`. If the deck is not yet named, derive a slug from the color identity and strategy type (e.g., `bg-graveyard`).

The bundle contains:
- `deck`: array of all mainboard + sideboard cards, each with `name`, `oracle_text`, `colors`, `color_identity`, `cmc`, `type_line`, `rarity`, `role` (assigned in Phase 5), and `board`
- `audit`: the mana audit result object from Phase 6
- `card_pool_rules`: the confirmed pool rules object from Phase 0
- `restrictions_checklist`: the compliance checklist built during Phase 5
- `working_pool`: the full working pool array from the cache

Both Phase 9 agents read only this file — they do not read `enriched.json`, the working pool cache, or any other cube data file.

---

## Phase 9: Self-Grill (Hard Gate)

Spawn two parallel Agent calls. Neither agent sees the other's output during generation.

### Proposer Agent

Read `_workspace/<deck-slug>_grill_input.json` for all card data. Do not read `enriched.json` or any other cube data file.

Defend the full deck list (main + sideboard). For every card:
- State its role in the strategy
- Quote `oracle_text` from the `deck` array in the grill bundle: `Oracle: "..."`
- Confirm it fits the selected pipeline from Phase 3
- Confirm it passes the `card_pool_rules` check
- Confirm color identity is within constraint

### Challenger Agent

Read `_workspace/<deck-slug>_grill_input.json` for all card data. Do not read `enriched.json` or any other cube data file.

Attack the deck independently. Challenger is the sole verifier for all hard checks — there is no pre-grill phase before this:
1. **Cube membership** — verify each card exists in the `working_pool` array of the bundle by exact name; flag any phantom inclusions (MUST be removed)
2. **Oracle text** — read `oracle_text` from the `deck` array in the bundle independently; does it actually do what Proposer claims?
3. **Restrictions** — check every card against `card_pool_rules` from the bundle; flag violations
4. **Identity fit** — does each card contribute to the selected pipeline? Suggest cuts that don't
5. **Better alternatives** — is there a card in the `working_pool` array of the bundle that fills the slot more efficiently? Check `taxonomic_profile` tags and `oracle_text` from the bundle
6. **Proportional validation** — verify each slot allocation is within accepted MTG deckbuilding ranges for the stated strategy type. Flag any proportion that deviates significantly from convention without adequate rationale
7. **Sideboard cohesion** — does the sideboard address realistic weaknesses? Are slots wasted?
8. **Mana audit re-run** — independently run mana_audit on the list using the `audit` key from the bundle as a reference; report discrepancies
9. **Pipeline viability** — can this pipeline actually achieve its stated win condition with the available card pool? If not, state explicitly: **"This pipeline cannot achieve its stated win condition with the available card pool."**

### Resolve Grill

- Proposer revises challenged slots using only cards from the `working_pool` array in the grill bundle
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
CMC  Card                    Qty   Color  Role                    Rar
  1  Vexing Devil            x1    R      Turn-1 threat           R
  2  Asylum Visitor          x2    B      Card engine             U
  ...

INSTANTS & SORCERIES ({N})
CMC  Card                    Qty   Color  Role                    Rar
  1  Lightning Axe           x2    R      Removal/Discard outlet  U
  ...

OTHER SPELLS ({N})
CMC  Card                    Qty   Color  Role                    Rar
  3  Stensia Masquerade      x1    B      Combat pump             U
  ...

SIDEBOARD ({N})
──────────────────────────────────────────────────────────────────
Card                    Qty   Color  Role / When to board in     Rar
Tragic Slip             x2    B      Recursive threats, morbid   C
Abrade                  x2    R      Artifacts + creatures       U
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
- `Color` column value is the card's base mana cost colors from the `colors` field (not `color_identity`); kicker pips are excluded; CubeCobra single-letter notation: `B`, `R`, `BR`, `GU`, `C` (colorless); pad all Color values to the same column width for alignment
- **Canonical section names for analysis.md** (strict — do not rename or reorder): `## MAINBOARD`, `## SIDEBOARD`, `## ANALYSIS`, `## MANA AUDIT: {PASS|WARN|FAIL}`, `## RESTRICTIONS COMPLIANCE`; sub-headers: `### LANDS`, `### CREATURES`, `### INSTANTS & SORCERIES`, `### OTHER SPELLS`
- Non-basic card names in all card table sections and the ANALYSIS zone must be Scryfall search links: `[Card Name](https://scryfall.com/search?q=!"Card+Name")`; basic land names (Plains, Island, Swamp, Mountain, Forest, Wastes) are plain text — no links

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

**Write deck.tsv** using the Write tool to `cubes/<id>/decks/<name>/deck.tsv`:
Tab-separated values — no quoting or escaping of any kind. Columns in this exact order:
`name`, `CMC`, `Type`, `Color`, `Set`, `Collector Number`, `Rarity`, `Color Category`, `status`, `Finish`, `board`, `maybeboard`, `image URL`, `image Back URL`, `tags`, `Notes`, `MTGO ID`, `Custom`, `Voucher`

TSV rules:
- Values are separated by tab characters; never use CSV quoting even if a value contains a comma
- One row per card copy (a ×2 card produces 2 identical rows)
- `board` column: `mainboard` or `sideboard` (full words only, never `main` or `side`)
- `tags` field uses semicolons as its internal separator (e.g. `Aristocrats/Sacrifice;Payload/Payoff`)

---

**Write deck.mwDeck** using `exporter.write_mwdeck(mainboard, sideboard, short_id, deck_name)`:
The function writes to `cubes/<id>/decks/<name>/deck.mwDeck` automatically.

---

**Write analysis.md** using `exporter.write_deck_analysis_md(analysis_text, short_id, deck_name, frontmatter)`:

The saved file MUST follow this exact structure. Section order is strict — do not reorder, rename, or omit any section.

**Frontmatter** (exactly these keys, no others):
```yaml
---
deck_name: "<name>"
cube_id: "<UUID from meta.json>"
cube_slug: "<slug from meta.json>"
colors: "<e.g. BR>"
format: "<40-card|60-card|commander-60|commander-100>"
built_at: "<ISO 8601 UTC e.g. 2026-05-24T20:05:35Z>"
mana_audit_status: "<PASS|WARN|FAIL>"
restrictions_status: "<PASS|FAIL>"
---
```

**Section structure** (use `##` for top-level, `###` for sub-sections):

1. `## MAINBOARD ({spells} spells + {lands} lands = {total})`
   - `### LANDS ({N})` — land list in a fenced code block
   - `### CREATURES ({N})` — card table in a fenced code block; omit if empty
   - `### INSTANTS & SORCERIES ({N})` — card table in a fenced code block; omit if empty
   - `### OTHER SPELLS ({N})` — card table in a fenced code block; omit if empty
2. `## SIDEBOARD ({N})` — card table in a fenced code block
3. `## ANALYSIS` — free Markdown body (NOT in a code block); at least one substantive observation
4. `## MANA AUDIT: {PASS|WARN|FAIL}` — audit report in a fenced code block
5. `## RESTRICTIONS COMPLIANCE` — checklist in a fenced code block

Card table columns in fenced code blocks: `CMC  Card  Qty  Color  Role  Rar` (mainboard); `Card  Qty  Color  Role / When to board in  Rar` (sideboard).

Non-basic card names in all fenced code block tables and in the `## ANALYSIS` body must be Scryfall search links: `[Card Name](https://scryfall.com/search?q=!"Card+Name")`. Basic lands are plain text.

The `frontmatter` dict passed to `exporter.write_deck_analysis_md()`:
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
  cubes/<id>/decks/<name>/deck.tsv
  cubes/<id>/decks/<name>/deck.mwDeck
  cubes/<id>/decks/<name>/analysis.md
```

---

## Tool Selection Table

| Task | Tool / File |
|------|-------------|
| Load card pool (with pool rules) | `cube_search.load_merged_pool(id, card_pool_rules=...)` — Phase 0 only |
| Filter by color/type/tag/CMC | `cube_search.search_pool(pool, color_identity=core_colors, splash_color_identity=splash_colors, ...)` |
| Query Payoff candidates | Filter working pool cache by `taxonomic_profile.structural_roles` containing `"Payload/Payoff"` |
| Query synergy support | Filter working pool cache by `taxonomic_profile.synergy_clusters` overlap + `"Enabler/Fodder"` or `"Engine/Outlet"` in `structural_roles` |
| Find commander candidates | `commander_finder.find_commanders(id, color_identity)` |
| Display commander table | `commander_finder.format_commanders_table(candidates)` |
| Run mana audit | `deck_audit.mana_audit(deck_cards, format, commander_cards, core_colors=core_colors, splash_colors=splash_colors)` |
| Display audit report | `deck_audit.format_audit_report(audit)` |
| Verify card exists | Search working pool cache by exact name — never training data |
| Read oracle text | `card.oracle_text` from working pool cache (main session) or grill bundle (Phase 9 agents) — never training data |
| Write deck files | Write tool → `cubes/<id>/decks/<name>/deck.json` and `deck.tsv`. `exporter.write_mwdeck()` → `deck.mwDeck`. `exporter.write_deck_analysis_md()` → `analysis.md` |
| Write a temp Python script | `_workspace/_tmp_<name>.py` — never to the repo root |

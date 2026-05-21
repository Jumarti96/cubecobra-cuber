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
cuber tag <id>      ← strongly recommended; tags drive Deck Identity analysis
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

## Phase 1: Interview

Use AskUserQuestion to collect all decisions before doing any analysis. Ask in a single multi-part message where possible.

**Required:**
1. **Cube** — short ID or slug (or list available cubes from `cubes/*/meta.json`)
2. **Format** — 40-card / 60-card / Commander-60 / Commander-100
3. **Colors** — which 1–3 colors; "surprise me" is valid (analyze pool first)
4. **Strategy / archetype** — aggro, control, midrange, combo, graveyard, tokens, etc.
5. **Power level** — casual / unpowered / powered / competitive

**Optional (ask but accept empty):**
6. **Restrictions** — budget, exclusions, max copies, locked-in cards, banned cards
7. **Sideboard size** — accept default for format or specify

Parse restrictions into a structured object:
```json
{
  "max_copies": 1,
  "locked_cards": ["Lightning Bolt"],
  "excluded_cards": ["Oko, Thief of Crowns"],
  "custom": "up to 2 rares total"
}
```
Thread restrictions through every subsequent phase.

---

## Phase 2: Deck Identity

Read `cubes/<id>/enriched.json` and `cubes/<id>/tagged.csv` using `cube_search.load_merged_pool(id)`.

Build the available pool: all cards where `board == "mainboard"` and color identity is a subset of the chosen colors.

**Tabulate tag density per color** (count of cards per functional tag, grouped by color):

```
Tag Density Report — {colors} pool ({N} cards)
────────────────────────────────────────────────
Tag              Count   Coverage
removal          14       18%
card-draw        9        12%
ramp             6         8%
threat           18       23%
counter          4         5%
graveyard        11       14%
...
```

**Classify archetypes:**
- **Strong** (≥ 10 cards with tag): fully supported archetype
- **Supported** (5–9 cards): playable but thin
- **Sparse** (< 5 cards): not viable as primary identity

**Propose a deck identity sentence** based on density analysis:
> "Black-Green graveyard midrange with strong threat density and supported removal."

Confirm with user before proceeding. If they redirect the strategy, re-tabulate for the new direction.

---

## Phase 3: Commander Selection (Commander formats only)

Skip this phase for 40-card and 60-card formats.

Run `commander_finder.find_commanders(id, color_identity=chosen_colors)`.

Display the formatted table using `commander_finder.format_commanders_table(candidates)`.

Ask the user to select:
- **1 commander** — any eligible card
- **2 partners** — both must have Partner / Friends forever / Doctor's companion / "Partner with" each other

On selection, derive the **binding color constraint**: the union of commanders' `color_identity`. All non-land cards must have color identity within this set.

---

## Phase 4: Deck Build

Use `cube_search.search_pool(pool, color_identity=..., ...)` to fill each slot category.

For each slot, read `oracle_text` from `enriched.json` before including any card. Do not rely on training-data knowledge of what the card does.

**Slot allocation guidelines:**

### 40-card draft
| Slot | Target | Notes |
|------|--------|-------|
| Lands | 17 | On-color basics + dual lands |
| Removal / interaction | 8–10 | Instants preferred |
| Threats / win conditions | 10–12 | Match curve to strategy |
| Engine / card advantage | 6–8 | Card draw, tutors |

### 60-card constructed
| Slot | Target | Notes |
|------|--------|-------|
| Lands | 20–24 | Adjust with ramp count |
| Removal / interaction | 10–12 | |
| Threats | 16–20 | |
| Engine | 8–12 | |

### Commander-60 / Commander-100
Scale slot allocations proportionally. Commander counts toward threats/engine, not the 60/100.

**Restrictions enforcement:** At every pick, verify the card does not violate the parsed restrictions object. Build a running compliance checklist.

**Verify before including any card:**
1. Card exists by name in enriched.json — hard check, no exceptions
2. Oracle text supports its assigned role — cite it explicitly
3. Color identity is within the chosen color constraint
4. Restrictions are not violated

---

## Phase 5: Mana Audit Gate

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

## Phase 6: Sideboard

Skip if the user opted out or if format does not normally use sideboards.

Default sizes: 8 (40-card), 15 (60-card), custom (commander).

Fill sideboard from the remaining cube pool (cards not already in the main deck):
- **Hate cards**: match likely opposing archetypes (graveyard hate, artifact removal, etc.) — cite oracle text for each
- **Flex slots**: cards that improve in certain matchups; explain what they answer

Challenger evaluates sideboard cohesion in Phase 8.

---

## Phase 7: Pre-Grill Check

Before the self-grill, perform hard verification:

1. **Cube membership**: every card in main deck + sideboard exists in `enriched.json` by exact name
2. **Oracle text coverage**: every card has a non-empty `oracle_text` in enriched.json
3. **Restrictions compliance**: full check against parsed restrictions object — produce checklist
4. **Mana audit**: confirm audit result is not FAIL (re-run if deck changed since Phase 5)

Remove any card failing check 1. Replace from the pool. Flag any oracle text gaps.

---

## Phase 8: Self-Grill (Hard Gate)

Spawn two parallel Agent calls. Neither agent sees the other's output during generation.

### Proposer Agent

Defend the full deck list (main + sideboard). For every card:
- State its role in the strategy
- Quote `oracle_text` from enriched.json: `Oracle: "..."`
- Confirm it fits the deck identity established in Phase 2
- Confirm it passes the restrictions check
- Confirm color identity is within constraint

### Challenger Agent

Attack the deck independently:
1. **Cube membership** — verify each card exists in enriched.json; flag any phantom inclusions (MUST be removed)
2. **Oracle text** — read oracle text independently; does it actually do what Proposer claims?
3. **Restrictions** — check every card against restrictions object; flag violations
4. **Identity fit** — does each card contribute to the stated deck identity? Suggest cuts that don't
5. **Better alternatives** — is there a card in the cube pool that fills the slot more efficiently? Check enriched.json tags and oracle text
6. **Sideboard cohesion** — does the sideboard address realistic weaknesses? Are slots wasted?
7. **Mana audit re-run** — independently run mana_audit on the list; report discrepancies

### Resolve Grill

- Proposer revises challenged slots using only cards from enriched.json
- Challenger confirms each revision
- Any card without confirmed cube membership must be removed
- Final list must satisfy: all cards in cube + oracle text supports all roles + audit ≥ WARN

---

## Phase 9: Present Final Deck

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
  ✓ Rares used: {list} ({N} of {max} allowed)
  ✓ Mythic used: {list} ({N} of {max} allowed)
  ✓ All commons/uncommons ≤ {N} copies
  ✓ Sideboard = {N} cards
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

## Phase 10: Save

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

The `analysis_text` is the full Phase 9 output reformatted as Markdown:
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
| Load card pool | `cube_search.load_merged_pool(id)` |
| Filter by color/type/tag/CMC | `cube_search.search_pool(pool, ...)` |
| Find commander candidates | `commander_finder.find_commanders(id, color_identity)` |
| Display commander table | `commander_finder.format_commanders_table(candidates)` |
| Run mana audit | `deck_audit.mana_audit(deck_cards, format, commander_cards)` |
| Display audit report | `deck_audit.format_audit_report(audit)` |
| Verify card exists | Search `enriched.json` cards[] by exact name |
| Read oracle text | `card.oracle_text` from enriched.json — never training data |
| Tag density analysis | `tagged.csv` tags column, grouped by color_identity |
| Write deck files | Write tool → `cubes/<id>/decks/<name>/deck.json` and `deck.csv`. `exporter.write_mwdeck()` → `deck.mwDeck`. `exporter.write_deck_analysis_md()` → `analysis.md` |

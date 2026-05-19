## Design Decisions

### D1 — Folder Naming: Title Slug, Not Short ID

Cube folders are named `{slugify(cube.name)}/` (e.g., `my-power-cube/`). The short-id lives in `meta.json` and is used for all CLI routing and CubeCobra API calls. Reasoning: title-based folders are human-navigable; short-ids (`p4ul8fmm`) are opaque. If two cubes slug-collide, append the short-id: `my-cube-p4ul8fmm/`.

### D2 — Remote/Working Separation

```
cubes/{slug}/
  remote/              ← pristine CubeCobra snapshot (never edit)
    cube.json          ← full cubeJSON at last fetch
    mainboard.csv      ← CubeCobra's CSV at last fetch
  meta.json            ← title, short-id, format, owner, fetched_at
  primer.md            ← extracted from cube.json.description, editable
  mainboard.csv        ← working copy (edit this: add/remove/reorder)
  maybeboard.csv       ← working copy
  enriched.json        ← Scryfall-enriched (auto-generated; regen with `enrich`)
  tagged.csv           ← functional tags (your work product)
  analysis.json        ← statistics (auto-generated with `stats`)
  decks/
    {name}.json        ← deck JSON
    {name}.csv         ← deck CSV (new in v2)
  exports/
    import-ready.csv   ← assembled by `cuber export`, upload this to CubeCobra
```

`remote/` is analogous to the git index of the upstream state. `cuber status` diffs working vs. remote. `cuber fetch` (re-fetch) overwrites `remote/` but does NOT overwrite the working `mainboard.csv` — it merges (new cards added, but local edits preserved), with a conflict report if a card appears in remote but was locally removed.

### D3 — CubeCobra CSV Is Already Enriched

The CubeCobra CSV download includes: Name, CMC, Type, Color, Set, Collector Number, Rarity, Color Category, Status, Finish, Image URLs, Tags, Notes. This means `remote/mainboard.csv` already has rarity, type, and color — fields previously requiring Scryfall enrichment.

`cuber enrich` now focuses on fields CubeCobra doesn't provide: `oracle_text`, `color_identity` (as a list, not a string), `mana_cost` (for pip analysis), `card_faces` (for DFCs). The Scryfall cache remains the source for these.

For the `add-card` workflow: a stub row contains only `name`. On next `enrich`, stub rows are detected (by empty `oracle_text`) and hydrated from Scryfall. CubeCobra fields (rarity, set, etc.) are populated from Scryfall too, since no CubeCobra data exists for the newly-added card until it's re-exported and imported.

### D4 — add-card Input Modes

```
# Single card
cuber add-card <id> "Lightning Bolt"

# Multiple positional args
cuber add-card <id> "Lightning Bolt" "Brainstorm" "Swords to Plowshares"

# Newline-separated string (shell heredoc or quoted)
cuber add-card <id> "$(printf 'Lightning Bolt\nBrainstorm\nSwords to Plowshares')"

# From a text file (one card name per line)
cuber add-card <id> --from-file cards.txt

# Stdin (pipe-friendly)
echo -e "Lightning Bolt\nBrainstorm" | cuber add-card <id> --stdin

# Send to maybeboard instead of mainboard
cuber add-card <id> "Teferi, Hero of Dominaria" --maybeboard
```

All input modes normalize card names (strip whitespace, collapse internal spaces). Duplicates within the batch are deduplicated. Cards already in `mainboard.csv` emit a warning and are skipped (unless `--force`).

### D5 — Merged Card Lookup for Deck Building

The deck builder constructs a unified card lookup before any deck logic runs:

```python
# Conceptual merge (implemented in cube_search.py)
cards = load_enriched(short_id)          # oracle_text, color_identity, cmc, type_line
tags_by_name = load_tags(short_id)       # {name: [tag1, tag2, ...]} from tagged.csv
for card in cards:
    card['functional_tags'] = tags_by_name.get(card['name'], [])
```

Tags are a semantic index for fast slot filtering ("all RG cards tagged `ramp`"). Oracle text is the ground truth cited in every justification. The Iron Rule applies to oracle text, not tags — tags are a convenience layer, not authoritative.

### D6 — Deck Identity Phase

After the interview, before building:

1. Read `enriched.json` + `tagged.csv` for the chosen colors.
2. Count cards per functional tag within those colors. Build an archetype density table.
3. Apply a threshold: archetypes with ≥ 6 cards in the chosen colors are "Strong"; 3–5 are "Supported"; < 3 are "Sparse."
4. Propose a deck identity sentence: "BG Graveyard Midrange — recursion as the primary engine, sacrifice as secondary value."
5. User confirms, redirects, or overrides.

The confirmed identity is passed as a structured parameter to every subsequent phase. The Challenger agent cites identity mismatches explicitly: "Gravedigger supports the graveyard identity; Wurmcoil Engine does not."

### D7 — Mana Audit Formulas

Commander formats (60+1, 60+2, 100-card):
- **Burgess formula**: `recommended_lands = round((31 + color_count + commander_cmc) * deck_size / 100)`
- **Karsten adjustment**: `karsten = round(max(36, 42 - floor(ramp_count / 2.5)) * deck_size / 100)`
- `recommended = max(burgess, karsten)`
- Status: FAIL if actual < burgess; WARN if actual < recommended; PASS otherwise.

Constructed formats (40-card, 60-card):
- **Baseline**: 24 lands for 60-card, scaled proportionally for 40-card (16).
- **Ramp adjustment**: −1 land per 2 ramp spells.
- **Curve adjustment**: ±1–2 based on average CMC vs. 3.0 neutral.
- Clamped to [14, 18] for 40-card; [20, 27] for 60-card.

**Color balance**: pip demand (count colored pips in mana costs) vs. land color production (count lands that produce each color). If a color has > 10pp gap between pip demand% and production%, flag as WARN; > 15pp gap is FAIL.

### D8 — Commander Detection

`commander_finder.py` searches `enriched.json` for eligible commanders. Detection logic (adapted from dan-blanchard):

```
Eligible if:
  type_line contains "Legendary Creature"
  OR type_line contains "Legendary" AND oracle_text matches "can be your commander"
  OR type_line contains "Legendary Planeswalker" AND oracle_text matches "can be your commander"

Partner flags (detect in oracle_text):
  is_partner: "Partner" standalone keyword, "Friends forever", "Doctor's companion"
  partner_with: "Partner with X" → extract X
  has_background: "Choose a Background"
```

Commander identity determines the deck's color constraint for all subsequent card picks.

### D9 — Restrictions System

Restrictions are parsed in Phase 1 into a structured object:

```json
{
  "deck_size": 40,
  "max_copies": {
    "common": 2,
    "uncommon": 2,
    "rare": 1,
    "mythic": 1
  },
  "locked_cards": ["Thoughtseize"],
  "excluded_cards": ["Black Lotus"],
  "custom_notes": "No infinite combos"
}
```

This object is:
- Passed explicitly to the Proposer and Challenger agents.
- Checked mechanically in the Pre-Grill Legality phase (before self-grill).
- Displayed as a compliance checklist in the final deck output.

The interview normalizes natural language restrictions: "up to 2 copies of commons or uncommons" → `max_copies.common = 2, max_copies.uncommon = 2`.

### D10 — Sideboard Interview

Sideboard size is asked during the interview:
- 40-card: default 8 (offer 0, 8, custom)
- 60-card: default 15 (offer 0, 15, custom)
- Commander: default none (offer 10, custom, none)
- Custom: user enters a number; skill notes reduced reliability vs. standard sizes.

The Challenger agent evaluates sideboard cohesion: "Are these cards realistic sideboard answers for the expected field, given the cube's archetypes?"

### D11 — No Push API

CubeCobra's public API (confirmed from source inspection of their JS bundle) has **no write endpoints**. All cube updates must go through the CubeCobra UI. `cuber export` assembles `exports/import-ready.csv` in the exact 19-column CubeCobra format. The user uploads this via: cube page → List tab → Export → Replace with CSV Import. This is documented in the README and printed by `cuber export`.

### D12 — deck.csv Schema

```
Name,Quantity,Board,Role,Rarity,Color Identity,CMC,Tags,Oracle Text Excerpt
Lightning Bolt,1,mainboard,Removal,Common,R,1,removal,"Lightning Bolt deals 3 damage to any target."
...
```

`Board` is `mainboard` or `sideboard`. `Role` is the slot assignment from the deck builder. `Oracle Text Excerpt` is truncated to 120 chars. This format is easily readable in Excel/Sheets and is the input for the future dashboard's deck viewer.

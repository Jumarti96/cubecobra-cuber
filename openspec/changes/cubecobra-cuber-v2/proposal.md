## Why

v1 of Cubecobra Cuber treats a cube as a collection of files to process. v2 treats it as a **project** with a lifecycle: pull from CubeCobra, edit locally, push back. The deck builder is upgraded from a simple 40-card drafter into a full format-aware construction tool that reasons about deck identity, validates mana bases with established formulas, and enforces user-defined restrictions.

Two gaps drove this:

1. **Cube management is one-way.** v1 fetches a thin CSV and meta.json, but offers no clear path for making local changes and propagating them back. There's no concept of "what's changed since I last pulled from CubeCobra," and adding a single card requires manual CSV editing.

2. **The deck builder doesn't know what it's building.** It produces a 40-card list without understanding deck identity, can't validate the mana base quantitatively, ignores card rarity when applying restrictions, and can't find valid commanders for a Commander cube. dan-blanchard's deck-wizard has years of refinement on these problems; v2 adapts its best ideas into our cube-constrained context.

## What Changes

### Section 1 — Cube Management

- **New**: `cuber fetch` now fetches the full `cubeJSON` from CubeCobra (richest endpoint: mainboard/maybeboard split, per-card Scryfall IDs, designer tags, description). Falls back to CSV if JSON fails.
- **New**: Cube folder named `{title-slug}/` instead of `{short-id}/`. `meta.json` carries the short-id for routing.
- **New**: Folder split — `remote/` subfolder holds pristine CubeCobra snapshot (never edit); working files live at root of the cube folder.
- **New**: `cuber add-card` command — adds one or more cards to `mainboard.csv` (or `maybeboard.csv` with `--maybeboard`). Accepts CLI args, newline list, or text file.
- **New**: `cuber status` command — diffs local `mainboard.csv` against `remote/mainboard.csv`. Shows added, removed, tag-changed cards.
- **New**: `primer.md` — cube description extracted from cubeJSON, stored as Markdown, editable locally.
- **Changed**: `cuber export` assembles `exports/import-ready.csv` from meta + mainboard.csv + tags. This file is what the user uploads to CubeCobra's "Replace with CSV" importer.
- **Changed**: `cuber enrich` handles partial rows (card name only); fills all other fields from Scryfall.
- **New**: `cuber/cube_manager.py` — module housing fetch-and-disassemble, add-cards, status-diff, and export-assemble logic.

### Section 2 — Deck Builder (enhanced skill)

- **Changed**: `/build-deck` now supports four formats: 40-card draft, 60-card constructed, Commander (60+1/2), and 100-card Commander.
- **New**: Deck Identity Phase — analyzes tag density for chosen colors, identifies supported archetypes, confirms deck identity with user before building. Every subsequent pick is evaluated against the confirmed identity.
- **New**: Restrictions system — parsed in Phase 1 into a structured object (`max_copies_by_rarity`, `locked_cards`, `excluded_cards`). Enforced at every phase. Compliance checklist shown in final output.
- **New**: Commander detection — `cuber/commander_finder.py` searches `enriched.json` for commander-eligible cards. Handles partner, "Partner with X", "Friends forever", "Doctor's companion", and "Choose a Background" via regex (adapted from dan-blanchard).
- **New**: Mana audit — `cuber/deck_audit.py` implements Burgess formula (Commander) and constructed land target formula (40/60). Validates color balance via pip demand vs. land production. Grade: PASS / WARN / FAIL.
- **New**: Cube search — `cuber/cube_search.py` filters `enriched.json` by oracle regex, type line, CMC range, color identity, functional tag, and rarity. Used during deck building to populate slots.
- **Changed**: Card lookup merges `enriched.json` (oracle text, color identity, CMC) with `tagged.csv` (functional tags). Tags act as a semantic index for fast filtering; oracle text remains the ground truth cited in justifications.
- **New**: Sideboard — format-aware defaults (8 cards for 40-card, 15 for 60-card, optional/custom for Commander). Interview allows custom size.
- **New**: Deck output includes `deck.csv` alongside `deck.json` — human-readable in any spreadsheet viewer.
- **Changed**: Self-grill challenger now explicitly cites deck identity, restrictions compliance, and mana audit result — not just oracle text.

### Section 3 — Documentation

- **Changed**: `README.md` updated for all v2 commands and skills.
- **New**: `.context-for-design-ai.md` — comprehensive project context file for the future dashboard design AI. Covers all data schemas, file structures, commands, skills, and dashboard feature suggestions.

## Capabilities

### New Capabilities

- `cube-fetch-v2`: Fetch cubeJSON and disassemble into project folder (meta, primer, remote snapshot, working copies)
- `cube-lifecycle`: Local edits with clear remote/working separation; status diff; export assembly
- `add-card`: Multi-input card addition (CLI args, newline list, text file) with mainboard/maybeboard routing
- `cube-status`: Diff local working files against remote snapshot
- `deck-builder-v2`: Format-aware deck building (40/60/Commander/100), deck identity phase, restrictions, mana audit, sideboard, CSV output
- `deck-audit`: Burgess + Karsten mana audit for Commander; constructed land formula for 40/60; color balance grading
- `commander-finder`: Identify valid commanders from enriched.json cube pool with partner detection
- `cube-search`: Oracle/tag/CMC/color/rarity filter within the cube's card pool

### Modified Capabilities

- `cubecobra-client`: Now fetches cubeJSON as primary (not CSV); falls back to CSV; writes to title-slug folder
- `cube-data-model`: Extended to support partial card rows (add-card workflow); deck.csv schema added
- `cli-commands`: `fetch`, `enrich`, `export` redesigned; `add-card`, `status` added
- `skill-build-deck`: Full rewrite — 7 phases, format-aware, deck identity, commander support, mana audit, restrictions, sideboard, CSV output

## Impact

- **Dependencies**: No new dependencies. `cuber/cube_manager.py`, `cuber/deck_audit.py`, `cuber/commander_finder.py`, `cuber/cube_search.py` are new modules using only stdlib + existing dependencies.
- **Breaking changes**: Cube folder structure changes (`{short-id}/` → `{title-slug}/`). Existing `cubes/` folders from v1 are not auto-migrated; user runs `cuber fetch` again to re-fetch under v2 structure.
- **External APIs**: Same CubeCobra endpoints. CubeCobra has no write/push API — all cube updates go through the "Replace with CSV" manual import. This was confirmed by inspecting the complete API documentation.
- **No auth required**: All CubeCobra API calls remain unauthenticated (read-only public endpoints).

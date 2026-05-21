# cube-editor-v2-enricher-overhaul — Enricher Overhaul

## Why

`cuber enrich` currently re-fetches every card by name every run, ignoring any set code or collector number present in `mainboard.csv`. This causes two problems: (1) set-fetched cubes lose their intended printings because Scryfall returns the canonical printing by name rather than the set-specific one; (2) re-enriching an already-enriched cube re-fetches all cards unnecessarily, even those that haven't changed. Both problems make the enricher less useful and more error-prone.

## What Changes

- **Add** set-pinning to enrichment: when a mainboard row has `Set` + `Collector Number`, fetch by `{set, collector_number}` identifier instead of `{name}`, preserving the intended printing
- **Add** partial set-pinning: when a row has `Set` but no `Collector Number`, fetch by `{name, set}` to constrain to the correct set without requiring an exact collector number
- **Add** skip-if-enriched logic: cards already present in `enriched.json` with a matching `scryfall_id` are skipped unless `--refresh` is specified or their set/CN in mainboard.csv has changed
- **Add** `cuber search` CLI command: expose the existing `search_pool()` / `format_search_results()` functions in `cube_search.py` as a CLI command

## Capabilities

### New Capabilities

- `enricher-set-pinning`: Fetch logic that respects `Set` and `Collector Number` columns in `mainboard.csv` when determining which Scryfall identifier to use per card.
- `enricher-skip-if-enriched`: Incremental enrichment — skip cards that are already fully enriched and whose set/CN hasn't changed. Respect `--refresh` flag to force full re-enrich.
- `cube-search-command`: CLI command exposing the existing `cube_search.py` search logic so users can query their local cube by color, type, CMC, oracle text, tags, and rarity.

### Modified Capabilities

<!-- No existing spec-level requirements are changing -->

## Impact

- `cuber/scryfall.py`: `enrich_cube()`, `lookup_cards()`, `_backfill_mainboard_csv()` — identifier strategy changes; add set-pinning batch logic
- `cuber/cli.py`: new `search` command
- `cuber/cube_search.py`: no logic changes; `search_pool()` and `format_search_results()` are already correct
- `cuber/cube.py`: no changes
- `enriched.json`: no schema changes; content more stable (set codes preserved)
- `mainboard.csv`: no changes; `Set` and `Collector Number` columns now consulted during enrichment

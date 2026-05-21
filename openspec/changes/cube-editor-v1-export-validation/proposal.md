# cube-editor-v1-export-validation — Export & Add-Card Overhaul

## Why

The current export pipeline blocks on duplicate cards (wrong for intentional multiples), never verifies card names against Scryfall unless the user separately runs `enrich`, and produces minimal log entries. Meanwhile, `add-card` accepts any string without checking whether the card exists, so typos and wrong names go undetected until much later. These gaps make the cube editing workflow error-prone and the export log too thin to be useful.

## What Changes

- **Remove** the duplicate-card error from `_validate_mainboard()` — intentional duplicates are valid; `cuber dedup` handles enforcement when wanted
- **Add** Scryfall validation at export time: cards with a `scryfall_id` in `enriched.json` are pre-verified; unverified cards are checked live; cards not found on Scryfall block export
- **Add** `--skip-scryfall` flag to `cuber export` for offline use
- **Expand** `exports/export-log.json` entries with: `export_number`, `cube_title`, `enrichment_coverage`, `missing_from_scryfall`, `validation_summary`, `rarity_delta`
- **Add** Scryfall name verification to `cuber add-card` (default ON): normalizes to canonical name, warns on fuzzy match, rejects unknown names; `--no-verify` escapes
- **Add** `cuber swap <id> <old> <new>` command: atomic remove + verified add; aborts if new card not found

## Capabilities

### New Capabilities

- `export-validation`: Validates mainboard card existence against Scryfall at export time, with smart short-circuit via `enriched.json`. Produces a richer export log entry per run.
- `add-card-verification`: Verifies card names against Scryfall at add time using fuzzy lookup; normalizes to canonical Scryfall names before writing to mainboard.csv.
- `swap-card`: Atomic card replacement command — removes one card and adds another in a single operation with verification.

### Modified Capabilities

<!-- No existing spec-level requirements are changing — these are all new behaviors -->

## Impact

- `cuber/cube_manager.py`: `_validate_mainboard()`, `assemble_export()`, `add_cards()`
- `cuber/cli.py`: `add_card()` command, new `swap` command
- `cuber/scryfall.py`: `_fuzzy_lookup()` promoted from private to module-level (renamed `fuzzy_lookup`)
- `exports/export-log.json`: schema expanded (new fields added, backward-compatible)
- No breaking changes to CLI interface; new flags and commands only

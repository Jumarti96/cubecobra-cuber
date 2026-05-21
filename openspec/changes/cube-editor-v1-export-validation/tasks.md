# Tasks — cube-editor-v1-export-validation

## 1. Scryfall fuzzy_lookup — promote to public

- [x] 1.1 Rename `_fuzzy_lookup` → `fuzzy_lookup` in `cuber/scryfall.py` and update all internal callers
- [x] 1.2 Add `fuzzy_lookup` to `cuber/__init__.py` exports so it is importable from other modules

## 2. Export validation — remove duplicate error, add Scryfall check

- [x] 2.1 Remove the duplicate-card error from `_validate_mainboard()` in `cuber/cube_manager.py`
- [x] 2.2 Add `_load_enriched_index()` helper: load `enriched.json` and return a `{name_lower: scryfall_id}` dict; return empty dict if file missing
- [x] 2.3 Add `_verify_cards_scryfall()`: accepts a list of unverified card names, calls `fuzzy_lookup()` for each, collects failures; respects rate delay between calls
- [x] 2.4 Wire both helpers into `assemble_export()`: cross-check mainboard names against enriched index, call `_verify_cards_scryfall()` for the remainder, block export if any failures
- [x] 2.5 Add `--skip-scryfall` flag to the `export` command in `cuber/cli.py`; pass it through to `assemble_export()`

## 3. Richer export log

- [x] 3.1 Add `_compute_enrichment_coverage()`: count mainboard names present in enriched index; return `"N/M"` string
- [x] 3.2 Add `_compute_rarity_delta()`: compare added/removed card names (from `cube_status` diff) to rarity data in mainboard.csv; return per-rarity added/removed counts
- [x] 3.3 Update the log entry dict in `assemble_export()` to include: `export_number`, `cube_title`, `enrichment_coverage`, `missing_from_scryfall`, `validation_summary`, `rarity_delta`
- [x] 3.4 Compute `export_number` by reading existing log length + 1 before inserting

## 4. Verify-on-add

- [x] 4.1 Update `add_cards()` in `cuber/cube_manager.py` to accept a `verify: bool = True` parameter
- [x] 4.2 When `verify=True`: call `fuzzy_lookup()` per name; on exact match use canonical name; on fuzzy match use canonical name and collect a correction notice; on not-found skip the card and collect an error; on network failure add the card and collect an unverified warning
- [x] 4.3 Update return dict from `add_cards()` to include: `corrections` (list of `{input, canonical}` dicts), `not_found` (list of attempted names), `unverified` (list of names added without confirmation)
- [x] 4.4 Add `--no-verify` flag to `add_card` command in `cuber/cli.py`; pass `verify=False` to `add_cards()`
- [x] 4.5 Update CLI output in `add_card()` to print correction notices, not-found errors, and unverified warnings

## 5. cuber swap command

- [x] 5.1 Add `swap_card()` function in `cuber/cube_manager.py`: verify new card with `fuzzy_lookup()` first; if not found return error without any mutation; else remove old card (error if not found), add new card with canonical name
- [x] 5.2 Add `swap` command to `cuber/cli.py` with args: `id_or_slug`, `old_name`, `new_name`; optional `--maybeboard` flag
- [x] 5.3 CLI output: show removed card, added card (with canonical correction if applicable), or clear error if old card not found or new card not verified

## 6. Documentation & alignment

- [x] 6.1 Update `README.md`: document `--skip-scryfall` flag for `export`, `--no-verify` flag for `add-card`, new `swap` command with usage example
- [x] 6.2 Update `.context-for-design-ai.md`: document the richer `export-log.json` schema (all new fields) so the dashboard/app AI knows the full log structure; update `meta.json` and `enriched.json` notes if any fields changed
- [x] 6.3 Verify no skill files (`skills/build-deck.md`, `.claude/skills/`) reference export or add-card behavior that needs updating

# Tasks — cube-editor-v2-enricher-overhaul

## 1. Identifier strategy — set-pinning in lookup_cards()

- [x] 1.1 Refactor `lookup_cards()` in `cuber/scryfall.py` to accept a list of identifier dicts (`List[Dict]`) instead of a list of names; each dict is `{"name": ...}`, `{"set": ..., "collector_number": ...}`, or `{"name": ..., "set": ...}`
- [x] 1.2 Update the cache key logic: for set+CN identifiers, use `f"{set}:{cn}"` as the cache key; for name identifiers, use the normalized name as before
- [x] 1.3 Update the `not_found` fallback: when a set+CN identifier is not found, fall back to fuzzy lookup by name (log a warning that the pinned printing was unavailable)

## 2. Enricher — build identifiers from mainboard.csv

- [x] 2.1 Add `_build_identifier(row: Dict[str, str]) -> Dict[str, str]` in `cuber/scryfall.py`: implements the three-tier logic (set+CN → name+set → name)
- [x] 2.2 Update `enrich_cube()` to call `_build_identifier()` for each mainboard row instead of using raw names; pass identifier dicts to `lookup_cards()`
- [x] 2.3 Verify the identifier→card mapping is preserved correctly when matching Scryfall responses back to mainboard rows (the response `name` field is the join key)

## 3. Skip-if-enriched logic

- [x] 3.1 Add `_load_enriched_dict(short_id: str) -> Dict[str, Card]` that loads `enriched.json` and returns a `{name_lower: Card}` dict; returns empty dict if file missing
- [x] 3.2 Add `_is_already_enriched(row: Dict, existing: Dict[str, Card]) -> bool`: checks scryfall_id present, set matches (if row has Set), CN matches (if row has CN)
- [x] 3.3 In `enrich_cube()`, load the existing enriched dict and partition mainboard rows into `to_fetch` and `already_enriched`; initialize the output card list with the already-enriched cards
- [x] 3.4 Ensure `--refresh` flag bypasses `_is_already_enriched` (passes all cards to `to_fetch`)
- [x] 3.5 Update CLI output to print skip count and fetch count separately

## 4. Backfill — protect user-specified Set column

- [x] 4.1 In `_backfill_mainboard_csv()`, add a check: only write the `Set` column if the existing row has an empty `Set` value; always write `CMC`, `Type`, `Color`, `Rarity`, `Collector Number`, `image URL`, `image Back URL`

## 5. cuber search command

- [x] 5.1 Add `search` command to `cuber/cli.py` with flags: `--color`, `--type`, `--cmc-min`, `--cmc-max`, `--oracle`, `--tag`, `--rarity`, `--limit` (default 25)
- [x] 5.2 In the command handler: call `load_merged_pool()`, then `search_pool()` with the provided filters, then `format_search_results()` with the limit; print the result
- [x] 5.3 Handle missing `enriched.json` with a clear error message and `raise typer.Exit(1)`

## 6. Documentation & alignment

- [x] 6.1 Update `README.md`: document the new set-pinning behavior of `cuber enrich`, the skip-if-enriched behavior, and the new `cuber search` command with all flags
- [x] 6.2 Update `.context-for-design-ai.md`: note that `enriched.json` now reliably reflects the user's intended printing (set code stable after enrich); document `cuber search` command surface for any search UI the dashboard might expose
- [x] 6.3 Verify no skill files reference enrichment behavior that needs updating

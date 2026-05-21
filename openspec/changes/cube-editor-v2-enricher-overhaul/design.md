# Design — cube-editor-v2-enricher-overhaul

## Context

`enrich_cube()` in `scryfall.py` currently:
1. Loads all card names from `mainboard.csv`
2. Passes them all to `lookup_cards()` as `{"name": "..."}` identifiers
3. Overwrites `enriched.json` from scratch with the results
4. Calls `_backfill_mainboard_csv()` to write Scryfall fields back into mainboard

The Scryfall `/cards/collection` endpoint accepts mixed identifier types in one batch: `{"name": "..."}`, `{"set": "...", "collector_number": "..."}`, or `{"name": "...", "set": "..."}`. All three can be present in the same batch POST.

The key invariant to maintain: `mainboard.csv` is the source of truth for which cards are in the cube and what printing the user wants. `enriched.json` is a derived cache of Scryfall metadata. When they conflict, `mainboard.csv` wins.

## Goals / Non-Goals

**Goals:**
- Preserve set codes and collector numbers from `mainboard.csv` through the enrichment process
- Skip re-fetching cards that are already correctly enriched
- Detect set/CN changes in `mainboard.csv` and re-fetch affected cards automatically
- Expose `cuber search` as a first-class CLI command

**Non-Goals:**
- Auto-creating `enriched.json` at fetch time (fetch and enrich remain separate steps)
- Changing the `Card` dataclass or `enriched.json` schema
- Changing any behavior of `cuber export` (that is MR1)

## Decisions

### D1: Identifier strategy — three tiers per card

**Decision:** For each row in `mainboard.csv`, choose the Scryfall identifier as follows:
- Has `Set` + `Collector Number` (both non-empty) → `{"set": set.lower(), "collector_number": cn}`
- Has `Set` only → `{"name": name, "set": set.lower()}`
- Has neither → `{"name": name}`

All identifiers for a batch are mixed together in the same `/cards/collection` POST. Scryfall handles all three types in one request.

**Rationale:** This exactly matches the user's stated rule: "when there's a card name and a set code, only the rest is enriched respecting the set code; when only the name is available, enriches whatever it finds." The three-tier strategy maps directly.

**Alternative considered:** Only support set+CN (full pin), require both columns. Rejected: too strict. Many cubes have set codes but no collector numbers; they should still benefit from set-scoped lookup.

### D2: Skip-if-enriched — check scryfall_id + set match

**Decision:** Before building the identifier batch, load `enriched.json` into a dict keyed by name. A card is "already enriched" if:
1. Its name exists in the enriched dict
2. The enriched entry has a non-empty `scryfall_id`
3. If `mainboard.csv` row has a `Set` value: enriched `set_code` matches `mainboard.csv[Set].lower()`
4. If `mainboard.csv` row has a `Collector Number`: enriched `collector_number` matches

If all conditions hold → skip this card (keep existing enriched data). Any condition fails → re-fetch.

**Rationale:** Covers the "user changed the printing" scenario cleanly. The comparison is O(1) per card (dict lookup + string compare). `--refresh` bypasses all skips.

**Alternative considered:** Track a `enriched_at` timestamp and skip if recent. Rejected: time-based skipping ignores user intent changes. The content-based comparison is strictly more correct.

### D3: cuber search — thin CLI wrapper, no new logic

**Decision:** Add a `search` command to `cli.py` that calls `load_merged_pool()` and `search_pool()` from `cube_search.py` and formats output with `format_search_results()`. No changes to `cube_search.py`.

**Rationale:** The logic is complete and correct. This is a pure surface-area addition.

**Flags:**
- `--color W,U,B` — color identity filter (subset match)
- `--type creature` — substring match on type_line
- `--cmc-min N` / `--cmc-max N` — CMC range
- `--oracle "draw a card"` — regex on oracle text
- `--tag removal` — tag filter (all listed tags must match)
- `--rarity rare` — exact rarity match
- `--limit N` — result count (default 25)

### D4: _backfill_mainboard_csv — no longer overwrites Set from Scryfall

**Decision:** `_backfill_mainboard_csv()` SHALL NOT overwrite the `Set` column if the mainboard row already has a non-empty `Set` value. It still writes `image URL`, `Type`, `CMC`, `Rarity`, `Color`, `Collector Number` (from the Scryfall response for the pinned printing).

**Rationale:** The backfill was the direct cause of set codes being overwritten after `fetch_set`. Since we're now fetching the correct printing by set+CN, the Scryfall response will match the intended set — but as a belt-and-suspenders measure, we don't overwrite a user-specified set.

## Risks / Trade-offs

**[Risk] Scryfall `{name, set}` lookup returns a different card than expected** → Mitigation: if the set has no card by that name, Scryfall returns it in `not_found`; the fallback fuzzy lookup handles it gracefully (same behavior as today).

**[Risk] Set code in mainboard.csv is an alias (e.g., "con" vs "CON")** → Mitigation: always `.lower()` both sides before comparing. Already done in `_backfill_mainboard_csv`.

**[Risk] Large cubes with many new cards take longer on first enrich** → This is unchanged from today. Subsequent enriches are faster due to skipping.

## Migration Plan

No data migration. Existing `enriched.json` files remain valid. On next `cuber enrich` run, cards will be re-verified according to the new skip logic; any whose set/CN doesn't match will be re-fetched.

## Open Questions

None.

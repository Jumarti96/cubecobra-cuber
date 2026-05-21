# Design — cube-editor-v1-export-validation

## Context

The cube pipeline has three verification touchpoints:
1. `add-card` — currently writes any string as a stub, no validation
2. `enrich` — calls Scryfall, flags missing cards in `meta.json["missing_cards"]`
3. `export` — currently validates only for unenriched stubs and duplicates

The intent is to make verification happen earlier (at add time) and more reliably (at export time regardless of whether `enrich` has run). The `enriched.json` file serves as a verification cache — if a card is there with a `scryfall_id`, no network call is needed at export.

`_fuzzy_lookup()` already exists in `scryfall.py` and handles name normalization + typo correction via the Scryfall `/cards/named?fuzzy=` endpoint. It just needs to be promoted from private to public use.

## Goals / Non-Goals

**Goals:**
- Catch wrong card names at the earliest possible point (add time)
- Guarantee that every exported card exists on Scryfall, without mandating `enrich`
- Make the export log a meaningful audit trail (rarity deltas, coverage, missing names)
- Allow intentional duplicate cards without triggering errors
- Keep the pipeline non-blocking for offline/air-gapped use via `--skip-scryfall`

**Non-Goals:**
- Changing enrichment behavior (that is MR2)
- Verifying set codes or collector numbers at export time (enrichment concern)
- Migrating existing export logs to the new schema

## Decisions

### D1: Verification order at export — enriched.json first, then live

**Decision:** At export, iterate mainboard cards. For each card, check `enriched.json` by name for a non-empty `scryfall_id`. If found: verified, no network call. If not found: call `fuzzy_lookup()` live.

**Rationale:** Avoids re-hitting Scryfall for an entire enriched cube on every export. An un-enriched cube (common after `fetch-set`) still gets validated. The `enriched.json` check is an O(1) dict lookup — essentially free.

**Alternative considered:** Always call Scryfall at export regardless of enriched state. Rejected: too slow for large cubes, and pointlessly duplicates work already done by `enrich`.

### D2: fuzzy_lookup promoted to public, used in both add and export

**Decision:** Rename `_fuzzy_lookup` → `fuzzy_lookup` in `scryfall.py`. Both `add_cards()` and the export validation path use it.

**Rationale:** The function already does exactly what both callsites need — fuzzy name resolution with normalization. No new logic, just visibility change.

**Alternative considered:** Separate "strict" lookup for export vs. "fuzzy" for add. Rejected: the fuzzy lookup is strict enough — if Scryfall can't match it, it doesn't exist. Separate paths add complexity with no benefit.

### D3: add-card verification — default ON, non-blocking on network failure

**Decision:** `add_cards()` calls `fuzzy_lookup()` per card by default. On network failure, the card is added with a `(unverified)` warning. On lookup failure (card not found), the card is rejected with a clear error. `--no-verify` flag skips all lookups.

**Rationale:** Default ON gives immediate feedback for the common case (interactive use). Non-blocking on failure means a dropped network connection doesn't interrupt a bulk import session. `--no-verify` handles bulk file imports where names are known good.

**Alternative considered:** Default OFF, user opts in. Rejected: wrong names would silently persist to mainboard.csv until export, making the feedback loop longer and the error more confusing.

### D4: swap command — abort-on-failure before any mutation

**Decision:** `cuber swap` verifies the new card with `fuzzy_lookup()` BEFORE removing the old card. If verification fails, abort with no changes made.

**Rationale:** Atomicity. The user should never end up with a removed card and no replacement. Verify-then-mutate is the safe order.

### D5: Export log — new fields are additive, no migration

**Decision:** New log fields (`export_number`, `cube_title`, `enrichment_coverage`, `missing_from_scryfall`, `validation_summary`, `rarity_delta`) are appended to new log entries. Existing entries remain as-is.

**Rationale:** The log is an append-only audit trail. Old entries don't need new fields — they represent historical state. Any reader should treat missing fields as unknown, not as zero.

## Risks / Trade-offs

**[Risk] `fuzzy_lookup` adds latency to `add-card`** → Mitigation: one API call per card, ~150ms each. Acceptable for interactive use. `--no-verify` escapes for bulk imports.

**[Risk] Export Scryfall calls fail mid-run** → Mitigation: collect all failures, report them together at the end. Don't abort on first failure. Let the user fix all missing cards at once.

**[Risk] A card exists on Scryfall but is unreachable due to rate limiting** → Mitigation: the existing `RATE_DELAY` in `scryfall.py` already handles this. Export validation reuses the same client.

**[Risk] User adds a card via `--no-verify` with a wrong name, then exports without `--skip-scryfall`** → This is correct behavior: export catches it. The `--no-verify` flag is an explicit bypass, not a permanent exemption.

## Migration Plan

No schema migration needed. All changes are additive:
- New CLI flags are optional
- New log fields appear only in new entries
- `fuzzy_lookup` rename is internal to `scryfall.py`; no external callers

Deployment: ship as a single commit on a feature branch. No staged rollout needed.

## Open Questions

None — design is fully settled based on exploration session.

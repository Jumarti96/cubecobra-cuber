# Spec — enricher-skip-if-enriched

## ADDED Requirements

### Requirement: Enrich skips cards that are already correctly enriched
`cuber enrich` SHALL skip fetching a card from Scryfall if all of the following are true:
1. The card name exists in `enriched.json` with a non-empty `scryfall_id`
2. If the `mainboard.csv` row has a `Set` value: the enriched entry's `set_code` matches it (case-insensitive)
3. If the `mainboard.csv` row has a `Collector Number`: the enriched entry's `collector_number` matches it

If any condition fails, the card is re-fetched.

#### Scenario: Already-enriched card is skipped on re-run
- **WHEN** `enriched.json` contains "Lightning Bolt" with a valid `scryfall_id` and `set_code="lea"`
- **AND** `mainboard.csv` row has `Set=LEA`
- **AND** user runs `cuber enrich`
- **THEN** no Scryfall call is made for "Lightning Bolt"
- **AND** the existing enriched data is preserved as-is

#### Scenario: Card with changed Set is re-fetched
- **WHEN** `enriched.json` contains "Lightning Bolt" with `set_code="lea"`
- **AND** user changes `mainboard.csv` row to `Set=M11`
- **AND** user runs `cuber enrich`
- **THEN** Scryfall is called for "Lightning Bolt" using `{"name": "Lightning Bolt", "set": "m11"}`
- **AND** `enriched.json` is updated with the M11 printing data

#### Scenario: New card added via add-card is fetched
- **WHEN** a card name exists in `mainboard.csv` but not in `enriched.json`
- **THEN** Scryfall is called for that card normally

---

### Requirement: --refresh flag forces full re-enrichment
When `cuber enrich` is run with `--refresh`, ALL cards SHALL be re-fetched from Scryfall regardless of their current enriched state.

#### Scenario: --refresh bypasses skip logic
- **WHEN** user runs `cuber enrich <id> --refresh`
- **THEN** every card in `mainboard.csv` is re-fetched from Scryfall
- **AND** `enriched.json` is fully rebuilt

---

### Requirement: Enrich output reports skip count
The CLI output of `cuber enrich` SHALL report how many cards were skipped (already enriched) and how many were newly fetched.

#### Scenario: Partial re-enrich reports counts
- **WHEN** 500 of 540 cards are skipped and 40 are newly fetched
- **THEN** CLI prints something like: `Skipped 500 (already enriched). Fetched 40 new/changed cards.`

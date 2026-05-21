# Spec — export-validation

## ADDED Requirements

### Requirement: Duplicate cards are allowed in mainboard
The system SHALL permit multiple rows with the same card name in `mainboard.csv`. Duplicates SHALL NOT block export. The `cuber dedup` command exists for users who want to enforce uniqueness.

#### Scenario: Export succeeds with intentional duplicates
- **WHEN** `mainboard.csv` contains two rows named "Ponder"
- **THEN** `cuber export` succeeds and both rows appear in `import-ready.csv`

#### Scenario: Dedup command still removes duplicates on request
- **WHEN** user runs `cuber dedup <id>`
- **THEN** duplicate rows are removed, keeping the first occurrence

---

### Requirement: Export validates all cards against Scryfall
Before writing `import-ready.csv`, `cuber export` SHALL verify that every mainboard card exists on Scryfall. Cards already present in `enriched.json` with a non-empty `scryfall_id` are considered pre-verified and require no network call. Cards not in `enriched.json` are verified via a live Scryfall fuzzy lookup.

#### Scenario: Fully enriched cube exports without network calls
- **WHEN** `enriched.json` exists and all mainboard card names have a matching `scryfall_id`
- **THEN** export completes with no Scryfall API calls

#### Scenario: Un-enriched cube is validated live at export
- **WHEN** `enriched.json` does not exist or is missing some cards
- **THEN** export calls Scryfall for each unverified card before proceeding

#### Scenario: Unknown card blocks export
- **WHEN** a card name in `mainboard.csv` cannot be matched by Scryfall (exact or fuzzy)
- **THEN** export is blocked, the card name is reported as an error, and `import-ready.csv` is NOT written

#### Scenario: Multiple unknown cards reported together
- **WHEN** several card names fail Scryfall lookup
- **THEN** all failing names are reported in a single error block before aborting

---

### Requirement: --skip-scryfall flag bypasses validation
`cuber export` SHALL accept a `--skip-scryfall` flag that disables all Scryfall verification. When set, export proceeds based solely on local data.

#### Scenario: Offline export skips Scryfall
- **WHEN** user runs `cuber export <id> --skip-scryfall`
- **THEN** no Scryfall API calls are made and export proceeds without card verification

---

### Requirement: Export log entry is enriched with validation metadata
Each entry written to `exports/export-log.json` SHALL include:
- `export_number`: sequential integer starting at 1 for the first export of this cube
- `cube_title`: string from `meta.json["title"]`
- `enrichment_coverage`: string `"N/M"` where N = cards with a `scryfall_id` in `enriched.json`, M = total mainboard cards
- `missing_from_scryfall`: list of card names that failed Scryfall lookup during this export
- `validation_summary`: object `{"errors": N, "warnings": N}`
- `rarity_delta`: object with per-rarity counts of cards added and removed vs remote, e.g. `{"rare": {"added": 2, "removed": 1}}`

Existing log entries (from before this change) SHALL remain unchanged.

#### Scenario: New export log entry contains all required fields
- **WHEN** `cuber export` completes successfully
- **THEN** the new entry at index 0 of `export-log.json` contains all six fields above

#### Scenario: Coverage reflects enrichment state
- **WHEN** 500 of 540 mainboard cards have a `scryfall_id` in `enriched.json`
- **THEN** `enrichment_coverage` is `"500/540"`

#### Scenario: Rarity delta reflects cards added and removed since last fetch
- **WHEN** the user has added 2 rare cards and removed 1 uncommon since the last `cuber fetch`
- **THEN** `rarity_delta` contains `{"rare": {"added": 2, "removed": 0}, "uncommon": {"added": 0, "removed": 1}}`

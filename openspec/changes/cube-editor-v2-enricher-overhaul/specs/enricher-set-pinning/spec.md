# Spec — enricher-set-pinning

## ADDED Requirements

### Requirement: Enrich uses set+collector_number identifier when both are present
When a `mainboard.csv` row has non-empty `Set` AND `Collector Number` columns, `cuber enrich` SHALL fetch that card from Scryfall using a `{set, collector_number}` identifier, locking in the exact printing.

#### Scenario: Set-fetched cube preserves set codes after enrich
- **WHEN** `mainboard.csv` contains rows with `Set=MH3` and `Collector Number=42`
- **AND** user runs `cuber enrich`
- **THEN** Scryfall is queried by `{"set": "mh3", "collector_number": "42"}`
- **AND** the resulting `enriched.json` entry has `set_code="mh3"`
- **AND** `mainboard.csv` still shows `Set=MH3` after backfill

---

### Requirement: Enrich uses name+set identifier when set is present but collector number is absent
When a `mainboard.csv` row has a non-empty `Set` but no `Collector Number`, `cuber enrich` SHALL fetch using a `{name, set}` identifier.

#### Scenario: Set-scoped lookup without collector number
- **WHEN** `mainboard.csv` has `name="Lightning Bolt"`, `Set=M11`, `Collector Number=""`
- **THEN** Scryfall is queried by `{"name": "Lightning Bolt", "set": "m11"}`
- **AND** the returned card is from set M11

---

### Requirement: Enrich falls back to name-only lookup when no set is specified
When a `mainboard.csv` row has no `Set` value, `cuber enrich` SHALL fetch by `{name}` only, and Scryfall's canonical printing is used.

#### Scenario: Name-only lookup for unspecified set
- **WHEN** `mainboard.csv` has `name="Counterspell"` with empty `Set`
- **THEN** Scryfall is queried by `{"name": "Counterspell"}`
- **AND** the resulting enriched entry uses whatever printing Scryfall considers canonical

---

### Requirement: _backfill_mainboard_csv does not overwrite a user-specified Set value
When writing Scryfall data back into `mainboard.csv`, the `Set` column SHALL NOT be overwritten if the row already has a non-empty `Set` value.

#### Scenario: Backfill preserves existing Set column
- **WHEN** `mainboard.csv` row has `Set=MH3`
- **AND** enrich completes with the MH3 printing
- **THEN** `mainboard.csv` row still shows `Set=MH3`

#### Scenario: Backfill writes Set for name-only cards
- **WHEN** `mainboard.csv` row has empty `Set`
- **AND** Scryfall returns a printing from set "lea"
- **THEN** `mainboard.csv` row is updated to `Set=LEA`

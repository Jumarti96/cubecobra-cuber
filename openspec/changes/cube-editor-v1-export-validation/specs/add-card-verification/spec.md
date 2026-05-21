# Spec — add-card-verification

## ADDED Requirements

### Requirement: add-card verifies names against Scryfall by default
When the user runs `cuber add-card`, the system SHALL call Scryfall's fuzzy lookup for each card name before writing to `mainboard.csv`. This behavior is ON by default.

#### Scenario: Exact name match — card added with canonical name
- **WHEN** user runs `cuber add-card obc "Lightning Bolt"`
- **THEN** the card is added to `mainboard.csv` as "Lightning Bolt" (Scryfall's canonical form)

#### Scenario: Fuzzy match corrects a typo — canonical name used with notice
- **WHEN** user runs `cuber add-card obc "Lightning Bol"`
- **THEN** Scryfall returns "Lightning Bolt" as the fuzzy match
- **AND** the card is added as "Lightning Bolt"
- **AND** the CLI prints: `"Lightning Bol" → added as "Lightning Bolt"`

#### Scenario: Unknown card name is rejected
- **WHEN** user runs `cuber add-card obc "Xyzzyx the Unknowable"`
- **THEN** Scryfall finds no match
- **AND** the card is NOT added to `mainboard.csv`
- **AND** the CLI prints an error identifying the attempted name

#### Scenario: Multiple cards — partial success
- **WHEN** user adds three cards and one fails Scryfall lookup
- **THEN** the two valid cards are added
- **AND** the failed card is reported separately with its attempted name
- **AND** the CLI instructs the user to re-run with the correct name

---

### Requirement: --no-verify flag bypasses Scryfall on add-card
`cuber add-card` SHALL accept a `--no-verify` flag. When set, cards are written to `mainboard.csv` as stubs without any Scryfall call. A warning is printed for each unverified card.

#### Scenario: Bulk import bypasses verification
- **WHEN** user runs `cuber add-card obc --from-file cards.txt --no-verify`
- **THEN** all card names in the file are added immediately without Scryfall calls
- **AND** the CLI prints: `(unverified — run cuber enrich to hydrate)`

---

### Requirement: Network failure on add-card is non-blocking
If a Scryfall API call fails due to a network error during `add-card`, the system SHALL add the card anyway and print a warning that it is unverified.

#### Scenario: Scryfall unreachable — card added with warning
- **WHEN** Scryfall is unreachable (timeout or connection error)
- **THEN** the card is added to `mainboard.csv`
- **AND** the CLI prints: `(unverified — Scryfall unreachable)`

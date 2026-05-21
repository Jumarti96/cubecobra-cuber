# Spec — swap-card

## ADDED Requirements

### Requirement: cuber swap atomically replaces one card with another
The system SHALL provide a `cuber swap <id> <old_name> <new_name>` command that removes one card and adds another in a single operation. The new card is verified against Scryfall before any mutation occurs.

#### Scenario: Successful swap
- **WHEN** user runs `cuber swap obc "Dark Ritual" "Cabal Ritual"`
- **AND** "Dark Ritual" exists in `mainboard.csv`
- **AND** Scryfall confirms "Cabal Ritual" exists
- **THEN** "Dark Ritual" is removed from `mainboard.csv`
- **AND** "Cabal Ritual" is added to `mainboard.csv`
- **AND** the CLI prints the removed and added card names

#### Scenario: New card not found — swap aborted, no changes made
- **WHEN** user runs `cuber swap obc "Dark Ritual" "Cabal Ritu"` (typo)
- **AND** Scryfall cannot match "Cabal Ritu" exactly or fuzzily
- **THEN** `mainboard.csv` is NOT modified
- **AND** the CLI reports the new card name was not found on Scryfall
- **AND** "Dark Ritual" remains in the cube

#### Scenario: New card matched fuzzily — swap proceeds with canonical name
- **WHEN** Scryfall returns a fuzzy match for the new card name
- **THEN** swap proceeds using the canonical Scryfall name
- **AND** the CLI notes the name correction: `"Cabal Ritu" → swapped in as "Cabal Ritual"`

#### Scenario: Old card not found in mainboard
- **WHEN** the card to remove does not exist in `mainboard.csv`
- **THEN** swap is aborted with an error
- **AND** no changes are made

#### Scenario: Swap targets maybeboard
- **WHEN** user runs `cuber swap obc "Card A" "Card B" --maybeboard`
- **THEN** the operation is performed on `maybeboard.csv` instead of `mainboard.csv`

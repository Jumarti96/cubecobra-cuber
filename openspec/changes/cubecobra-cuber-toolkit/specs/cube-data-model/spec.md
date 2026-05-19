## ADDED Requirements

### Requirement: Canonical enriched.json schema
The system SHALL produce `cubes/{short-id}/enriched.json` as the authoritative joined representation of CubeCobra + Scryfall data. This file is the contract between CLI data commands and Claude Code skills.

#### Scenario: enriched.json produced by enrich command
- **WHEN** `python -m cuber enrich obc` completes successfully
- **THEN** `cubes/obc/enriched.json` exists and contains: `cube_id`, `short_id`, `title`, `fetched_at`, and a `cards` array where each entry has: `name`, `cmc`, `type_line`, `color_identity` (array), `oracle_text`, `power`, `toughness`, `rarity`, `set`, `collector_number`, `color_category`, `tags` (array, may be empty), `board`, `finish`, `status`, `image_url`, `scryfall_id`, and optionally `card_faces`

#### Scenario: Tags field initialized empty
- **WHEN** enrich runs before any tagging has been done
- **THEN** each card in enriched.json has `tags: []`

### Requirement: Card dataclass validation
The system SHALL validate that each card object has at minimum: `name` (non-empty string), `scryfall_id` (non-empty string), `color_identity` (array), `cmc` (non-negative float), `type_line` (non-empty string). Cards failing validation SHALL be logged as warnings and excluded from enriched.json.

#### Scenario: Missing required field
- **WHEN** a card record from Scryfall is missing `type_line`
- **THEN** the card is excluded from enriched.json, a warning is printed with the card name, and the field is added to `meta.json.validation_warnings`

### Requirement: meta.json schema
The system SHALL maintain `cubes/{short-id}/meta.json` with: `short_id`, `cube_id`, `title`, `url`, `fetched_at`, `card_count`, `missing_cards` (array), `schema_warning` (bool), `validation_warnings` (array).

#### Scenario: meta.json updated on enrich
- **WHEN** `enrich` completes
- **THEN** `meta.json.card_count` is updated to reflect the number of successfully enriched cards

### Requirement: Deck output schema
The system SHALL write deck files to `cubes/{short-id}/decks/{deck-name}.json` with: `deck_name`, `cube_short_id`, `built_at`, `strategy`, `colors`, `cards` (array of card objects from enriched.json), `land_count`, `nonland_count`.

#### Scenario: Deck file written after /build-deck
- **WHEN** the user approves a deck built by the /build-deck skill
- **THEN** a valid deck JSON is written to `cubes/{short-id}/decks/` with the above schema

## ADDED Requirements

### Requirement: Color identity distribution
The system SHALL compute, for a cube, the count and percentage of cards by color identity: W, U, B, R, G, multicolor, colorless. The report SHALL be informational — no thresholds trigger errors or warnings.

#### Scenario: Stats output for a mono-red cube
- **WHEN** `python -m cuber stats obc` is run on a cube with 360 red cards
- **THEN** the report shows 360 (100%) Red and 0 for all other colors — no warning is emitted about color imbalance

#### Scenario: Sidecar JSON written
- **WHEN** stats completes
- **THEN** `cubes/{short-id}/analysis.json` is written with the full stats object in addition to the human-readable stdout summary

### Requirement: CMC curve
The system SHALL compute the count of cards at each CMC value (0 through 7+), separated by card type (creature vs. non-creature). Output SHALL include both raw counts and a simple ASCII bar chart.

#### Scenario: CMC curve displayed
- **WHEN** `python -m cuber stats obc` is run
- **THEN** stdout includes a CMC distribution table and ASCII bar chart showing creature vs. non-creature counts per CMC value

### Requirement: Rarity breakdown
The system SHALL compute the count and percentage of cards by rarity: common, uncommon, rare, mythic, special.

#### Scenario: Rarity reported
- **WHEN** stats runs
- **THEN** output includes rarity distribution with counts and percentages

### Requirement: Card type breakdown
The system SHALL compute counts for: Creature, Instant, Sorcery, Enchantment, Artifact, Planeswalker, Land, Other. Cards that match multiple types (e.g., Artifact Creature) SHALL be counted under the most specific primary type.

#### Scenario: Type breakdown reported
- **WHEN** stats runs
- **THEN** output includes a card type table with counts and percentages

### Requirement: Archetype tag density (when tags present)
When `tags` fields are populated in enriched.json, the system SHALL report the count and percentage of cards carrying each tag. Tags with fewer than 3 cards SHALL be flagged as potentially under-supported — as an informational note, not an error.

#### Scenario: Tag density reported when tags exist
- **WHEN** stats runs after tagging has been performed
- **THEN** output includes a tag density table sorted by count descending, with a note for tags appearing on fewer than 3 cards

#### Scenario: Tag density skipped when no tags
- **WHEN** stats runs on a cube with no tags in enriched.json
- **THEN** the tag density section is omitted from output with a note suggesting the user run `/tag-cube` first

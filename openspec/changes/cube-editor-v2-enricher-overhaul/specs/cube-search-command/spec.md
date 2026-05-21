# Spec — cube-search-command

## ADDED Requirements

### Requirement: cuber search filters local cube cards by multiple criteria
The system SHALL provide a `cuber search <id>` command that queries the local enriched card pool using any combination of: color identity, card type, CMC range, oracle text pattern, tags, and rarity.

#### Scenario: Search by color and type
- **WHEN** user runs `cuber search obc --color B --type creature`
- **THEN** CLI prints a table of black creatures in the mainboard

#### Scenario: Search by oracle text
- **WHEN** user runs `cuber search obc --oracle "draw a card"`
- **THEN** CLI prints all mainboard cards whose oracle text matches the pattern (case-insensitive)

#### Scenario: Search by CMC range
- **WHEN** user runs `cuber search obc --cmc-min 1 --cmc-max 2`
- **THEN** CLI prints all mainboard cards with CMC 1 or 2

#### Scenario: Search by tag
- **WHEN** user runs `cuber search obc --tag removal`
- **THEN** CLI prints all mainboard cards tagged "removal"

#### Scenario: No results
- **WHEN** the filter matches no cards
- **THEN** CLI prints "No cards found."

---

### Requirement: cuber search results are formatted as an ASCII table
Results SHALL be displayed as a compact table with columns: Name, Color Identity, CMC, Rarity, Tags, Oracle excerpt. The default result limit is 25 cards; `--limit N` overrides it.

#### Scenario: Results truncated with count
- **WHEN** search matches 60 cards and `--limit` is not set
- **THEN** the first 25 are shown and the CLI prints "... and 35 more cards"

---

### Requirement: cuber search requires enriched data
If `enriched.json` does not exist for the given cube, `cuber search` SHALL print an error directing the user to run `cuber enrich` first, and exit with a non-zero code.

#### Scenario: Missing enriched.json
- **WHEN** user runs `cuber search obc --type instant` and `enriched.json` does not exist
- **THEN** CLI prints: `enriched.json not found — run cuber enrich obc first`
- **AND** exits with code 1

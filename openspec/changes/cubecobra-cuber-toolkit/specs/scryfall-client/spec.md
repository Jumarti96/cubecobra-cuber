## ADDED Requirements

### Requirement: Per-card Scryfall lookup with SQLite cache
The system SHALL fetch card metadata from Scryfall and cache results in `cubes/.cache/scryfall.db` (SQLite). Cache lookup SHALL use normalized card name as key. Cached entries SHALL expire after 7 days; a `--refresh` flag SHALL bust the cache for a given cube.

#### Scenario: Cache miss — card fetched from API
- **WHEN** `enrich` is run and a card is not in the SQLite cache
- **THEN** the system fetches the card from Scryfall, stores oracle_id, color_identity, oracle_text, power, toughness, cmc, type_line, mana_cost, rarity, set, layout, card_faces in the cache, and uses it for enrichment

#### Scenario: Cache hit — card served from SQLite
- **WHEN** `enrich` is run and a card was cached within the last 7 days
- **THEN** the system reads from SQLite without making a network request

#### Scenario: Cache refresh
- **WHEN** the user runs `python -m cuber enrich obc --refresh`
- **THEN** the system ignores cached entries for all cards in the cube and re-fetches from Scryfall

### Requirement: Batch fetch via /cards/collection
The system SHALL use Scryfall's `/cards/collection` endpoint to fetch up to 75 cards per request, respecting the 10 req/sec rate limit with at least 100ms delay between requests.

#### Scenario: Full cube enrichment
- **WHEN** `enrich` is run on a 360-card cube with a cold cache
- **THEN** the system issues no more than 5 batch requests (75 cards each), completes without 429 errors, and stores all cards in SQLite

#### Scenario: Rate limit respected
- **WHEN** issuing multiple batch requests
- **THEN** each request is separated by at least 100ms to stay within the 10 req/sec limit

### Requirement: Double-faced card handling
The system SHALL correctly handle DFC (double-faced cards) by storing both faces' oracle text, mana cost, type line, power, and toughness.

#### Scenario: DFC enrichment
- **WHEN** a card has `layout` of `transform` or `modal_dfc`
- **THEN** the enriched card record contains a `card_faces` array with `name`, `oracle_text`, `mana_cost`, `type_line`, `power`, `toughness` for each face

### Requirement: Fetch all cards from a retail set
The system SHALL support querying all cards in a given set code using Scryfall's `/cards/search` endpoint with `q=set:{code}` and paginating through all results.

#### Scenario: Set fetch
- **WHEN** the user runs `python -m cuber fetch-set eoe`
- **THEN** the system paginates through all Scryfall results for set `eoe`, collects all unique cards, and saves them as a cube in `cubes/eoe/`

#### Scenario: Unknown set code
- **WHEN** the user provides a set code that Scryfall does not recognize
- **THEN** the system prints a clear error with the Scryfall response and exits with a non-zero code

### Requirement: Card not found handling
The system SHALL handle cards not found on Scryfall gracefully, recording them in `meta.json` under `missing_cards` and continuing enrichment for all other cards.

#### Scenario: Card missing from Scryfall
- **WHEN** a card in raw.csv cannot be found on Scryfall (custom card, misspelling, or unreleased card)
- **THEN** the system skips that card, adds its name to `meta.json.missing_cards`, and completes enrichment for all remaining cards

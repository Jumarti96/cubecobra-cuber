## ADDED Requirements

### Requirement: Human-readable output with JSON sidecar
Every CLI command SHALL print a human-readable summary to stdout AND write full structured output to a sidecar JSON file. The sidecar path SHALL be printed as the last line of stdout (e.g., `Full output: cubes/obc/analysis.json`).

#### Scenario: Stats command sidecar
- **WHEN** `python -m cuber stats obc` completes
- **THEN** stdout contains a human-readable distribution table, and `cubes/obc/analysis.json` contains the complete structured data

### Requirement: fetch command
`python -m cuber fetch {short-id}` SHALL download the cube from CubeCobra and write `raw.csv` + `meta.json`. Options: `--dry-run` (print URL without fetching).

#### Scenario: Successful fetch
- **WHEN** `python -m cuber fetch obc` is run
- **THEN** `cubes/obc/raw.csv` and `cubes/obc/meta.json` are written, stdout shows card count and fetch timestamp

### Requirement: enrich command
`python -m cuber enrich {short-id}` SHALL look up each card from `raw.csv` in Scryfall and write `enriched.json`. Options: `--refresh` (bust SQLite cache). If `raw.csv` is missing, the command SHALL automatically run `fetch` first and log the auto-trigger to stdout before proceeding.

#### Scenario: enrich auto-triggers fetch when raw.csv missing
- **WHEN** `python -m cuber enrich obc` is run and `cubes/obc/raw.csv` does not exist
- **THEN** the command prints "raw.csv not found — running fetch first..." and automatically fetches the cube before proceeding with enrichment

#### Scenario: enrich runs normally when raw.csv exists
- **WHEN** `python -m cuber enrich obc` is run and `cubes/obc/raw.csv` already exists
- **THEN** the command proceeds directly to Scryfall lookup without re-fetching

### Requirement: stats command
`python -m cuber stats {short-id}` SHALL read `enriched.json` and print color/type/rarity/CMC distributions. SHALL fail with a clear message if `enriched.json` is missing.

#### Scenario: Stats on unenriched cube
- **WHEN** `python -m cuber stats obc` is run without enriched.json
- **THEN** the command prints "Run `python -m cuber enrich obc` first." and exits with code 1

### Requirement: tag command
`python -m cuber tag {short-id}` SHALL read `enriched.json`, batch-process cards through the LLM tagger, and write `tagged.csv`. Options: `--overwrite` (replace existing tags instead of merging).

#### Scenario: Tag writes tagged.csv
- **WHEN** `python -m cuber tag obc` completes
- **THEN** `cubes/obc/tagged.csv` exists with the `tags` column populated

### Requirement: export command
`python -m cuber export {short-id}` SHALL write `tagged.csv` from the current state of `enriched.json` (using whatever tags are already stored there). This is the "finalize for upload" command.

#### Scenario: Export produces importable CSV
- **WHEN** `python -m cuber export obc` runs
- **THEN** `cubes/obc/tagged.csv` contains the 19-column CubeCobra format with current tags

### Requirement: fetch-set command
`python -m cuber fetch-set {set-code}` SHALL query Scryfall for all cards in the given set and save them as a cube in `cubes/{set-code}/`. Options: `--exclude-basics` (default: true), `--exclude-tokens` (default: true).

#### Scenario: fetch-set creates cube folder
- **WHEN** `python -m cuber fetch-set eoe` completes
- **THEN** `cubes/eoe/raw.csv` and `cubes/eoe/meta.json` exist, with `meta.json.source` set to `"scryfall-set:eoe"`

### Requirement: list command
`python -m cuber list` SHALL print a table of all locally cached cubes showing: short ID, title, card count, last fetched date.

#### Scenario: List shows all cubes
- **WHEN** `python -m cuber list` is run with two cubes cached
- **THEN** stdout shows a two-row table with short ID, title, card count, fetched_at for each

### Requirement: diff command
`python -m cuber diff {id1} {id2}` SHALL compare two cubes and report: cards in both, cards only in id1, cards only in id2, and delta stats (color/type/rarity counts).

#### Scenario: Diff between two cubes
- **WHEN** `python -m cuber diff obc vintage-540` is run
- **THEN** stdout lists shared cards, cards unique to each, and the stat deltas; sidecar JSON is written to a temp path printed at the end

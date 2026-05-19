## ADDED Requirements

### Requirement: Oracle-text-based functional tagging
The system SHALL tag each card by constructing a prompt that includes the card's name, type line, and oracle text from `enriched.json`. The LLM SHALL assign zero or more functional tags from a canonical tag vocabulary. The system SHALL NEVER assume card abilities from training data — all tagging decisions MUST be grounded in oracle text provided in the prompt.

#### Scenario: Card tagged by oracle text
- **WHEN** tagger.py processes "Lightning Bolt" with oracle text "Lightning Bolt deals 3 damage to any target."
- **THEN** the LLM assigns tags including `removal` and `creature-removal` based on the oracle text, not prior knowledge of the card

#### Scenario: Card with no matching tags
- **WHEN** a card's oracle text does not match any canonical tag category
- **THEN** the card receives an empty tags array and no error is raised

### Requirement: Canonical tag vocabulary
The system SHALL prompt the LLM using a fixed canonical tag list: `card-draw`, `card-advantage`, `removal`, `creature-removal`, `artifact-removal`, `enchantment-removal`, `board-wipe`, `counterspell`, `ramp`, `land-fetch`, `aggro`, `control`, `combo`, `engine`, `graveyard`, `token`, `tutor`, `looting`, `discard`, `protection`, `haste-enabler`, `evasion`, `lord`, `land`, `mana-rock`, `mana-dork`. Additional tags may be returned if the LLM identifies a relevant category not in the list.

#### Scenario: Tag from canonical list assigned
- **WHEN** a card draws cards ("draw a card" in oracle text)
- **THEN** it receives at minimum the `card-draw` tag

### Requirement: Batch processing with cost preview
The system SHALL process cards in batches of 50 and SHALL print an estimated token count and LLM cost estimate before proceeding, with a confirmation prompt.

#### Scenario: Cost preview shown before tagging
- **WHEN** the user runs `python -m cuber tag obc`
- **THEN** the system prints "Estimated: ~N tokens, ~$X.XX at current model rates. Proceed? [y/N]" before making any API calls

#### Scenario: User declines cost
- **WHEN** the user enters "N" at the cost confirmation
- **THEN** no LLM calls are made and no files are written

### Requirement: Tagged.csv output
The system SHALL write `cubes/{short-id}/tagged.csv` in CubeCobra's 19-column CSV format with the `tags` column populated as semicolon-separated values. This file SHALL be directly importable via CubeCobra's "Replace with CSV" feature.

#### Scenario: tagged.csv matches CubeCobra import format
- **WHEN** tagging completes
- **THEN** `tagged.csv` has exactly the 19 CubeCobra columns, with `tags` containing values like `removal;creature-removal` (semicolons, no spaces around delimiter)

### Requirement: Tags merged with existing tags
If cards in `enriched.json` already have tags (from a previous tagging run or manual edit), the system SHALL merge new AI-generated tags with existing ones, deduplicating. The `--overwrite` flag SHALL replace existing tags entirely.

#### Scenario: Tags merged on re-run
- **WHEN** a card already has tag `removal` and the AI assigns `creature-removal`
- **THEN** the card ends up with both `removal` and `creature-removal` (deduplicated)

## ADDED Requirements

### Requirement: /tag-cube skill reads enriched.json and tags cards
The skill SHALL read `cubes/{short-id}/enriched.json`, construct prompts using only oracle text present in that file, assign functional tags to each card, and write `cubes/{short-id}/tagged.csv`. The skill SHALL NEVER infer card abilities from training data.

#### Scenario: Skill invoked with cube ID
- **WHEN** the user runs `/tag-cube obc`
- **THEN** the skill reads `cubes/obc/enriched.json`, tags all cards using oracle text from the file, and writes `cubes/obc/tagged.csv` with the `tags` column populated

#### Scenario: enriched.json missing
- **WHEN** `/tag-cube obc` is invoked and `cubes/obc/enriched.json` does not exist
- **THEN** the skill instructs the user to run `python -m cuber fetch obc` and `python -m cuber enrich obc` first and stops

### Requirement: Iron rule — oracle text only
The skill instructions SHALL include an explicit hard rule: "Never assume what a card does. All tag assignments must be justified by the oracle text in enriched.json. If oracle text is missing or unclear, assign no tag and note the card."

#### Scenario: Card with ambiguous oracle text
- **WHEN** a card's oracle text does not clearly map to any canonical tag
- **THEN** the skill assigns no tags to that card and lists it in a "Review needed" section of the output

### Requirement: Tag output summary
The skill SHALL present a summary table before writing tagged.csv: card name | assigned tags, grouped by tag, with a count per tag.

#### Scenario: Summary shown before writing
- **WHEN** tagging completes
- **THEN** the skill displays a tag distribution table and asks the user to confirm before writing tagged.csv

## ADDED Requirements

### Requirement: /set-cube creates a cube from all cards in a retail MTG set
The skill SHALL accept a set name or set code, resolve it to a Scryfall set code if needed, run `python -m cuber fetch-set {code}`, ask clarifying questions about card inclusion, and produce an analysis of the set's draft viability and mechanical identity.

#### Scenario: Set identified from full name
- **WHEN** the user says "Build me a cube from Edge of Eternities"
- **THEN** the skill resolves "Edge of Eternities" to set code `eoe` and runs `python -m cuber fetch-set eoe`

#### Scenario: Set identified from code
- **WHEN** the user says "/set-cube eoe"
- **THEN** the skill runs `python -m cuber fetch-set eoe` directly without name resolution

#### Scenario: Unknown set name
- **WHEN** the user provides a set name that cannot be resolved to a Scryfall code
- **THEN** the skill asks the user to confirm the set code directly, rather than guessing

### Requirement: Inclusion clarification interview
The skill SHALL ask the user about card inclusion preferences before processing: include basic lands? Include tokens? Restrict to specific rarities only?

#### Scenario: Basics excluded by default
- **WHEN** the user does not specify
- **THEN** the skill excludes basic lands and tokens by default and confirms this with the user

### Requirement: Mechanical identity analysis
The skill SHALL analyze the set's mechanical themes by reading oracle text of all fetched cards and identifying recurring mechanics, keywords, and archetypes. The skill MUST cite oracle text — it SHALL NEVER assume a set's themes from training data.

#### Scenario: Mechanical themes identified from oracle text
- **WHEN** 40% of cards in the set have "surveil" in their oracle text
- **THEN** the skill identifies Surveil as a primary mechanical theme of the set, citing example oracle texts

### Requirement: Draft viability assessment
The skill SHALL evaluate how well the set supports draft play by checking archetype density (how many cards support each identified theme), color balance, and removal density. All assessments SHALL be informational.

#### Scenario: Draft viability reported
- **WHEN** set-cube analysis completes
- **THEN** the skill presents: mechanical themes found, archetype density per theme per color, color balance, removal count, and an overall draft viability note (informational, not a pass/fail)

### Requirement: Optional size reduction
If the set has more cards than a target draft size (e.g., 360), the skill SHALL optionally suggest cuts to reach that target, following the same oracle-text-verification and self-grill discipline as /suggest-cube.

#### Scenario: User requests reduction to 360
- **WHEN** the set has 480 cards and the user asks to trim to 360
- **THEN** the skill proposes specific cuts prioritized by: duplicate effects, low-power cards, narrow situational cards — all justified by oracle text comparison

### Requirement: Output written to cubes/{set-code}/
The skill SHALL ensure `cubes/{set-code}/raw.csv`, `enriched.json`, and `meta.json` exist after the workflow, with `meta.json.source` set to `"scryfall-set:{code}"`.

#### Scenario: Cube folder created
- **WHEN** /set-cube eoe completes
- **THEN** `cubes/eoe/` contains raw.csv, enriched.json, and meta.json with source field set correctly

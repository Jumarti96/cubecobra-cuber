## ADDED Requirements

### Requirement: /analyze-cube skill produces stats dashboard
The skill SHALL read `cubes/{short-id}/enriched.json`, compute color/type/rarity/CMC distributions and archetype tag density, and present a structured dashboard. All metrics SHALL be informational — no distribution triggers an error or blocks the user.

#### Scenario: Full analysis displayed
- **WHEN** the user runs `/analyze-cube obc`
- **THEN** the skill displays: color identity distribution, CMC curve with ASCII bar chart, rarity breakdown, card type breakdown, and (if tags exist) archetype tag density

#### Scenario: Analysis on untagged cube
- **WHEN** `/analyze-cube obc` is run on a cube with no tags
- **THEN** the skill shows all non-tag metrics and includes a note: "Tags not found — run /tag-cube obc to see archetype coverage"

### Requirement: analysis.json sidecar written
The skill SHALL write `cubes/{short-id}/analysis.json` containing all computed metrics in structured JSON.

#### Scenario: Sidecar written
- **WHEN** analysis completes
- **THEN** `cubes/{short-id}/analysis.json` is written and the skill prints its path

### Requirement: Balance checks are informational
The skill SHALL report balance metrics (e.g., "White has 15% of cards, convention is 15–20%") as observations, never as errors. The skill SHALL NOT block the user or suggest a cube is broken based on generic reference ranges.

#### Scenario: Imbalanced cube analyzed
- **WHEN** a cube has 80% red cards
- **THEN** the skill reports this as a fact ("Red: 288/360 cards, 80%") without emitting a warning or error about color imbalance

### Requirement: Tool selection table in skill doc
The skill document SHALL include a reference table mapping analysis tasks to CLI commands, so Claude knows exactly which command to run for each data need.

#### Scenario: Claude picks correct command
- **WHEN** the skill needs CMC curve data
- **THEN** Claude runs `python -m cuber stats {id}` and reads the sidecar JSON, not a custom implementation

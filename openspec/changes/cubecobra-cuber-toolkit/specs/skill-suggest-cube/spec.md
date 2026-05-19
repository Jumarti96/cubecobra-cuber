## ADDED Requirements

### Requirement: /suggest-cube analyzes gaps and proposes specific swaps
The skill SHALL load `enriched.json` + `tagged.csv`, run an internal analysis pass, identify the most impactful problems (color gaps, archetype starvation, signal dilution, power outliers, accidental combo warps), and propose specific cuts + specific adds with oracle-text-verified justifications.

#### Scenario: Skill identifies archetype starvation
- **WHEN** a cube has a `graveyard` tag on fewer than 3 cards
- **THEN** the skill flags this as a potential starvation signal and proposes specific adds to strengthen the archetype, citing Scryfall oracle text for each proposed add

#### Scenario: Proposed add verified via oracle text
- **WHEN** the skill proposes adding a card to fill a removal gap
- **THEN** the proposal includes the card's oracle text to confirm it fills the stated role

### Requirement: Iron rule — oracle text only
All justifications for cuts and adds SHALL cite oracle text. The skill SHALL NEVER claim a card "does X" without including its oracle text as evidence.

#### Scenario: Cut justified by oracle text
- **WHEN** the skill proposes cutting a card for being a "power outlier"
- **THEN** the proposal includes the card's oracle text and explains which specific ability makes it warping

### Requirement: Self-grill gate (hard gate before presenting to user)
Before presenting recommendations, the skill SHALL run two parallel subagents:

**Proposer responsibilities:**
- Defend each cut: what problem does removing this card solve?
- Defend each add: how does this card solve the identified problem? (cite oracle text)
- Confirm the add is available on Scryfall (search if needed)

**Challenger responsibilities:**
- Independently read oracle text for every cut and add
- Confirm the proposed add actually addresses the stated problem
- Ask: "Is there a better add that solves this problem with less disruption to the cube?"
- Check whether the cut removes critical support for another archetype (consult tagged.csv)
- Verify the add fits the cube's power level (compare CMC and effect to existing cards)

#### Scenario: Self-grill catches collateral damage
- **WHEN** the Proposer suggests cutting a card that also appears in tagged.csv under `ramp` and `engine`
- **THEN** the Challenger flags that removing it weakens two archetypes, and the Proposer must either justify the cut more strongly or propose an alternative

### Requirement: Recommendations presented as a table
The skill SHALL present final recommendations as a table: Cut | Reason | Add | Reason | Expected Impact. The user SHALL be asked to approve before any files are written.

#### Scenario: Table shown before writing
- **WHEN** self-grill completes
- **THEN** a formatted table of all proposed swaps is shown with a "Apply these changes? [y/N]" prompt

### Requirement: tagged.csv updated on approval
On user approval, the skill SHALL update `enriched.json` with the new card set and write a fresh `tagged.csv` ready for CubeCobra import.

#### Scenario: tagged.csv written after approval
- **WHEN** the user approves the suggested changes
- **THEN** `cubes/{short-id}/tagged.csv` is updated with cuts removed and adds included, ready for "Replace with CSV" upload

### Requirement: Balance metrics are informational
The skill SHALL report balance findings as observations. It SHALL NOT refuse to analyze or suggest changes because a cube has unconventional balance. A deliberately imbalanced cube (e.g., mono-color, combo-focused) is valid.

#### Scenario: Unusual cube analyzed without errors
- **WHEN** `/suggest-cube` runs on a cube with 90% blue cards
- **THEN** the skill notes the color skew as a fact and asks the user if it is intentional before suggesting changes to correct it

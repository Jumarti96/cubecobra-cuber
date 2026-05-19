## ADDED Requirements

### Requirement: /build-deck skill interviews the user and builds a 40-card cube deck
The skill SHALL interview the user (which cube, strategy/archetype, colors, power level, any restrictions), load `enriched.json` + `tagged.csv`, and construct a 40-card deck drawn exclusively from cards in that cube. Every card recommendation SHALL cite oracle text from enriched.json.

#### Scenario: Deck built from cube
- **WHEN** the user runs `/build-deck obc` and answers interview questions (aggro, red-white, no restrictions)
- **THEN** the skill proposes a 40-card deck using only cards present in `cubes/obc/enriched.json`

#### Scenario: Card not in cube proposed
- **WHEN** either the Proposer or Challenger references a card not in enriched.json
- **THEN** this is treated as a self-grill violation: the card MUST be removed from the proposal before the deck is presented to the user

### Requirement: Iron rule — verify via oracle text
The skill instructions SHALL state: "NEVER assume what a card does. All slot justifications MUST cite oracle text from enriched.json. If a card's oracle text does not support its stated role, it must be replaced."

#### Scenario: Oracle text cited in justification
- **WHEN** the Proposer defends including "Lightning Bolt" as removal
- **THEN** the Proposer cites: "Oracle text: 'Lightning Bolt deals 3 damage to any target.' — justifies removal role."

### Requirement: Self-grill gate (hard gate before presenting to user)
Before presenting the final deck, the skill SHALL run two parallel subagents: Proposer and Challenger. The gate MUST complete before any deck is shown to the user.

**Proposer responsibilities:**
- Defend the 40-card list for strategy coherence, curve, and mana base
- Cite oracle text for each card's assigned role
- Push back on Challenger challenges only when citing oracle text or quantitative argument

**Challenger responsibilities:**
- Verify every card is present in enriched.json (hard check)
- Confirm oracle text supports the card's stated role
- Check color pip requirements vs. the proposed mana base
- Ask "Is there a better card in this cube for this slot?" (check enriched.json)
- Validate the cube has enough density to support the stated archetype (use tag counts from tagged.csv)

#### Scenario: Self-grill catches out-of-cube card
- **WHEN** the Proposer suggests a card not in the cube
- **THEN** the Challenger flags it, the Proposer removes it, and the replacement must also be from the cube

#### Scenario: Self-grill catches oracle text mismatch
- **WHEN** the Proposer assigns a card to a role its oracle text doesn't support
- **THEN** the Challenger cites the oracle text and the card is replaced or re-assigned

### Requirement: Deck written to cubes/{id}/decks/
On user approval, the skill SHALL write the final deck to `cubes/{short-id}/decks/{deck-name}.json` using the deck schema defined in the cube-data-model spec.

#### Scenario: Deck saved on approval
- **WHEN** the user approves the final deck list
- **THEN** the skill writes the deck JSON and prints the path

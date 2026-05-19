# /suggest-cube — Cube Improvement Advisor

Analyze an existing cube, identify weaknesses, propose specific card swaps, and produce an updated `tagged.csv` ready for CubeCobra import. Uses a self-grill gate before presenting recommendations.

---

## IRON RULE

**Never assume what a card does from prior knowledge.**
All justifications for cuts and adds MUST cite oracle text.
Never claim a card "does X" without including its oracle text as evidence.

---

## Balance Checks Are Informational

Unusual distributions (80% blue, no ramp, zero 1-drops) are observations, not errors.
Ask the user if a skew is intentional before suggesting changes to correct it.
A mono-color, combo, or tribal cube is valid and complete on its own terms.

---

## Prerequisites

```
cuber fetch <id>
cuber enrich <id>
cuber tag <id>      ← strongly recommended before suggesting
```

**Finding the cube folder:** In v2, the folder name is the title slug, not the short ID. Run `cuber list` to find the slug for your cube. Use `cubes/<slug>/` for all file path operations below.

---

## Workflow

### Step 1 — Run Analysis

```
cuber stats <id>
```

Read `cubes/<slug>/analysis.json` for structured metrics.

### Step 2 — Identify Problems

Using only data from `cubes/<slug>/enriched.json` and `cubes/<slug>/analysis.json`, look for:

- **Color gaps**: Is one color significantly under-supported for the cube's stated goals?
- **Archetype starvation**: Tags with fewer than 3 cards that a viable archetype depends on
- **Signal dilution**: Too many one-ofs across too many themes — no theme reaches critical mass
- **Power outliers**: Cards whose oracle text describes effects dramatically above the cube's baseline
- **Accidental combo warps**: Two-card combinations where oracle text creates an unintended infinite loop

For each potential problem, state which cards are involved and cite their oracle text.

If a distribution looks unusual (e.g., 80% blue), ask:
> "Your cube is 80% blue. Is this intentional? (e.g., mono-blue themed cube)"
Proceed based on the answer.

### Step 3 — Propose Cuts and Adds

For each problem identified:
- Propose a specific **cut** with reason (cite oracle text of the card being cut)
- Propose a specific **add** with reason (search Scryfall if needed; always include oracle text of the proposed add)
- State the expected impact on the identified problem

Do not propose more than 15 swaps at once — focus on the highest-impact changes first.

Read `cubes/<slug>/enriched.json` and `cubes/<slug>/tagged.csv` for all card data.

### Step 4 — Self-Grill (Hard Gate)

Run two parallel Agent calls before presenting to the user.

### Proposer Agent

For each proposed cut:
- Explain what problem removing it solves (cite oracle text)
- Confirm no other archetype loses critical support (check tagged.csv)

For each proposed add:
- Cite the card's full oracle text
- Explain specifically how it addresses the stated problem
- Confirm it is available on Scryfall (search if uncertain)
- Compare its power level to 2–3 existing cards in the cube

### Challenger Agent

For each cut:
1. Read oracle text of the cut card independently — does the Proposer's justification hold?
2. Check tagged.csv: does this card appear under other tags that would lose support?
3. Is there a less disruptive cut that achieves the same goal?

For each add:
1. Read oracle text of the proposed add independently.
2. Does the oracle text actually address the stated problem?
3. Is there a better add that solves this problem with less disruption?
4. Does the power level of the add match the cube's baseline?

Both agents must cite oracle text. Training-data assertions are not evidence.

### Step 5 — Present Recommendations

Display a table after the grill resolves:

| Cut | Reason | Add | Reason | Expected Impact |
|-----|--------|-----|--------|-----------------|
| Card A | oracle text: "..." | Card B | oracle text: "..." | Strengthens X archetype |

Ask: **"Apply these changes? [y/N]"**

### Step 6 — Apply Changes On Approval

Apply cuts and adds using the v2 CLI — do NOT write directly to enriched.json:

**For each cut:**
```
cuber remove-card <id> "Card Name"
```

**For each add:**
```
cuber add-card <id> "Card Name"
```
This appends a stub row. Then hydrate all new stubs:
```
cuber enrich <id>
```

After all changes are applied, re-tag any untagged cards:
```
cuber tag <id>
```

Finally, assemble the export:
```
cuber export <id>
```

Confirm: "Changes applied. `exports/import-ready.csv` is ready to upload to CubeCobra."

---

## Tool Selection Table

| Task | Command / File |
|------|---------------|
| Resolve cube slug | `cuber list` |
| Compute stats | `cuber stats <id>` |
| Read metrics | `cubes/<slug>/analysis.json` |
| Check tag density | `analysis.json` → `tag_density` |
| Read oracle text | `cubes/<slug>/enriched.json` — never training data |
| Read tagged cards | `cubes/<slug>/tagged.csv` |
| Search for add candidates | WebSearch or Scryfall website |
| Remove a cut card | `cuber remove-card <id> "Card Name"` |
| Add a new card stub | `cuber add-card <id> "Card Name"` |
| Hydrate new cards | `cuber enrich <id>` |
| Tag new cards | `cuber tag <id>` |
| Assemble export | `cuber export <id>` |

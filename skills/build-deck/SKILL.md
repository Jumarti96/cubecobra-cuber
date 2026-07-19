---
name: build-deck
description: Build a deck from a locally cached cube in any supported format
---
# /build-deck — Cube Deck Builder

Build a deck from a locally cached cube in any supported format. Cards must come only from the cube pool. A self-grill gate runs before the final list is shown. The deck is saved as deck.json, deck.tsv, deck.mwDeck, and analysis.md in a per-deck subfolder when you confirm.

**You build the deck.** You investigate the cube, build, and repair. A two-agent self-grill audits the finished list before you show it to the user.

Read the IRON RULE and the counts principle before doing anything — they bind every phase.

---

## IRON RULE — Oracle Text Or It Didn't Happen

**Never assume what a card does from prior knowledge.**
Every inclusion and justification MUST cite `oracle_text` from the working pool cache (`_workspace/<run-token>/working_pool.json`). The Phase 9 agents cite oracle text from the grill input bundle (`_workspace/<run-token>/grill_input.json`).
If the oracle text does not support the stated role, the card must be replaced.

---

## The Counts Principle — Counts, Not Adjectives

No card is good or bad in isolation. Any claim that a card is weak, strong, a trap, a must-include, or "not worth the slot" **when its value depends on how many other cards qualify** must be stated as an actual count against **this** deck's list — a numerator and a denominator — not as an adjective.

> WEAK:  "This cost reducer only reduces generic mana, so it's marginal here."
> STRONG: "This cost reducer reduces generic mana; 16 of the 24 nonland cards in this list have a generic component. INCLUDE."

This binds every card whose value is a function of how many others qualify: cost reducers, tribal and type-matters payoffs, storm and spell-count triggers, graveyard counts, devotion, threshold, metalcraft, delirium, domain, affinity. Compute the count from the list you actually built; if the list changes, recount.

---

## Prerequisites

```
cuber fetch <id>
cuber enrich <id>
cuber tag <id>       ← required; taxonomic_profile drives pipeline discovery
```

Phase 2 builds/loads the **cube dossier** (`cuber dossier <id>`) for you — it does not need to be run by hand first.

---

## Supported Formats

| Format | Deck Size | Commander | Sideboard default |
|--------|-----------|-----------|-------------------|
| `40-card` | 40 cards | No | 8 cards |
| `60-card` | 60 cards | No | 15 cards |
| `commander-60` | 61 cards (60 + 1 commander) | 1 or 2 partners | Optional |
| `commander-100` | 101 cards (100 + 1 commander) | 1 or 2 partners | Optional |

---

## Reference Files (read at phase start)

Detailed mechanics live in `references/` under this skill's base directory. **At the start of each phase listed below, read the named file before executing that phase.** The rules in this file always apply; the references hold the JSON shapes, tables, and format specs.

| File | Read at |
|------|---------|
| `references/workspace-and-pool.md` | Phase 0 start |
| `references/discovery.md` | Phase 2 start (covers Phases 2–4) |
| `references/build.md` | Phase 5 start (covers Phases 5–6b) |
| `references/challenger-template.md` | Phase 9 start |
| `references/render-and-save.md` | Phase 10 start (covers Phases 10–11) |

---

## Phase 0: Card Pool Definition

### Workspace Setup

Run at the very start of Phase 0, before any user prompts or analysis:

**Read `references/workspace-and-pool.md` now.** Mint the run token by running the command in its steps 1–3 — it atomically creates `_workspace/<run-token>/`, handles collisions by retrying, and must never be done by hand or with `exist_ok=True`.

Every file this run writes — the working pool cache, the grill input bundle, every temp Python script, every intermediate audit/dump — goes inside `_workspace/<run-token>/`, never at `_workspace/` root and never at the repo root. Concurrent runs each get their own token, so they can never read or overwrite each other's files.

Do not delete anything outside your own `_workspace/<run-token>/` directory.

### Pool Restrictions

Ask the user (in natural language):
> "Are there any pool restrictions? For example: up to 2 copies of commons and uncommons, only certain rares, or specific cards to exclude. Press Enter to use the full cube mainboard."

If the user provides no restrictions, proceed immediately with the full cube mainboard.

Infer the `card_pool_rules` object from the answer — the JSON shape and field semantics are in `references/workspace-and-pool.md`.

**Display the inferred `card_pool_rules` and ask the user to confirm before proceeding.** If the user corrects the inferred object, update it and re-display. Proceed only after explicit confirmation.

Once confirmed, pass `card_pool_rules` to `cube_search.load_merged_pool(id, card_pool_rules=...)`. All subsequent phases use this filtered pool exclusively.

### Working Pool Cache

After loading the filtered pool, write `_workspace/<run-token>/working_pool.json`. Track this path — all subsequent phases reference it. (Per-card field lists, the load-bearing `tags`/`mana_cost` note, and the `export_meta.json` capture for Phase 11 are in `references/workspace-and-pool.md`.)

**Do not read `enriched.json` after Phase 0 completes.** All card data for Phases 2–9 comes from the working pool cache and the bundle derived from it.

---

## Phase 1: Interview

Use AskUserQuestion to collect decisions before any analysis. Ask in a single multi-part message where possible.

**Required:**
1. **Cube** — short ID or slug (or list available cubes from `cubes/*/meta.json`)
2. **Format** — 40-card / 60-card / Commander-60 / Commander-100
3. **Colors** *(optional)* — any color preference? Default is pool-derived; say "surprise me" or leave empty to let strategy discovery determine colors from the winning pipeline
4. **Intent** — how do you want to play? Choose one:
   - `Competitive` — maximize win consistency, interaction density
   - `Experimental` — unusual synergies, high variance, cross-archetype overlap
   - `Fun / Niche` — most distinctive or uncommon win condition in the pool
   - `Specific Constraint` — describe your constraint (e.g., "I want to play around Grapeshot")
5. **Power level** — casual / unpowered / powered / competitive

**Optional (ask but accept empty):**
6. **Sideboard size** — accept format default or specify

Note: card pool restrictions were collected in Phase 0. Do not re-ask them here.

---

## Phase 2: Deck Identity (Discovery)

Load card data from the working pool cache: `_workspace/<run-token>/working_pool.json`. Do not call `cube_search.load_merged_pool` or read `enriched.json`.

### Step 0: The Cube Dossier

**Run this first, before discovery.** The dossier is the deck-independent truth about the cube — colour distribution, mana infrastructure (with per-pair fixing counts), structural censuses (rituals, sweepers, sacrifice outlets, cost reducers, tutors), tribal rosters, and a threat profile of what the cube's *other* decks do. It warm-starts your investigation and is what the sideboard is built against.

```
cuber dossier <id>
```

This writes/loads `cubes/<slug>/dossier.json` and prints a summary. It is **cached per cube** and invalidated automatically when the cube changes, so on a repeat run it is nearly free. Pass `--rebuild` to force recomputation.

**Read `references/discovery.md` now.** It holds the census key table and its reading caveats, the fixing score derivation, the colour-count escalation rules, the optional interaction-chain aid, pipeline discovery, splash evaluation, and commander selection.

**Do not re-derive census facts by hand.** If you find yourself sweeping the pool for rituals, counting duals, or tallying a tribe, the answer is already in the dossier. But **never trust a 0-match as an impossibility** (`census_caveat`), and **verify each named dual/manland against its oracle text** before trusting the fixing count — a colourless manland is not colored fixing.

### Step 2: Pipeline Discovery

Run **Pipeline Discovery** per `references/discovery.md`: find payoff candidates, validate cluster support against the viability threshold, and build a ranked shortlist of 3–5 viable pipelines, each retained as a structured object with an oracle-grounded `thesis` (`kill_mechanism`, `goldfish_turn`, `default_role`).

---

## Phase 3: Strategy Selection

Present the shortlist to the user. For each pipeline entry display:
- Payoff card name and its synergy cluster(s)
- Supporting card count (Enabler/Fodder + Engine/Outlet in the cluster)
- Color identity of the pipeline's core cards
- Fixing score for that color combination

**Highlight the top recommendation** (marked clearly, based on intent ranking). If the user had no color preference in Phase 1, show the recommended pipeline's color identity as the suggested default.

Ask the user to accept the top recommendation, pick a different pipeline from the shortlist, or describe their own constraint (you construct and validate a pipeline anchored to it).

Lock the selected pipeline. **Carry the full shortlist forward — it will be used for re-evaluation in Phase 9 if needed.** The shortlist is never recomputed.

### Splash Evaluation

Run the deterministic splash filter in `references/discovery.md`. It sets `splash_colors` and the bounded `splash_candidates` list (at most 3 names per splash colour) — a splash colour never admits its whole colour, only these named cards.

---

## Phase 4: Commander Selection (Commander formats only)

Skip for 40-card and 60-card formats. Follow the procedure in `references/discovery.md`. The union of the selected commanders' `color_identity` becomes the binding colour constraint for all non-land cards.

---

## Phase 5: Deck Build

You build the deck. **Read `references/build.md` now.** It holds the seven-step build procedure, the slot-allocation table, the land-count modifiers, the pip-source math, the lightweight sweep shape, and the Phase 6b invocation.

### Phase 5A — Lightweight Sweep

Before committing the list, record a short sweep so no strong card is silently skipped and the analysis can show what was considered:
- **INCLUDE candidates** — cards you are building from, each with a one-line oracle-grounded reason scoped to this pipeline.
- **Considered but excluded** — a *bounded* list (not every pool card) of cards a reader would expect you to run but you rejected, each with a one-line mechanism reason. Count-dependent rejections obey the Counts Principle.

The considered-but-excluded entries become the `### CARDS CONSIDERED BUT EXCLUDED` section of the analysis. The sweep shape is in `references/build.md`.

### Phase 5B — Build

Build from the INCLUDE candidates. For each card, its oracle text (from the working pool cache) must support the role you assign; if it does not, the card does not go in.

Follow the seven numbered steps in `references/build.md`: **1 CLASSIFY → 2 ALLOCATE SLOTS → 3 LAND COUNT → 4 MANA SOURCES → 5 FILL → 6 COUNT-DEPENDENT VERDICTS → 7 record `build_output`**.

### Phase 5C — Pre-flight Validation (deterministic)

Write `_workspace/<run-token>/_tmp_validate_build.py` and run the light checks in `references/build.md` (deck size, exact-name membership, copy limits, colour identity, splash cap). Every check is a string or number comparison. Fix any failure directly, then re-run until all pass. Do not proceed with a failing check.

---

## Phase 6: Mana Audit Gate

Convert the mainboard into card dicts (join `name` against the working pool cache).

Run `deck_audit.mana_audit(deck_cards, format, commander_cards, core_colors=core_colors, splash_colors=splash_colors)`.
Display the report using `deck_audit.format_audit_report(audit)`.

**If audit result is FAIL:**
- Adjust land count toward the recommended target
- Re-balance producing lands if a color gap > 15pp exists
- Replace non-producing utility lands with on-color duals from the pool
- Re-run the audit after adjustments; log all swaps made

**If audit result is WARN:** note the issue, proceed without blocking.
**If audit result is PASS:** proceed.

Do not show the deck to the user or spawn the grill until the audit is at least WARN.

---

## Phase 6b: Structural Gate

Run the structural checks (the deck-building methodology, mechanized — thresholds live in `cuber/deck_checks.py`, never re-derive them by hand). The invocation snippet, the `role_counts` reliability-weighting rules, and the `coverage_declaration` construction are in `references/build.md`.

**Gate tiers:**
- **HARD — treat like a mana-audit FAIL:** `assembly` (an engine role's P(seen by thesis turn) < 0.75 — either add functional copies, or the thesis turn was optimistic: revise it and say so) and `coverage` (missing class, phantom card name, empty concession). Repair and re-run. Assembly counts **reliability-weighted** copies: a conditional functional copy is declared at a weight below one with its mechanism, never counted as a full copy.
- **WARN-tier — respond, don't rebuild:** `curve` and `goldfish`. Each WARN flag gets one line in `build_output.structural_responses` stating the mechanism-grounded reason the deviation is accepted.

**Also record `build_output.failure_modes`** — one mechanism-grounded line each for **flood** (what do excess lands do here?), **screw** (which hands are keepable on 2 lands?), and **decapitation** (what is the line when the key piece is answered on sight?).

Store the full report as `build_output.structural_checks`. It ships in the grill bundle.

---

## Phase 7: Sideboard

Skip if the user opted out or if the format does not normally use sideboards.

Default sizes: 8 (40-card), 15 (60-card), custom (commander).

A sideboard answers the **REST OF THE CUBE**, not your own deck. Work from `dossier.threat_profile` (what other decks in this cube actually do) and the rest of the cube's cards:
- **Hate cards**: match real threat classes in this cube (graveyard, artifacts, sweepers…) — cite oracle text for each, and state which threat class it answers
- **Flex slots**: cards that improve in certain matchups; explain what they answer and when to board them in
- Note any threat class the pool gives your colours no answer to

All sideboard cards come from the pool and count against combined copy limits.

---

## Phase 8: Grill Input Bundle

Write `_workspace/<run-token>/grill_input.json`.

The bundle contains:
- `deck`: array of all mainboard + sideboard cards, each with `name`, `oracle_text`, `colors`, `color_identity`, `cmc`, `type_line`, `rarity`, `role` (from Phase 5), and `board`
- `audit`: the mana audit result object from Phase 6
- `card_pool_rules`: the confirmed pool rules object from Phase 0
- `restrictions_checklist`: the compliance checklist from Phase 5
- `build_output`: your recorded derivation — `macro_archetype`, `deck_identity`, `thesis_turn`, `default_role`, `slot_allocation`, `land_math`, `pip_math`, `coverage`, `failure_modes`, `structural_checks`, `structural_responses`. This lets the grill audit the **derivation**, not just the list.
- `validation_report`: the Phase 5C check results (all PASS by the time you get here)
- `working_pool`: the full working pool array from the cache — the grill's evidence base and what its absence audit scans
- `dossier`: the cube dossier (for the threat-profile sideboard and interaction checks)

Both Phase 9 agents read only this file — never `enriched.json`, the working pool cache, or any other cube data file.

---

## Phase 9: Self-Grill (Hard Gate)

**Read `references/challenger-template.md` now.** Spawn the two agents it describes — a Proposer that defends every card with an oracle quote, and a Challenger that attacks the deck independently and runs the full checklist (membership, oracle, restrictions, identity fit, better alternatives, proportional validation, sideboard cohesion, mana re-run, **derivation audit**, **absence audit**, and pipeline viability). Neither agent sees the other's output during generation.

### Resolve Grill (you adjudicate)

You built this deck, so you defend it and judge the Challenger's findings. The discipline is in *how*:

1. **Respond to every finding explicitly** — accept or reject, with an oracle-grounded reason or a recount. Silent dismissal is prohibited.
2. **Hard findings force a repair, never a rebuttal:** a legality violation (a Phase 5C check), a mana-audit regression (audit falls below WARN), a structural-gate HARD failure, or a count that fails to reproduce.
3. **Soft findings** (a card-swap opinion, an absence, a proportional-band deviation, a role-text quibble) you may accept or reject on the merits — verify each claim against oracle text first. But an absence finding naming a card whose oracle-grounded count you cannot rebut is a finding you accept.
4. **Repair the deck yourself.** Apply accepted findings, recount any count-dependent verdict whose denominator moved, then re-run the Phase 5C validator, the Phase 6 audit, and the Phase 6b gate on the result.

Final list must satisfy: every card in the cube + oracle text supports every role + audit ≥ WARN + Phase 5C all-PASS + Phase 6b HARD gates pass.

### Re-evaluation Path

Trigger, and only this trigger: the Challenger states **"This pipeline cannot achieve its stated win condition with the available card pool."** (Not a mana issue. Not a ratio issue. Not a card-swap issue.) Verify the claim against the pool's oracle text; if it stands:

1. Log the rejection: `{ "payoff_card": "<name>", "verdict": "PIPELINE_NOT_VIABLE" }`.
2. Select the **next pipeline** from the Phase 3 shortlist. Do NOT re-run discovery or Phase 2.
3. Rebuild from Phase 5, re-running Phases 6–9.

If the shortlist is exhausted:
> "All shortlisted pipelines were rejected. Options: (1) Restart Phase 0 to adjust pool rules. (2) Lower the viability threshold and rerun discovery."

Wait for user guidance before proceeding.

---

## Phase 10: Present Final Deck

Display the deck using the enforced format. **Section order is strict — do not reorder.**

**Read `references/render-and-save.md` now.** It holds the display template, the format rules (including: **no Scryfall links, no external links of any kind, card names as plain text everywhere**), and the Phase 11 file specs.

**Header counts are derived, then verified.** Every section header carries a count (`## MAINBOARD (24 spells + 16 lands = 40)`, `### CREATURES (13)`). Compute each from the deck arrays at render time — never hand-write it, never copy it from a previous version. After writing `analysis.md`, re-parse it and confirm every section's summed `Qty` matches its header and that the file contains zero occurrences of `scryfall`.

Ask: **"Save this deck? [y/N]"**

---

## Phase 11: Save

On confirmation, prompt for a deck name if not already provided. Sanitize to a filesystem-safe slug (lowercase, alphanumeric + hyphens).

All four files go into a single subfolder: `cubes/<id>/decks/<name>/`

File-by-file specs — the `deck.json` schema, `deck.tsv` columns, `exporter.write_mwdeck`, and the `analysis.md` frontmatter and section structure — are in `references/render-and-save.md`.

Confirm all four paths:
```
Saved:
  cubes/<id>/decks/<name>/deck.json
  cubes/<id>/decks/<name>/deck.tsv
  cubes/<id>/decks/<name>/deck.mwDeck
  cubes/<id>/decks/<name>/analysis.md
```

---

## Tool Selection Table

| Task | Tool / File |
|------|-------------|
| Load card pool (with pool rules) | `cube_search.load_merged_pool(id, card_pool_rules=...)` — Phase 0 only |
| **Build / load the cube dossier** | `cuber dossier <id>` — Phase 2 Step 0. Cached per cube; `--rebuild` to force |
| **Mana infrastructure, fixing score** | `dossier.mana_infrastructure.duals_by_pair` — use the `free` count. Verify named lands against oracle before trusting it |
| **Rituals, sweepers, sac outlets, tutors** | `dossier.structural_census` — but a 0-match proves nothing: see `census_caveat` |
| **What the sideboard answers** | `dossier.threat_profile` + the rest of the cube |
| Filter by color/type/tag/CMC | `cube_search.search_pool(pool, color_identity=core_colors, splash_color_identity=splash_colors, ...)` |
| Query Payoff candidates | Filter working pool cache by `taxonomic_profile.structural_roles` containing `"Payload/Payoff"` |
| Query synergy support | Filter working pool cache by `taxonomic_profile.synergy_clusters` overlap + `"Enabler/Fodder"` or `"Engine/Outlet"` in `structural_roles` |
| Find commander candidates | `commander_finder.find_commanders(id, color_identity)` |
| Display commander table | `commander_finder.format_commanders_table(candidates)` |
| Run mana audit | `deck_audit.mana_audit(deck_cards, format, commander_cards, core_colors=core_colors, splash_colors=splash_colors)` |
| Display audit report | `deck_audit.format_audit_report(audit)` |
| **Structural gate (curve / assembly / goldfish / coverage)** | `deck_checks.run_structural_checks(...)` + `deck_checks.format_checks_report(report)` — Phase 6b. Thresholds live in `cuber/deck_checks.py`; NEVER re-derive them by hand |
| Verify card exists | Search working pool cache by exact name — never training data |
| Read oracle text | `card.oracle_text` from the working pool cache (you) or the grill bundle (Phase 9 agents) — never training data |
| Write deck files | Write tool → `cubes/<id>/decks/<name>/deck.json` and `deck.tsv`. `exporter.write_mwdeck()` → `deck.mwDeck`. `exporter.write_deck_analysis_md()` → `analysis.md` |
| Write a temp Python script | `_workspace/<run-token>/_tmp_<name>.py` — never to the repo root or shared `_workspace/` root |

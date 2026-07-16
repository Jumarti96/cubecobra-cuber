---
name: build-deck
description: Build a deck from a locally cached cube in any supported format
---
# /build-deck — Cube Deck Builder

Build a deck from a locally cached cube in any supported format. Cards must come only from the cube pool.

**You build the deck.** You investigate the cube, sweep the legal pool with fresh eyes, build, and repair. Deck isolation — the property that every deck is evaluated as if it were the first deck ever built — is delivered by three guards, not by outsourcing the build:

1. **The Fresh-Eyes Sweep (prevention):** before building, every card in this deck's legal pool gets a recorded, fresh, one-line verdict scoped to THIS deck. A card cannot be skipped because it was rejected for a previous deck.
2. **The cold Challenger (detection):** an independent, no-prior-context agent audits the finished deck from a hashed bundle — including an absence audit that asks "what strong pool card is missing?" from a context that has never seen another deck.
3. **The analysis firewall:** excluded-card content in the output is generated from the sweep, never free-authored, and the analysis may not reference any other deck.

The deck is saved as deck.json, deck.tsv, deck.mwDeck, sweep.json, and analysis.md in a per-deck subfolder when you confirm.

Read IRON RULES 1–3 before doing anything. They are the point of this skill, not preamble.

---

## IRON RULE 1 — Oracle Text Or It Didn't Happen

**Never assume what a card does from prior knowledge.**
Every inclusion and justification MUST cite `oracle_text` from the working pool cache (`_workspace/<run-token>/working_pool.json`). The Challenger cites from `grill_input.json`.
If the oracle text does not support the stated role, the card must be replaced.

---

## IRON RULE 2 — Deck-Scoped Verdicts Never Cross a Deck Boundary

A card-quality verdict is a property of the **pair (card, list)** — never of the card alone. The thing that must be isolated is **the deck**, not the builder. You build decks with a warm context, and after deck 1 that context inevitably contains deck 1's verdicts. This rule is how those verdicts are kept from corrupting deck 2:

| Tier | Scope | May influence a later deck? | Why |
|------|-------|-----------------------------|-----|
| **Cube facts, interactions, pool limits** | the cube | **YES** — via the dossier | True or false independent of any deck. Verifiable from oracle text or a pool count. |
| **Card-quality verdicts** | the (card, list) pair | **NEVER** | Stale the moment the list changes. The Fresh-Eyes Sweep exists to force re-derivation. |
| **Grill findings, repair lessons, build narratives** | one deck's run | **NEVER** | Deck-scoped by construction. |

> "Dralnu's Crusade makes all Goblins Zombies, so Deadapult can sacrifice any Goblin." — a **fact about the cube**. Travels (via the dossier).
> "Deadapult isn't worth a slot." / "Helm of Awakening is weak here." — a **verdict about one list**. Never travels.

**Concretely, this binds you three ways:**
1. **In the sweep and build:** every verdict is formed fresh against THIS deck's pipeline and list. You may not skip, shortcut, or copy a verdict because you "already know" the card from an earlier deck — the reason recorded in the sweep must be derivable from this deck's bundle alone.
2. **In prompts and bundles:** nothing deck-scoped is ever authored into the Challenger's prompt or smuggled into the dossier. See the prompt protocol below.
3. **In the output:** the `## ANALYSIS` body may not reference another deck, another build, or reasoning formed while building one. Excluded-card content is generated from this deck's sweep. See Phase 10.

**The dossier is frozen before the first deck is built.** It is therefore *structurally incapable* of containing a finding about any deck, and it is byte-identical for every deck in the session. That is the guarantee — not a promise you make, but a property of *when* the file is written. (Newly discovered cube facts are written back only at session end — Phase 12 — never mid-session.)

### Prompt protocol (binding for every spawned agent)

All knowledge travels in the **bundle**. None is ever authored into a prompt. The Challenger is spawned from the template in `references/challenger-template.md`.

1. **Verbatim only.** Copy the template character for character. The ONLY text you may change is the value substituted into a declared `{{PLACEHOLDER}}` slot.
2. **No additions.** You MUST NOT add a single sentence, clause, bullet, heading, preamble, or postscript. Not a summary. Not a "note". Not a "for context…". Not a "focus especially on…". Not a greeting.
3. **No card names in prompts.** The template has no card-name placeholder. You may never *tell* the Challenger which card to attack, defend, or "pay attention to".
4. **No analysis in prompts.** Your reasoning, math, win-condition narrative, damage counts, curve claims, verdicts and conclusions never appear in a prompt. If a number matters, it is in the bundle or the agent derives it.
5. **No priors.** You MUST NOT carry a finding from a previous deck, a previous attempt, or another agent's output into a prompt.
6. **No leading questions.** A question that contains its own answer is a prohibited addition under (2), (3) and (4).

If the Challenger needs information no placeholder covers, that information belongs in the **bundle** — as a machine-derived field, or as a dossier entry that satisfies the admissibility rule below. Never smuggle it into the prompt.

### Dossier admissibility — mechanisms and limits, no conclusions

Anything you author into the dossier MUST be checkable against oracle text or a pool count.

- **Admissible:** "8 of the 10 Goblins are mono-red." "Card A's oracle says X, card B's says Y, so A enables B."
- **Inadmissible:** any word that ranks a card — good, bad, weak, strong, a trap, a must-include, "not worth the slot", "don't bother with".

State the mechanism and the count. The conclusion belongs to whoever owns a list.

**The census caveat is part of the dossier and it binds you too:** every `pool_limits` entry is a regex probe result. A probe that matched 0 cards proves nothing — no-match is not does-not-exist. Never treat a 0-match line as a hard constraint; verify against oracle text before relying on it.

**The chains caveat is its authored-layer twin:** `interaction_chains` is a known-incomplete list. A chain proves an engine exists; the absence of a chain proves nothing. Derive compositions from oracle text first — the chain list is a floor under what the cube contains, never a ceiling.

**Pre-spawn self-check (mandatory).** Before every spawn, diff your prompt against the template in `references/challenger-template.md`. If any character outside a `{{PLACEHOLDER}}` differs, discard and rebuild. Then echo to the user only the placeholder table you substituted:

```
Spawning: Challenger
  {{GRILL_INPUT_PATH}} = _workspace/<run-token>/attempt-1/grill_input.json
  {{EXPECTED_HASH}}    = 9f2c…
Template: verbatim, 0 additions.
```

---

## IRON RULE 3 — Verdicts Are Counts, Not Adjectives

No card is good or bad in isolation. Any claim that a card is weak, strong, a trap, a must-include, or "not worth the slot" is **invalid** unless stated as a count against the actual list being built.

> INVALID: "This cost reducer only reduces generic mana, so it's weak here."
> VALID:   "This cost reducer reduces generic mana. 16 of the 24 nonland cards in this list have generic in their mana cost. INCLUDE."

A numerator and a denominator are both required, and the denominator is always **this** deck's list. If the list changes, the count is stale and MUST be recomputed.

**The count lives in exactly one place — a `quantitative_verdicts` entry — and it is computed, not typed.** The numerator and denominator are return values of `cuber.deck_counts` (Phase 5C step 6), and Phase 5D recomputes them from the same code. The VALID example above states the count in prose for readability *here*; in the actual build that count is the verdict's `numerator`/`denominator` (18 / 24 with a `generic_reducible` spec), and the `claim`, the card's `role`, and the sweep `reason` name the mechanism in words with **no count digits**. One computed copy of every number means no copy can go stale.

This binds every card whose value is a function of how many other cards qualify: cost reducers, tribal and type-matters payoffs, storm and spell-count triggers, graveyard counts, devotion, threshold, metalcraft, delirium, domain, affinity.

---

## The Isolation Model

| Role | Who | Context | Duties |
|------|-----|---------|--------|
| Builder | **You** (the orchestrator) | warm — full cube investigation | Sweep, build, repair, adjudicate grill findings, render output |
| Challenger | Cold agent (TEMPLATE D) | reads `grill_input.json` only, hash-gated | Hard checks, exhaustive per-card oracle verification, quantitative recounts, absence audit |

**Why you build:** a warm context that has investigated the cube builds better and ~5x faster than a cold agent that must re-derive everything per deck. That was measured, both directions.

**Why the Challenger is cold:** it is the contamination detector. Its value is precisely that it has never seen another deck, another attempt, or your reasoning. It is spawned once per grill round, single-shot, never resumed, never re-messaged. Feedback to it travels only by writing a new hashed bundle and spawning a brand-new instance.

**Adjudication:** you built this deck, so you defend it and judge the Challenger's findings — for THIS deck, your judgment is exactly the deck-scoped judgment IRON RULE 2 permits. But **hard findings are non-negotiable** (see Phase 9 Resolve): a legality violation, a mana-audit regression, a count that fails to reproduce, or the Re-evaluation trigger always forces action. You may never wave one through.

---

## Multi-Deck Sessions

This is where the guards earn their keep. If the user asks for a second deck in the same conversation:

1. **Mint a NEW run token** and restart at Phase 0's pool rules. You may not reuse the previous token, its bundles, or its hashes.
2. **Reuse the dossier — unchanged.** It was frozen before deck 1 and is deck-independent by construction. Every deck in the session embeds the *same* `dossier_sha256`. Do not regenerate it, do not amend it mid-session, and above all do not "update it with what we learned." (New cube facts are written back at session end — Phase 12.)
3. You may skip re-asking Phase 1 only if the user explicitly says "same settings" — and even then the answers are re-serialized **from the user's own words**, never from your recollection.
4. **Run the Fresh-Eyes Sweep in full, again.** This is not optional and not skippable for cards you "remember". The sweep is the mechanism that forces a card rejected for deck 1 to be re-evaluated from scratch for deck 2. Every sweep reason must be derivable from this deck's pipeline and pool alone.
5. **Nothing deck-scoped crosses.** No card verdict, no "we learned that X is a trap", no grill finding, no repair lesson — not into the sweep, not into a bundle, not into the analysis.

**The failure this prevents, concretely:** a cost reducer correctly cut from deck 1 (whose kill was an activated ability the reducer cannot discount) must be re-evaluated from scratch for deck 2, where it may discount most of the list. The verdict was never a property of the card — only of the pair (card, list).

---

## Prerequisites

```
cuber fetch <id>
cuber enrich <id>
cuber tag <id>       ← required; taxonomic_profile drives pipeline discovery
cuber dossier <id>   ← cube facts; cached per cube, run once (Phase 2 does this for you)
```

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

Detailed mechanics live in `references/` under this skill's base directory. **At the start of each phase listed below, read the named file before executing that phase.** The rules in this file always apply; the references hold the JSON shapes, tables, templates, and file-format specs.

| File | Read at |
|------|---------|
| `references/workspace-and-pool.md` | Phase 0 start |
| `references/discovery.md` | Phase 2 start (covers Phases 2–4) |
| `references/build.md` | Phase 5 start (covers Phases 5–6b) |
| `references/challenger-template.md` | Phase 9, immediately before spawning |
| `references/render-and-save.md` | Phase 10 start (covers Phases 10–11) |

## Phase 0: Card Pool Definition

### Workspace Setup

Run at the very start of Phase 0, before any user prompts or analysis:

**Read `references/workspace-and-pool.md` now.** Mint the run token by running the command in its steps 1–3 — it atomically creates `_workspace/<run-token>/`, handles collisions by retrying, and must never be done by hand or with `exist_ok=True`.

Every file this run writes — the working pool cache, the sweep, the grill input bundle, every temp Python script, every intermediate audit/dump — goes inside `_workspace/<run-token>/`, never at `_workspace/` root and never at the repo root. Concurrent runs (yours or another session's) each get their own token, so they can never read or overwrite each other's files.

Do not delete anything outside your own `_workspace/<run-token>/` directory. A run may clean up only its own run directory when finished; never glob-delete across `_workspace/` — another run's in-flight files may live there.

### Pool Restrictions

Ask the user (in natural language):
> "Are there any pool restrictions? For example: up to 2 copies of commons and uncommons, only certain rares, or specific cards to exclude. Press Enter to use the full cube mainboard."

If the user provides no restrictions, proceed immediately with the full cube mainboard.


Infer the `card_pool_rules` object from the answer — the JSON shape and field semantics are in `references/workspace-and-pool.md`.

**Display the inferred `card_pool_rules` and ask the user to confirm before proceeding.**

If the user corrects the inferred object, update it and re-display. Proceed only after explicit confirmation.

Once confirmed, pass `card_pool_rules` to `cube_search.load_merged_pool(id, card_pool_rules=...)`. All subsequent phases use this filtered pool exclusively.

### Working Pool Cache

After loading the filtered pool, write `_workspace/<run-token>/working_pool.json`. The run token from Workspace Setup already guarantees uniqueness, so no deck-slug or extra timestamp is needed in the filename. Track this path — all subsequent phases reference it.

(Per-card include/exclude field lists, the load-bearing `tags`/`mana_cost` note, and the `export_meta.json` capture for Phase 11 are in `references/workspace-and-pool.md`.)

**Do not read `enriched.json` after Phase 0 completes.** All card data for Phases 2–9 comes from the working pool cache and the bundles derived from it.

### Attempt Directories

Per-attempt files live one level below the run token, so a stale file from one build attempt can never be read by a later one:

(Directory layout diagram in `references/workspace-and-pool.md`.)

`k` starts at 1 and is incremented **only** by the Phase 9 Re-evaluation Path.

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

**Run this first, before anything else in Phase 2.** The dossier is the deck-independent truth about the cube. It is what the Challenger will be given, it is what warm-starts your own investigation, and it is what makes a cold auditor competent instead of amnesiac.

```
cuber dossier <id>
```

This writes/loads `cubes/<slug>/dossier.json` and prints a summary. It is **cached per cube** and invalidated automatically when the cube changes (`card_count` + `fetched_at`) or when the census semantics change (`dossier_version`), so on a repeat run against the same cube this step is nearly free. Pass `--rebuild` to force recomputation.

**Read `references/discovery.md` now.** It holds the census key table and its reading caveats, the fixing score and colour-count escalation rules, the chain-authoring procedure and format, pipeline discovery, splash evaluation, and commander selection.

---

### Step 0b: Author the Interaction Chains (seed pass + freeze)

**This is the one part of the dossier no script can produce, and the part whose absence most damages a build.** Tags and cluster names cannot encode *"card A changes card B's type so card C can eat it"* — and an auditor that is never told will hold both halves of a combo and never connect them. This layer is also what the Challenger's absence audit sees: it can only ask "why isn't the High Tide engine here?" if a chain surfaces that engine.

Author the chains per the seed-pass / incremental-pass procedure and the strict chain format in `references/discovery.md`.

Then **freeze the dossier**: re-save it and compute its SHA-256. From here to the end of the session it is immutable. Every deck embeds this same `dossier_sha256`. You do not amend it after a deck is built — new chains discovered while building are queued for the Phase 12 session-end write-back, never added mid-session.

```
python -c "import hashlib; print(hashlib.sha256(open('cubes/<slug>/dossier.json','rb').read()).hexdigest())"
```

---

Then run **Step 2: Pipeline Discovery** per `references/discovery.md`: find payoff candidates, validate cluster support against the viability threshold, and build a ranked shortlist of 3–5 viable pipelines, each retained as a structured object with an oracle-grounded `thesis`.

---

## Phase 3: Strategy Selection

Present the shortlist to the user.

For each pipeline entry display:
- Payoff card name and its synergy cluster(s)
- Supporting card count (Enabler/Fodder + Engine/Outlet in the cluster)
- Color identity of the pipeline's core cards
- Fixing score for that color combination

**Highlight the top recommendation** (marked clearly, based on intent ranking). If the user had no color preference in Phase 1, show the recommended pipeline's color identity as the suggested default.

Ask the user to:
- Accept the top recommendation
- Pick a different pipeline from the shortlist
- Describe their own constraint (AI constructs and validates a pipeline anchored to it)

Lock the selected pipeline. **Carry the full shortlist forward — it will be used for re-evaluation in Phase 9 if needed.** The shortlist is never recomputed.


### Splash Evaluation

Run the deterministic splash filter in `references/discovery.md`. It sets `splash_colors` and the bounded `splash_candidates` list (at most 3 names per splash colour) — **`splash_candidates` is what bounds `legal_pool`**; a splash colour never admits its whole colour.

---


## Phase 4: Commander Selection (Commander formats only)

Skip for 40-card and 60-card formats. Follow the procedure in `references/discovery.md`. The union of the selected commanders' `color_identity` becomes the binding colour constraint for all non-land cards.

---

## Phase 5: Deck Build

You build the deck — after the pool tiers are fixed and the Fresh-Eyes Sweep is complete. In that order, always.

**Read `references/build.md` now.** It holds the pool-tier construction, the sweep JSON shapes, the seven-step build procedure, the quantitative-verdict spec format and predicate list, the eight 5D checks, and the Phase 6b invocation.

### Phase 5A — Pool Tiers

Create `_workspace/<run-token>/attempt-<k>/` (k = 1 on the first build). Derive the two card tiers and write them to `pool_tiers.json`:

(Tier contents, precomputed per-card fields, and the disjointness sanity-check are specified in `references/build.md`.)

### Phase 5B — The Fresh-Eyes Sweep (mandatory, no exceptions)

**Before building, every card in `legal_pool` gets a fresh verdict for THIS deck.** This is the prevention guard: the incident this skill is built around was a card never *evaluated* for a deck because it had been rejected for a different one. The sweep makes that impossible — a card cannot be skipped, because every card must appear in the record.

For **every** card in `legal_pool`, record one entry:

(Entry shape and the `sweep.json` file shape are in `references/build.md`.)

- `INCLUDE` — a candidate for the list being built (not a final commitment).
- `EXCLUDE_CONSIDERED` — genuinely evaluated against this pipeline and excluded; the reason states why, as a mechanism or a count (IRON RULE 3 applies to any count-dependent claim).
- `EXCLUDE_OFFPLAN` — does not interact with this deck's plan (wrong role shape, off-strategy); one short clause suffices.

Sweep rules:
1. **Coverage is total.** Every `legal_pool` name appears exactly once. Verified mechanically in 5D.
2. **Reasons are fresh.** Each reason must be derivable from this deck's bundle alone — this card's oracle text, this pipeline's thesis, this list's shape. Never "as before", never "see deck N", never a conclusion you formed while building another deck. If you notice you are about to write a remembered verdict, stop and re-derive it; if it does not reproduce against this pipeline, it was never true here.
3. **Lands and colourless cards are swept too.** A one-clause reason is fine ("no U/R identity, this deck has no use for W sources" → EXCLUDE_OFFPLAN).
3b. **Engine cards state their floor.** For any card whose value depends on the engine assembling (payoff or enabler shape), the reason names what the card does when the engine *hasn't* assembled — as a mechanism ("without a sacrifice outlet this is a vanilla 1/1"). "Functions only when already ahead" (win-more shape) is a valid EXCLUDE_CONSIDERED mechanism.
4. **Reasons carry no count-over-the-list digits.** A `reason` states the mechanism qualitatively ("this deck runs no Goblins", "only cycling cards trigger it and this list has none") — never "0 Goblins", "8 of 24", "2 Island-typed". A count that is load-bearing to a rejection belongs in a `quantitative_verdicts` entry (spec-backed, recomputed in 5D), not in prose. Intrinsic card numbers ({R}{R}, "4 damage", "2 extra turns") are not counts-over-the-list and are fine. The same rule binds every `role` string in the mainboard/sideboard. This is verified mechanically in 5D check 8.

The sweep's `EXCLUDE_CONSIDERED` entries later become the `### CARDS CONSIDERED BUT EXCLUDED` table in the analysis — generated, never re-authored (Phase 10). The sweep is **not** shipped to the Challenger: its absence audit must reach its own conclusions about what is missing, not ratify yours.

### Phase 5C — Build

Build from the sweep's `INCLUDE` candidates. For each card, its oracle text (from `legal_pool`) must support the role you assign; if it does not, the card does not go in.


Follow the seven numbered steps in `references/build.md`: **1 CLASSIFY → 2 ALLOCATE SLOTS → 3 LAND COUNT → 4 MANA SOURCES → 5 FILL → 6 QUANTITATIVE VERDICTS (IRON RULE 3) → 7 record `build_output`**. Counts are computed by `cuber.deck_counts`, never typed by hand; `*_spec` fields are builder-internal and are stripped from the grill bundle.

### Phase 5D — Pre-flight Validation (deterministic)

Write `_workspace/<run-token>/attempt-<k>/_tmp_validate_build.py` and run these checks mechanically before the deck goes anywhere near the grill. **Every check is a string or number comparison. None is a judgment.**


(The eight deterministic checks are enumerated in `references/build.md`.)

Fix any failure directly (you built the deck; you repair it), then **re-run the validator until all checks pass**. Do not proceed to Phase 6 with a failing check, and never hand-patch a validator to make it agree.


---

## Phase 6: Mana Audit Gate

Convert the mainboard into card dicts (join `name` against the working pool cache).

Run `deck_audit.mana_audit(deck_cards, format, commander_cards, core_colors=core_colors, splash_colors=splash_colors)`.
Display the report using `deck_audit.format_audit_report(audit)`.

**If audit result is FAIL:**
- Adjust land count toward the recommended target
- Re-balance producing lands if a color gap > 15pp exists
- Replace non-producing utility lands with on-color duals from `legal_pool`
- Re-run the audit after adjustments; recount any quantitative verdict whose denominator moved
- Log all swaps made

**If audit result is WARN:** note the issue, proceed without blocking.
**If audit result is PASS:** proceed.

Do not show the deck to the user or spawn the grill until the audit is at least WARN.

---

## Phase 6b: Structural Gate

Run the structural checks (the deck-building methodology, mechanized — thresholds live in `cuber/deck_checks.py`, never re-derive them by hand):

(Invocation snippet and `coverage_declaration` construction are in `references/build.md`.)

**Gate tiers:**
- **HARD — treat like a mana-audit FAIL:** `assembly` (an engine role's P(seen by thesis turn) < 0.75 — either add functional copies, or the thesis turn was optimistic: revise it and say so) and `coverage` (missing class, phantom card name, empty concession). Repair, recount any moved verdict, re-run 5D + this gate.
- **WARN-tier — respond, don't rebuild:** `curve` and `goldfish`. Each WARN flag gets one line in `build_output.structural_responses` stating the mechanism-grounded reason the deviation is accepted ("the curve tops at 6 because the thesis turn is 6 and both 6-drops are the kill"). IRON RULE 3 binds these lines: no prose ratio counts.

**Also record `build_output.failure_modes`** — one mechanism-grounded line each for **flood** (what do excess lands do here?), **screw** (which hands are keepable on 2 lands?), and **decapitation** (what is the line when the key piece is answered on sight? if the honest answer is "lose", the deck needs protection slots or a second route — say which it has).

Store the full report as `build_output.structural_checks`. It ships in the grill bundle with everything else in `build_output`; the Challenger audits the derivation through its existing checks.

---

## Phase 7: Sideboard

Skip if the user opted out or if the format does not normally use sideboards.

Default sizes: 8 (40-card), 15 (60-card), custom (commander).

A sideboard answers the **REST OF THE CUBE**, not your own deck. Work from `dossier.threat_profile` (what other decks in this cube actually do) and `cube_index` (what an opponent may play):
- **Hate cards**: match real threat classes in this cube (graveyard, artifacts, sweepers…) — cite oracle text for each, and state which threat class it answers
- **Flex slots**: cards that improve in certain matchups; explain what they answer and when to board them in
- Note any threat class the pool gives your colours no answer to

All sideboard cards come from `legal_pool`, count against combined copy limits, and are re-validated by the 5D checks.

---

## Phase 8: Grill Input Bundle

Write `_workspace/<run-token>/attempt-<k>/grill_input.json`.

The bundle contains:
- `deck`: array of all mainboard + sideboard cards, each with `name`, `oracle_text`, `colors`, `color_identity`, `cmc`, `type_line`, `rarity`, `role` (from Phase 5), and `board`
- `audit`: the mana audit result object from Phase 6
- `card_pool_rules`: the confirmed pool rules object from Phase 0
- `restrictions_checklist`: the compliance checklist from Phase 5
- `build_output`: your recorded derivation — `macro_archetype`, `deck_identity`, `thesis_turn`, `default_role`, `slot_allocation`, `land_math`, `pip_math`, `quantitative_verdicts`, `coverage`, `failure_modes`, `structural_checks`, `structural_responses`. This lets the Challenger audit the **derivation**, not just the list.
- `validation_report`: the Phase 5D check results (all PASS by the time you get here)
- `attempt`: the integer k
- `legal_pool`, `cube_index` (from `pool_tiers.json`), `dossier`, `dossier_sha256`

**The sweep is deliberately NOT in this bundle.** The Challenger's absence audit must reach its own view of what is missing from the deck; shipping your sweep verdicts would hand it your conclusions to ratify — the exact failure the cold context exists to prevent.

The Challenger reads only this file — never `enriched.json`, the working pool cache, or any other cube data file.

### Integrity Checksum (Phase 8 → 9 handoff guard)

Immediately after writing `grill_input.json`, compute its SHA-256 — this is the `EXPECTED_HASH` the Challenger verifies against, so a concurrent session that overwrites the file mid-grill is caught instead of silently poisoning the deck:

```
python -c "import hashlib; print(hashlib.sha256(open('_workspace/<run-token>/attempt-<k>/grill_input.json','rb').read()).hexdigest())"
```

You MUST embed this hash literally in the Challenger prompt as `{{EXPECTED_HASH}}`. Together with `{{GRILL_INPUT_PATH}}` it is the **only** value you may vary in that prompt. See IRON RULE 2.

---

## Phase 9: Self-Grill (Hard Gate)

Spawn **one** agent from TEMPLATE D, **verbatim**.

TEMPLATE D lives in `references/challenger-template.md`. Read that file and copy the template byte-for-byte; substitute only the two declared placeholders (`{{GRILL_INPUT_PATH}}`, `{{EXPECTED_HASH}}`). The pre-spawn self-check (IRON RULE 2) diffs your built prompt against that file.

---

### Resolve Grill (you adjudicate)

You built this deck; you judge the findings — for THIS deck, that is exactly the deck-scoped judgment IRON RULE 2 permits. The discipline is in *how*:

1. **Respond to every finding explicitly.** For each one — including every INDEFENSIBLE entry and every absence — record accept or reject with an oracle-grounded reason or a recount. Write the resolution table to `_workspace/<run-token>/attempt-<k>/grill_resolution.json`: `[{ "finding": "…", "action": "ACCEPT|REJECT", "reason": "<oracle quote or recount>" }]`. Silent dismissal is prohibited; "I already considered that" is not a reason — the recount is.
2. **Hard findings are non-negotiable.** These always force a repair, never a rebuttal:
   - a legality violation (a Phase 5D check code),
   - a mana-audit regression (audit falls below WARN),
   - a quantitative verdict that fails to reproduce,
   - a dossier claim that fails to reproduce (report it to the user as a dossier error too — it will matter beyond this deck).
3. **Soft findings** (a card-swap opinion, an absence, a proportional-band deviation, a role-text quibble) you may accept or reject on the merits. A Challenger can be confidently wrong — verify each claim against oracle text before acting. But an absence finding naming a card whose oracle-grounded count you cannot rebut is a finding you accept.
4. **Repair the deck yourself.** Apply accepted findings, keep what you can, recount every quantitative verdict whose denominator moved (a verdict you did not recount is a verdict you may not keep), then re-run the Phase 5D validator and the Phase 6 audit on the result. Update the affected `sweep.json` entries if a repair changes a verdict (the sweep must describe this deck as built).
5. The Challenger's `COLOR ALLOCATION OBSERVATION`, if present, is lifted out and surfaced to the user in Phase 10. Colours are locked; nothing in this run acts on it.
6. The Challenger's `UNCAPTURED CHAIN CANDIDATES`, if present, are queued for the Phase 12 session-end write-back — they are cube facts, and holding them until session end preserves the freeze. They are not findings about this deck and require no grill action (though a candidate may coincide with an absence finding, which is adjudicated on its own merits in step 3).

**Grill rounds: one by default.** Spawn a second Challenger (fresh agent, re-hashed bundle) **only** if the first round produced a *hard* finding, so the repair itself gets checked. A soft finding does not buy a second round. **Max 2 rounds** in any case.

Final list must satisfy: every card in the cube + oracle text supports every role + audit ≥ WARN + Phase 5D all-PASS.

### Re-evaluation Path

Trigger, and only this trigger: the Challenger states **"This pipeline cannot achieve its stated win condition with the available card pool."** (Not a mana issue. Not a ratio issue. Not a card-swap issue.) Verify the claim against `legal_pool` oracle text; if it stands:

1. Log the rejection as `{ "payoff_card": "<name>", "verdict": "PIPELINE_NOT_VIABLE" }` — a name and an enum.
2. Select the **next pipeline** from the Phase 3 shortlist. Do NOT re-run discovery or Phase 2.
3. Increment k. Create `_workspace/<run-token>/attempt-<k>/`. Re-run Phase 5 from 5A: new pool tiers if the colours changed, and a **complete fresh sweep** — the old sweep's verdicts were scoped to the old pipeline and are stale by definition.
4. Re-run Phases 6–9 against `attempt-<k>`.

If the shortlist is exhausted (all shortlisted pipelines attempted and rejected):
> "All shortlisted pipelines were rejected. Options: (1) Restart Phase 0 to adjust pool rules. (2) Lower the viability threshold and rerun discovery."

Wait for user guidance before proceeding.

---

## Phase 10: Present Final Deck

Display the deck using the enforced format below. **Section order is strict — do not reorder.**

**Read `references/render-and-save.md` now.** It holds the display template, the format rules (including: **no Scryfall links, no external links of any kind, card names as plain text everywhere**), and the `_tmp_validate_analysis.py` check list. It also covers the Phase 11 file specs.

### The analysis firewall (binding)

The `## ANALYSIS` body is scoped to **this deck's run** — this bundle, this sweep, this grill. Three rules:

1. **No cross-deck content.** No reference to another deck, another build, another session, or a conclusion formed while building one. No "see above", no "as with the previous deck", no justifying a cut by what a different deck's payoff wants.
2. **Excluded-card content is generated, never authored.** `### CARDS CONSIDERED BUT EXCLUDED` is the sweep's `EXCLUDE_CONSIDERED` entries reproduced as-is. You may not add, drop, reword, or supplement an entry at render time — if a reason is wrong, the sweep is wrong, and the fix happens there.
3. **No foreign card names.** Every card name in the analysis body must be in this deck or its `legal_pool`. Naming a `cube_index` card is permitted **only** inside sideboard/threat discussion, where the rest of the cube is the subject.

### Section header counts — derive, then verify

Every section header carries a count: `## MAINBOARD (24 spells + 16 lands = 40)`, `### CREATURES (13)`, `## SIDEBOARD (10)`. These go stale the moment a card is swapped.

1. **Derive, never type.** Every header count is computed from the deck arrays at render time — the sum of `qty` for that section — never hand-written and never copied from a previous version.

After every write of `analysis.md`, run `_tmp_validate_analysis.py` per the check list in `references/render-and-save.md`. Any mismatch is a **hard failure**: regenerate from the deck arrays and sweep — never hand-patch the output to make the validator agree.

Ask: **"Save this deck? [y/N]"**

---

## Phase 11: Save

On confirmation, prompt for a deck name if not already provided. Sanitize to a filesystem-safe slug (lowercase, alphanumeric + hyphens).

All five files go into a single subfolder: `cubes/<id>/decks/<name>/`

File-by-file specs — the `deck.json` schema, `deck.tsv` columns, `exporter.write_mwdeck`, the `sweep.json` copy, and the `analysis.md` frontmatter and section structure — are in `references/render-and-save.md`.

---

Confirm all five paths:
```
Saved:
  cubes/<id>/decks/<name>/deck.json
  cubes/<id>/decks/<name>/deck.tsv
  cubes/<id>/decks/<name>/deck.mwDeck
  cubes/<id>/decks/<name>/sweep.json
  cubes/<id>/decks/<name>/analysis.md
```

---

## Phase 12: Session-End Chain Write-Back

Runs **only** when the user indicates the session is done (no more decks) — never between decks.

Candidates come from two sources: cube facts you discovered while building that no chain records — an engine, a type-change interaction, a mana loop — and every `UNCAPTURED CHAIN CANDIDATES` entry the Challengers reported during the session's grills. Queue both in your run directory as you go; at session end:

1. For each candidate, re-derive it from oracle text alone. It must satisfy the admissibility rule: mechanism + oracle quotes, no evaluation words, no reference to any deck. If you cannot state it as "A's text says X, B's text says Y, therefore Z is legal", it does not go in.
2. Append the qualifying chains to `dossier.interaction_chains` in `cubes/<slug>/dossier.json` (leave `chains_seeded_at` untouched — it records the seed pass).
3. Tell the user which chains were added. The next session's dossier freeze will include them.

**Why session end and not mid-run:** the dossier's isolation guarantee is temporal — frozen before deck 1, byte-identical for every deck in the session. A mid-session append would give later decks knowledge earlier decks lacked and reopen the exact channel this architecture closes.

---

## Tool Selection Table

| Task | Tool / File |
|------|-------------|
| Load card pool (with pool rules) | `cube_search.load_merged_pool(id, card_pool_rules=...)` — Phase 0 only |
| **Build / load the cube dossier** | `cuber dossier <id>` (`dossier.build_dossier` / `load_dossier` / `save_dossier`) — Phase 2 Step 0. Cached per cube; `--rebuild` to force |
| **Mana infrastructure, fixing score** | `dossier.mana_infrastructure.duals_by_pair` — use the `free` count. NEVER re-derive by hand |
| **Rituals, sweepers, sac outlets, tutors** | `dossier.structural_census` — NEVER re-derive by hand. But a 0-match proves nothing: see `census_caveat` |
| **What the sideboard answers** | `dossier.threat_profile` + `cube_index` |
| Filter by color/type/tag/CMC | `cube_search.search_pool(pool, color_identity=core_colors, splash_color_identity=splash_colors, ...)` |
| Query Payoff candidates | Filter working pool cache by `taxonomic_profile.structural_roles` containing `"Payload/Payoff"` |
| Query synergy support | Filter working pool cache by `taxonomic_profile.synergy_clusters` overlap + `"Enabler/Fodder"` or `"Engine/Outlet"` in `structural_roles` |
| Find commander candidates | `commander_finder.find_commanders(id, color_identity)` |
| Display commander table | `commander_finder.format_commanders_table(candidates)` |
| Run mana audit | `deck_audit.mana_audit(deck_cards, format, commander_cards, core_colors=core_colors, splash_colors=splash_colors)` |
| Display audit report | `deck_audit.format_audit_report(audit)` |
| **Structural gate (curve / assembly / goldfish / coverage)** | `deck_checks.run_structural_checks(...)` + `deck_checks.format_checks_report(report)` — Phase 6b. Thresholds and curve bands live in `cuber/deck_checks.py`; NEVER re-derive them by hand |
| Verify card exists | Search working pool cache by exact name — never training data |
| Read oracle text | `card.oracle_text` from the working pool cache (you) or the grill bundle (Challenger) — never training data |
| Pool tiers | `_workspace/<run-token>/attempt-<k>/pool_tiers.json` — `legal_pool` + `cube_index`, disjoint, precomputed `pips`/`has_generic`/`subtypes` |
| **Fresh-Eyes Sweep** | `_workspace/<run-token>/attempt-<k>/sweep.json` — every `legal_pool` card, exactly once, fresh reasons only |
| Pre-flight validation | `_workspace/<run-token>/attempt-<k>/_tmp_validate_build.py` — deterministic checks only |
| **Compute / recount any count** | `cuber.deck_counts` — `resolve(deck, spec)` for a verdict number, `check_verdicts(deck, verdicts)` for the 5D recount, `count_digits_in_prose(text)` for the 5D prose guard. The ONE place counts are computed; both the build and the validator call it |
| Grill input bundle | `_workspace/<run-token>/attempt-<k>/grill_input.json` — hashed; the sweep is deliberately excluded; verdict `*_spec` fields are stripped |
| **Spawn the Challenger** | Copy TEMPLATE D from `references/challenger-template.md` verbatim. Substitute declared `{{PLACEHOLDER}}` values only. Never author prompt text. See IRON RULE 2 |
| Grill resolution record | `_workspace/<run-token>/attempt-<k>/grill_resolution.json` — every finding, ACCEPT/REJECT, oracle-grounded reason |
| Validate analysis.md | `_workspace/<run-token>/attempt-<k>/_tmp_validate_analysis.py` — header counts, zero scryfall, firewall check, generation check |
| Write deck files | Write tool → `cubes/<id>/decks/<name>/deck.json` and `deck.tsv`. `exporter.write_mwdeck()` → `deck.mwDeck`. Copy → `sweep.json`. `exporter.write_deck_analysis_md()` → `analysis.md` |
| Write a temp Python script | `_workspace/<run-token>/attempt-<k>/_tmp_<name>.py` — never to the repo root or shared `_workspace/` root |

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
Every inclusion and justification MUST cite `oracle_text` from the working pool cache (`_workspace/<run-token>/working_pool.json`). The Phase 9 agents cite oracle text from their own Phase 8 bundle (`grill_proposer.json` / `grill_challenger.json`).
If the oracle text does not support the stated role, the card must be replaced.

---

## The Counts Principle — Counts, Not Adjectives

No card is good or bad in isolation. A card is **count-dependent** when its value is a function of how many other cards qualify: cost reducers, tribal and type-matters payoffs, storm and spell-count triggers, graveyard counts, devotion, threshold, metalcraft, delirium, domain, affinity — and any card whose relevant text reads a *rate* rather than a card: flip conditions, prowess, magecraft, "if an instant or sorcery was cast this turn".

Two rules follow. They bind at different phases because they need different things.

**1. State the count.** Any verdict on a count-dependent card — include, cut, trap, must-run, "not worth the slot" — is a numerator and a denominator against **this** deck's list, never an adjective.

> WEAK:  "This cost reducer only reduces generic mana, so it's marginal here."
> STRONG: "This cost reducer reduces generic mana; 16 of the 24 nonland cards in this list have a generic component. INCLUDE."

**2. Cut only where a denominator exists.** The denominator is a built list, and Phase 5A has none — the list is what Phase 5B produces. So a count-dependent card is **not decided at Phase 5A**: it stays in `include_candidates` flagged `"count_dependent": true`, and its verdict is written at Phase 5B **step 6 — COUNT-DEPENDENT VERDICTS**, against the mainboard that exists by then. A count-dependent name in `considered_but_excluded` is a Phase 5A error; the Challenger raises it BLOCKING (`references/challenger-template.md` item 11).

**The one exception — a ceiling already fixed by an earlier phase.** Some counts have an upper bound that is knowable at 5A because a previous phase locked it: `core_colors ∪ splash_colors` is locked at Phase 3, and deck size and format at Phase 1. Domain in a two-colour deck caps at 2 of 5; a "for each basic land type you control" payoff cannot beat that ceiling no matter what 5B builds. Cutting on a *ceiling* is still a count, so it obeys rule 1 — record it as `"reason": "domain ceiling 2/5 — core_colors locked to [G,W] at Phase 3"`. What you may not do is cut on a *guess about the eventual denominator*: "this deck probably won't have many instants" is the adjective this rule exists to stop.

> The failure this closes: `Delver of Secrets` was cut at Phase 5A as "a 1-mana beater". Its flip rate is instant/sorcery density; in the lists actually built it was 43.6% — a number that could not be written at 5A, and was not.

Compute counts from the list you actually built; if the list changes, recount.

---

## Phase Protocol — Announce, Then Work

**Every phase opens with a banner line to the user, before any phase work:**

> ▶ Phase <N> — <phase name>

No banner, no phase. The banner is written the moment the phase begins — not retroactively, not batched with the next one. A phase whose banner never appeared is a phase that was skipped.

**Subagent protocol (the Phase 5B skeleton critic and the Phase 9 agents):**

1. When dispatching, announce it: `⏳ Dispatching Proposer + Challenger`.
2. Every dispatch prompt mandates that the agent's report **open** with `=== <ROLE> REPORT — BEGIN ===` and **close** with `=== <ROLE> REPORT — END ===`.
3. When a report returns, verify **both** markers are present before using anything in it. A report missing either marker is incomplete — announce that and re-dispatch that agent; never adjudicate from a partial report.
4. After the check passes, announce: `✔ <role> report verified`.

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

**Basic lands are format-supplied.** The pool always includes an unlimited supply of the five basic lands (Plains, Island, Swamp, Mountain, Forest), whether or not the cube list contains them — unless the user explicitly restricts basics. Never inspect other files to check whether basics are in the cube; `dossier.mana_infrastructure.basics_in_pool` is informational only. When the cube lacks them, add them to the working pool per `references/workspace-and-pool.md`.

Infer the `card_pool_rules` object from the answer — the JSON shape and field semantics are in `references/workspace-and-pool.md`.

**Display the inferred `card_pool_rules` and ask the user to confirm before proceeding.** If the user corrects the inferred object, update it and re-display. Proceed only after explicit confirmation.

Once confirmed, write `_workspace/<run-token>/run_config.json` — `{run_token, cube_slug, short_id, format, card_pool_rules}` (+ `commander` once Phase 4 picks one). Every shipped script reads it; this is what lets them be format- and cube-generic instead of hardcoded to one run.

### Working Pool Cache

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/build_pool.py --run <run-token>
```

It loads the filtered pool through `cube_search.load_merged_pool`, dedupes by name (the cache is one row per **distinct card**, not per copy), synthesizes any missing basics, backfills DFC `mana_cost`/`power`/`toughness` from `card_faces[0]`, and writes `working_pool.json`. All subsequent phases use this file exclusively.

The DFC backfill is not cosmetic: `enriched.json` leaves `mana_cost` null on double-faced cards, which zeroes their pip contribution in every mana audit and makes `effective_cost.best_mode` reject them as unusable in every colour. On one measured cube that silently removed 41 cards from the colour gate.

Do **not** write a readable pool dump alongside it. (Per-card field lists and the Phase 11 `export_meta.json` capture are in `references/workspace-and-pool.md`.)

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
- Cluster roster size and its role census — e.g. `37 cards: 13 enabler/engine · 6 payoff · 9 interaction · 9 other`. The viability gate ran on the 13.
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

You build the deck. **Read `references/build.md` now.** It holds the seven-step build procedure, the slot-allocation table, the land-count model (formula + hypergeometric refinement, computed by `deck_audit.land_target` — never a percentage read off a table), the pip-source math, the seeded-sweep recipe and shape, and the Phase 6b invocation.

### Phase 5A — Seeded Sweep

The sweep is a **partition of a machine-generated seed**, not a list written from memory. The Step-0 critic is pool-blind and sees only `include_candidates`, so whatever the sweep omits is not reconsidered until Phase 9.

1. **Seed.** Run `scripts/seed_sweep.py` (invocation in `references/build.md`). Four bands: cluster overlap at *any* role, plus role-scoped bands for interaction/consistency, threats, and engines/fodder. Membership is the query's output; you do not choose it.
2. **Annotate and subtract.** Every seed card lands in exactly one of two lists with a stated reason — `include_candidates` or `considered_but_excluded` (cut, one-line mechanism; batch cuts may share one reason). Write them straight into `sweep.json`; no second partition file. No third destination, nothing dropped silently.
3. **Defer the count-dependent.** A card whose value is a count is not subtracted here — no list exists yet to count it against (the Counts Principle). It stays in `include_candidates` with `"count_dependent": true` and is decided at Phase 5B step 6. The one exception is a count whose ceiling an earlier phase already fixed.
4. **Verify.** Re-run `seed_sweep.py --verify`: it asserts the two lists partition the seed exactly, with no name in both and none missing. Fix and re-run until it passes.

`sweep.json` ships in the Phase 8 Challenger bundle and the Challenger audits it as checklist item 11. The `notable` exclusions become the `### CARDS CONSIDERED BUT EXCLUDED` section of the analysis. Band definitions and cap rules are in `references/build.md`.

### Phase 5B — Build

Draft the skeleton from `include_candidates`; FILL (step 5) draws from the whole colour-usable pool. The slice bounds the pool-blind critic, not your own build. For each card, its oracle text (from the working pool cache) must support the role you assign; if it does not, the card does not go in.

**Before you classify, run Step 0 — propose → critique → lock (every build):** pin the `archetype_family` from the locked `thesis.default_role` + Phase 1 intent, draft the skeleton (slot table + 3–5 keystones with oracle text quoted), then dispatch **one independent, pool-blind skeleton critic** (subagent protocol above) seeing only your skeleton and the machine-seeded `include_candidates` slice — never told the skeleton is yours. It must return `weak_keystones`, a `strongest_alternative` argued against the thesis, and `thesis_risk`. Resolve every weak keystone and **harvest** the alternative role-for-role into FILL. Mechanics and the trade-off this accepts are in `references/build.md`.

Then follow the numbered steps in `references/build.md`: **0 PROPOSE→CRITIQUE→LOCK → 1 CLASSIFY → 2 ALLOCATE SLOTS → 3 LAND COUNT → 4 MANA SOURCES → 5 FILL (+ harvest) → 6 COUNT-DEPENDENT VERDICTS → 7 record `build_output`**.

### Phase 5C — Pre-flight Validation (deterministic)

Run `scripts/validate_build.py --run <token> --deck <dir>` (deck size, exact-name membership, copy limits, colour usability, splash cap). Every check is a string or number comparison. The colour check tests **usability via `effective_cost.best_mode`**, not raw `color_identity`, so a card played by a colourless/in-colour mode (e.g. a cycler) is not falsely rejected. Fix any failure directly, then re-run until all pass. Do not proceed with a failing check, and never hand-patch a validator to make it agree.

---

## Phase 6: Mana Audit Gate

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/mana_audit.py \
    --run <run-token> --deck <deck-dir>
```

It joins the mainboard against the working pool cache, passes the commander through on the commander formats, prints the formatted report and writes `audit.json` (which Phase 8 ships to both grill agents). Exit 1 means FAIL.

The land count is a function of deck size, curve and acceleration only — there is no archetype term, so the mana audit takes no `macro_archetype`. (You still compute `macro_archetype` for the Phase 6b structural curve check, which does use it.)

**If audit result is FAIL:**
- Adjust land count toward the recommended target. The audit and Phase 5B step 3 call the *same* `land_target` function, so a land-count FAIL means the list drifted from the target you built to — usually because the actual avg MV moved during FILL. Fix the count, not the recommendation; `audit["land_target_trace"]` shows the derivation.
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

**Also record `build_output.failure_modes`** — all six modes, none omitted: **flood**, **screw**, **decapitation**, **gas-out**, **raced**, **disruption-fizzle**. Each entry is exactly one of two shapes: a `mitigation` (mechanism-grounded, naming the cards or plan that address it) or an `accepted` (stating explicitly what mitigating would cost the deck's identity or winning plan). There is no third shape. Mode definitions and the JSON spec are in `references/build.md`. The Challenger reviews every entry as a checklist (its item 13); an entry it cannot accept is a BLOCKING finding.

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

## Phase 8: Grill Input Bundles

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/build_bundle.py \
    --run <run-token> --deck <deck-dir>
```

It writes **two** files, one per Phase 9 role, and prints both sizes:

| File | Contents | Read by |
|---|---|---|
| `grill_proposer.json` (~25 KB) | `deck`, `deck_meta`, `audit`, `card_pool_rules`, `restrictions_checklist`, `validation_report`, `build_output_lite` | the Proposer, only |
| `grill_challenger.json` (~250 KB) | the above plus full `build_output`, `sweep`, `working_pool`, `dossier` | the Challenger, only |

**Phase 9 approval rounds use a third file.** Re-run the same script with `--delta`:

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/build_bundle.py \
    --run <run-token> --deck <deck-dir> --delta
```

| File | Contents | Read by |
|---|---|---|
| `grill_delta.json` (~30 KB) | `deck`, `deck_meta`, `audit`, `card_pool_rules`, `restrictions_checklist`, `validation_report`, `structural`, `build_output_delta`, `build_output_delta_keys`, `deck_changes` | the Challenger, in an approval round |

An approval round asks the Challenger to verify a handful of changed slots, and re-reading the whole
bundle to do it wastes ~90% of the load on artifacts that have not moved since round 0 — measured at
five rounds across a three-deck run. The delta ships the deck array, the re-run gate outputs and only
the `build_output` keys that actually changed: an ~88% cut.

The script diffs against the `grill_challenger.json` already on disk, which is a byte-exact snapshot of
what the Challenger's context holds — so **you declare nothing about what changed**; it is computed.
Two consequences: `--delta` deliberately does **not** rewrite the full bundles (that would destroy the
snapshot the next delta diffs against), and `--delta` with no snapshot is an error rather than a silent
fallback. A fresh Challenger, or a re-dispatched Proposer, needs a full non-`--delta` rebuild first.

If a finding genuinely needs a pool re-check, do not rebuild the full bundle — pass
`--pool-query "<oracle regex>"` to attach only the matching rows. `--with-pool` is the last resort.

**Why two files and not one with instructions.** The Proposer defends the cards in `deck`; it never needs the pool or the dossier, which are ~77% of the bundle. Telling one agent "do not read that key" is a prompt-adherence gamble — splitting the file is a guarantee. `build_output_lite` deliberately withholds `count_dependent_verdicts`: the Proposer's contract requires it to state counts *itself*, so handing it mine would be anti-adversarial.

The `deck` rows carry `tags` (so the Challenger's item-8 `mana_audit` re-run reproduces `accel_count` instead of computing zero and reporting a phantom discrepancy) and `usable_as` + `cast_mode` (so the Proposer can meet its off-identity contract by naming the legalising mode). The Challenger's `working_pool` is projected down by four fields that no checklist item reads; `oracle_text` and `taxonomic_profile` are never trimmed — they are the IRON RULE's evidence base. Both files are written with compact separators; nothing parses them by line.

Each Phase 9 agent reads only its own file — never `enriched.json`, the working pool cache, or any other cube data file.

---

## Phase 9: Self-Grill (Hard Gate)

**Read `references/challenger-template.md` now.** Spawn the two agents it describes — a Proposer that defends every card with an oracle quote, and a Challenger that attacks the deck independently and runs the full checklist (membership, oracle, restrictions, identity fit, better alternatives, proportional validation, sideboard cohesion, mana re-run, **derivation audit**, **absence audit**, **sweep audit**, pipeline viability, and **failure-mode review**). Neither agent sees the other's output during generation. Both dispatches and both returned reports follow the subagent protocol in **Phase Protocol** — verify the BEGIN/END markers before adjudicating.

### Resolve Grill (you adjudicate)

You built this deck, so you defend it and judge the Challenger's findings. Every finding arrives tagged by the Challenger as **BLOCKING** (the deck cannot finalize while it stands) or **ADVISORY** (yours to decide on the merits). Resolution is a table, a repair, an approval round, and a gate — in that order:

**1. The Resolution Table (required artifact — display it to the user).** One row per Challenger finding, no finding without a row:

| # | Finding | Severity | Decision | Grounds |
|---|---------|----------|----------|---------|

- `Severity` is the Challenger's tag, copied verbatim — never downgraded by you.
- `Decision` is `IMPLEMENT` or `CONTEST`.
- Hard findings — a legality violation (a Phase 5C check), a mana-audit regression (audit falls below WARN), a structural-gate HARD failure, a count that fails to reproduce — are always BLOCKING and always `IMPLEMENT`: repair, never rebuttal.
- A BLOCKING finding may be CONTESTed only with an oracle quote or a reproduced count in `Grounds`. "Marginal", "fine as is", and other adjectives are not grounds. An absence finding naming a card whose oracle-grounded count you cannot rebut is `IMPLEMENT`.
- ADVISORY findings: decide on the merits with one-line grounds — verify each claim against oracle text first. No approval needed.

**2. Repair the deck yourself — in ONE batched pass, then re-run only what the repair could have changed.** Apply **every** `IMPLEMENT` row before running any gate, and recount any count-dependent verdict whose denominator moved. Gates run **once per grill round**, over the batched result — never once per finding. Gating a single swap while three more are pending produces a verdict about a list that will not exist.

Then re-run by **the file you changed**, not by intent:

| What the repair changed | Re-run |
|---|---|
| `deck.json` — any card, any qty, either board | `validate_build.py`, `mana_audit.py`, `land_math.py` (non-commander), `structural.py`, then `build_bundle.py --delta` |
| `checks.json` only — `role_counts` / `coverage_declaration` / `thesis_turn` | `structural.py` only |
| `build_output.json` prose only — `deck_identity`, `structural_responses`, `failure_modes`, `analysis_body`, a reworded rationale | **nothing** |

`validate_build.py`, `mana_audit.py` and `land_math.py` read `deck.json`, `run_config.json` and `working_pool.json`; `structural.py` additionally reads `--checks`. **None of them opens `build_output.json`** — `structural.py` mentions it only in a docstring. A prose-only `build_output` edit therefore cannot change any gate verdict, and re-running the gates to "confirm" it spends tokens reproducing a byte-identical result. The one script that *does* read `build_output.json` is `render_save.py`, so a prose edit is visible at Phase 10 and never at a gate.

The rule keys off the changed file precisely so it cannot be over-applied: if you edited a **count** in `build_output`, you almost certainly also changed `deck.json` or `checks.json`, and any `deck.json` touch re-runs everything.

**3. Approval round** (skip only when the Challenger reported zero BLOCKING findings). Re-run `build_bundle.py --delta` (Phase 8), then send back to the **same Challenger agent** (SendMessage — its context is intact; do not spawn a fresh one): the Resolution Table, **only the changed slots** as `−<card> +<card>` with counts, and **the path to `grill_delta.json`**.

Do not paste the deck list into the message, and do not point the agent back at `grill_challenger.json`. The delta already carries the updated `deck` array, the re-run gate outputs in full, and only the `build_output` keys that changed, at roughly a tenth of the full bundle — the machine resends the list so you never retype it, and the agent's recounts get correct denominators. (`--delta` does not rewrite the full bundles; they are the snapshot it was computed against.) It returns a verdict per BLOCKING finding: RESOLVED or UNRESOLVED with a one-line reason. Any UNRESOLVED verdict → one more repair + review round. **Cap: two review rounds.** BLOCKING findings still UNRESOLVED after round two are escalated to the user with both sides' reasoning; the user rules.

**4. Finalization gate.** Phase 10 is reachable only when every BLOCKING finding is RESOLVED — or the user has ruled on it — AND the final list satisfies: every card in the cube + oracle text supports every role + audit ≥ WARN + Phase 5C all-PASS + Phase 6b HARD gates pass.

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

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/render_save.py \
    --run <run-token> --deck <deck-dir> [--save --name <deck-slug>]
```

Without `--save` it writes `analysis_preview.md` in the run dir; with it, all four files under `cubes/<id>/decks/<name>/`. It emits every **mechanical** section from the deck arrays — card tables, header counts, structural report, failure-mode table, mana audit, restrictions checklist. You author only `build_output.analysis_body` (`### DECK IDENTITY` + free-form observations). Deriving the headers rather than typing them makes header-versus-list drift impossible, not merely detectable.

Then verify: `scripts/validate_analysis.py --run <token> --deck <dir>` (add `--saved` after Phase 11).

Ask: **"Save this deck? [y/N]"**

---

## Phase 11: Save

On confirmation, prompt for a deck name if not already provided. Sanitize to a filesystem-safe slug (lowercase, alphanumeric + hyphens).

All four files go into a single subfolder: `cubes/<id>/decks/<name>/`. Re-run `render_save.py` with `--save --name <slug>`; it builds `export_meta.json` for the deck's cards at this point (not the whole pool at Phase 0) and writes all four.

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
| Filter by color/type/CMC | `cube_search.search_pool(pool, color_identity=core_colors, splash_color_identity=splash_colors, ...)` — admits a card if `effective_cost.best_mode` finds a usable mode (a colourless/in-colour cycler or kicker-decline counts, even off printed identity); each returned card carries `usable_as` (`None` = normal cast, else the mode, e.g. `"cycler"`). Returned dicts are copies — the tag never mutates the pool cache. **Never pass `tags=`**: pooled `tags` come only from `tagged.csv`, are AND-only, and return zero rows *in silence* on a cube without one. Filter `taxonomic_profile` in Python instead |
| Query Payoff candidates | Filter working pool cache by `taxonomic_profile.structural_roles` containing `"Payload/Payoff"` |
| **Query a pipeline's cluster roster** | Filter working pool cache by `taxonomic_profile.synergy_clusters` overlap, **all roles** — a role filter hides an archetype's own payoffs, threats and card flow. This roster is what Phase 5A seeds from |
| Count a pipeline's feeders (viability gate only) | The roster subset whose `structural_roles` include `"Enabler/Fodder"` or `"Engine/Outlet"`. The gate is tested against this count, never against the roster |
| **Card resource profile (mana/card economy)** | `taxonomic_profile.resource_exchange` from the working pool — `Mana:`/`Cards:`/`Board:`/`Life:` labels, empty = neutral. Key absent (untagged cube) → derive from oracle text |
| Find commander candidates | `commander_finder.find_commanders(id, color_identity)` |
| Display commander table | `commander_finder.format_commanders_table(candidates)` |
| Run mana audit | `deck_audit.mana_audit(deck_cards, format, commander_cards, core_colors=core_colors, splash_colors=splash_colors)` |
| Display audit report | `deck_audit.format_audit_report(audit)` |
| **Structural gate (curve / assembly / goldfish / coverage)** | `deck_checks.run_structural_checks(...)` + `deck_checks.format_checks_report(report)` — Phase 6b. Thresholds live in `cuber/deck_checks.py`; NEVER re-derive them by hand |
| Verify card exists | Search working pool cache by exact name — never training data |
| Read oracle text | `card.oracle_text` from the working pool cache (you) or the grill bundle (Phase 9 agents) — never training data |
| Write deck files | Write tool → `cubes/<id>/decks/<name>/deck.json` and `deck.tsv`. `exporter.write_mwdeck()` → `deck.mwDeck`. `exporter.write_deck_analysis_md()` → `analysis.md` |
| Write a temp Python script | `_workspace/<run-token>/_tmp_<name>.py` — never to the repo root or shared `_workspace/` root |

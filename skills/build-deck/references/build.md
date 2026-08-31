# build-deck reference — Phases 5–6b: build mechanics

Read at the start of Phase 5; covers the seeded sweep, the Step-0 propose-and-critique gate, the seven-step build procedure, the pre-flight checks, and the Phase 6b structural-gate invocation. Mechanics only — the IRON RULE, the Counts Principle, and the gate semantics are in SKILL.md.

The build works from the whole filtered pool (the working pool cache), bounded by `core_colors`, `splash_colors`, and the named `splash_candidates`. There is no separate legal/index split — the grill bundle ships the full `working_pool`, and the sideboard and absence audit see the rest of the cube through it. Phase 5A's seed is the cluster-scoped slice the Step-0 critic sees; your own FILL is not bounded by it.

## Phase 5A — the seeded sweep

The sweep is a **partition of a machine-generated seed**. You do not author the candidate list; you annotate it and subtract from it with a stated reason. Downstream, the Step-0 critic is pool-blind and sees nothing but `include_candidates` — so a list written from recall becomes the universe the skeleton is drafted and critiqued against, and anything recall skipped is not reconsidered until Phase 9.

### 1. Seed — run the query, don't remember the cards

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/seed_sweep.py \
    --run <run-token> --deck <deck-dir> --pipeline <pipeline.json>
```

`pipeline.json` carries `{payoff, clusters, core_colors, splash_colors, splash_candidates}`. The script writes `seed.json` and prints the per-band counts. Four bands:

- **pipeline band** — every colour-usable card overlapping the locked pipeline's `synergy_clusters`, *any structural role*, plus the payoff itself and the named `splash_candidates`.
- **staple band** — `Interaction/Disruption` or `Infrastructure/Consistency`, cluster or no cluster. Without it the deck's answers and consistency pieces are reachable only by cluster accident.
- **threat band** — `Payload/Payoff` or `Standalone Threat`, cluster or no cluster. A deck's creatures usually do not share the payoff's cluster, so without this band the seed offers an archetype with nothing to attack with.
- **engine band** — `Engine/Outlet` or `Enabler/Fodder`, cluster or no cluster. These are the sacrifice outlets, evasion granters and token fodder that make a payoff *fire*; they are frequently tagged into no cluster at all. Omitting this band hid `Siege Zombie` and `Cobbled Wings` in a measured run — both wanted, both found only later by the Challenger at far higher cost. Adding it took the still-unreachable count on two live pipelines to **zero**.

Together the four bands cover all six structural roles. Lands are excluded from every band: they are chosen in steps 3–4 from the whole pool.

Two properties the query buys that a hand-written list does not. `search_pool(color_identity=…)` returns copies stamped with `usable_as` via `effective_cost.best_mode`, so the slice carries the same colour-usability verdict Phase 5C check 4 and the Challenger's item 4 test against. And splash-colour cards enter only by exact name from `splash_candidates`, so a splash colour never admits its whole colour.

**Caps.** The pipeline band is never capped — capping it is the original defect in machine form. Staple is capped at 40, threat and engine at 25 each (lowest CMC first, ties by name), and every dropped name goes in `seed_query.*_dropped` so nothing is invisible to the Challenger's absence audit. If the pipeline band alone runs past ~120 cards, the locked clusters are too generic to scope anything: narrow to the clusters the payoff's oracle text actually reads and record the narrowing in `seed_query.clusters_note`. Never truncate the pipeline band.

**Run every scripted phase from the repo root with `PYTHONPATH=.`** — Python puts the *script's* directory on `sys.path`, not the cwd, so `from cuber import ...` raises `ModuleNotFoundError` otherwise. And the working-pool cache is **copy-expanded**: `load_merged_pool` materialises `multipliers` as duplicate rows (503 rows for 305 distinct cards on a 2×-commons cube). The shipped scripts dedupe by name; any script you write yourself must too, or every common is counted twice.

### 2. Annotate and subtract

Every seed card goes into exactly one of two lists, each entry carrying a reason. There is no third destination and nothing leaves the seed unrecorded.

```json
{
  "run_token": "run-…",
  "pipeline_payoff": "<name>",
  "swept_at": "<ISO 8601 UTC>",
  "seed_query": {
    "core_colors": ["U", "R"], "splash_colors": [], "splash_candidates": [],
    "clusters": ["Spellslinger", "Flashback/GY-Cast"],
    "pipeline_band": 37, "staple_band": 38, "threat_band": 25, "engine_band": 11,
    "seed_total": 111,
    "staple_cap": 40, "staple_dropped": [],
    "threat_cap": 25, "threat_dropped": [], "engine_cap": 25, "engine_dropped": []
  },
  "include_candidates": [
    { "card": "High Tide", "band": "pipeline", "usable_as": null,
      "count_dependent": false,
      "reason": "<one line, grounded in this card's oracle_text and THIS pipeline>" },
    { "card": "Delver of Secrets // Insectile Aberration", "band": "pipeline", "usable_as": null,
      "count_dependent": true,
      "reason": "flip rate = instant/sorcery density — verdict deferred to 5B step 6" }
  ],
  "considered_but_excluded": [
    { "card": "Helm of Awakening", "notable": true,
      "reason": "<one-line mechanism against THIS pipeline>" },
    { "cards": ["…", "…", "…"], "notable": false,
      "reason": "<one shared mechanism reason for a batch cut>" }
  ]
}
```

- `include_candidates` — the slice you draft the skeleton from and the Step 0 critic reads. One oracle-grounded line each, scoped to this pipeline.
- `considered_but_excluded` — the rest of the seed, all of it. A `cards` array cuts a batch under one shared mechanism reason, so subtracting thirty off-plan staples costs one line, not thirty. `notable: true` marks the cuts a reader would ask about; those are what Phase 10 renders as `### CARDS CONSIDERED BUT EXCLUDED`.
- **Count-dependent cards are not subtracted here.** A card whose value is a count has no denominator at 5A — the list it would be counted against is what 5B produces. It stays in `include_candidates` with `"count_dependent": true`, and its verdict is written at step 6 (SKILL.md, the Counts Principle).

Write it to `_workspace/<run-token>/<deck-dir>/sweep.json`. This is the **only** artifact for the partition — write the annotations straight into it. Do not stage them through a separate `part_deckN.json` and then copy them across: that stores the same include/exclude reasons twice in two formats and gives the run two things that can disagree. `sweep.json` ships in the Phase 8 Challenger bundle.

### 3. Verify before locking

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/seed_sweep.py \
    --run <run-token> --deck <deck-dir> --verify
```

It asserts the partition is exact: every seed card recorded in exactly one list, none in both, and no count-dependent card sitting in the excluded list. A card in the seed and in neither list is the exact failure this section exists to prevent — fix and re-run until it passes. Whether a card *is* count-dependent is a reading of oracle text, not an assert; that half is checked by the Challenger (`references/challenger-template.md` item 11).

## Phase 5B — the build steps (Step 0, then the seven)

**Step 0 — PROPOSE → CRITIQUE → LOCK (every build, before you classify).** Do not pick a build and run with it unexamined. Pin the archetype family, draft the skeleton, have one independent critic attack it, then lock. This runs on **every** build — when the pool supports only one build the critic returns `false_choice` and the commitment is confirmed; there is no "clean pipeline" skip.

*Why one critic and not a race.* This step was originally three parallel sketchers plus a shape judge. That design was justified by an **archetype** blind-spotting problem — five independent builders classified Aggro ×4 / Midrange ×1 and never surfaced the pool-supported Combo shape. The fix that actually solved it was pinning `archetype_family` before dispatch, two days later: sketches became builds of ONE archetype and could no longer span archetypes. The race outlived its own justification. Measured over a four-deck run the judge picked the first-dispatched sketch 4/4 — zero variation for ~120k tokens per deck — while the useful output (weak keystones, harvests) came from adversarial oracle-reading, which one critic does at a quarter of the cost. The pool-wide "is there a better card" question is Phase 9's job and Phase 9 does it better, because it has a denominator.

*0a. Pin the archetype family, then draft the skeleton yourself.*

- **Pin the `archetype_family` (one line, grounded).** Map `default_role` → macro-archetype: `combo` → **combo**; `aggressor` → **aggro** *or* **tempo**; `controller` → **control** *or* **midrange**. Break the two-way ties with the intent and the curve/interaction shape of the `include_candidates` (e.g. "aggressor + a two-mana interaction-heavy curve + Competitive → **tempo**"). State the family and the one-line grounds.
- **Draft the skeleton** from `include_candidates` only (IRON RULE — never from prior knowledge): `{macro_archetype, slot_table (% + count per the table below), land_pip_implication (one line), keystone_package, rationale}`. The **keystone_package** is the payoff cluster + the 3–5 load-bearing cards that define this plan — not the full deck — each with its assigned role and its `oracle_text` quoted from the slice. The build must deliver the thesis `kill_mechanism` by the `goldfish_turn`.

*0b. Dispatch ONE skeleton critic* (independent subagent; the SKILL.md Phase Protocol markers apply — announce it, verify BEGIN/END before use). Its input bundle is EXACTLY: your drafted skeleton (slot table + keystone package with the oracle text quoted), the fixed `archetype_family` + grounds, the locked `thesis` (`kill_mechanism`, `goldfish_turn`, `default_role`), the Phase 1 intent + power level, the slot band table below + format / deck size N (+ commander identity if any), `core_colors` / `splash_colors`, and the Phase 5A `include_candidates` slice with each card's `oracle_text`, `type_line`, `mana_cost`, `cmc` and `usable_as`. Give it **no wider pool, no dossier, and no signal that the skeleton is yours or that you want it upheld** — present it as "a proposed skeleton". State its contract as a recipe:

- *Its job is to attack, not to approve.* Returning "looks good" with an empty `strongest_alternative` is a failed report unless it also argues why no materially different build exists.
- *Output (fixed shape):*
  - `weak_keystones` — every keystone whose **quoted oracle text** does not support its assigned role. Quote the clause (or name the absent clause) for each. This is the same test the old shape judge applied, unchanged.
  - `strongest_alternative` — the best *materially different* build the same slice supports, argued **against** the thesis: its lens in one line, its slot table, the cards it would add and what it cuts, and the one line on why a builder might prefer it. Use the lens menu below as a starting point.
  - `false_choice` — set only when the slice genuinely supports no materially different build, with the mechanism reason (e.g. "the only payoff cluster with ≥4 members is X; every alternative is the same deck minus its best cards").
  - `thesis_risk` — one line: the most likely way this skeleton fails to deliver `kill_mechanism` by `goldfish_turn`.

  | Family | Lens menu for `strongest_alternative` |
  |---|---|
  | Combo    | fastest goldfish · most redundant assembly · most resilient to disruption |
  | Aggro    | lowest-curve / most explosive · most reach & evasion · most resilient to sweepers |
  | Tempo    | most proactive clock · most interaction-dense · most card-advantage-leaning |
  | Control  | most proactive finisher · most reactive attrition · most engine-forward |
  | Midrange | most threat-dense / aggressive · most grindy value · most flexible toolbox |

*0c. Resolve and lock.* Steps 1–4 below now **record and refine** the skeleton rather than choose a build fresh. Two obligations flow into FILL (step 5): resolve **every** `weak_keystones` entry (swap the card or restate its role with the clause that does support it — never wave it through), and **harvest** `strongest_alternative` role-for-role, taking each card it named that beats your slot-mate on this pipeline. Record the whole selection as `build_output.skeleton_selection` (step 7):

```
{archetype_family, grounds, skeleton, critic_findings, weak_keystones, strongest_alternative, harvested}
```

*Known trade-off.* The skeleton is no longer pool-blind — you draft it, so anchoring is real. The mandatory `strongest_alternative` and Challenger item 6 are what hold against it. If a critic returns an empty `strongest_alternative` on a pipeline that plainly supports one, that is a signal this step has regressed to rubber-stamping; report it.

**1. CLASSIFY — lock the skeleton's classification.** The `archetype_family` was fixed in Step 0; record it and the projected average MV. This records the locked choice; it is not a fresh pick.

**2. ALLOCATE SLOTS — proportional to N.** State every slot as a percentage AND an absolute count `round(N × proportion)`, each with a one-sentence rationale tied to THIS pipeline. Land % is of deck_size N; nonland proportions are % of nonland cards.

| Slot                  | Tempo   | Combo   | Aggro   | Midrange       | Control |
|-----------------------|---------|---------|---------|----------------|---------|
| Lands                 | derived — step 3 | derived — step 3 | derived — step 3 | derived — step 3 | derived — step 3 |
| Interaction           | 25–35%  | 10–20%  | 10–15%  | 20–30%         | 35–45%  |
| Threats/Payoffs       | 10–18%  | 5–15%   | 45–55%  | 30–40%         | 5–10%   |
| Engine & Infra.       | 20–30%  | 40–50%  | 0–10%   | 0% (absorbed)  | 10–20%  |

**Midrange Engine & Infra. note:** Midrange does not reserve a separate Engine budget — the expectation is that Threats/Payoffs cards pull double duty. Prefer cards that generate value on their own, but don't reject a strong threat solely because it lacks explicit value text.

The ranges are guidance; the rationale must justify any deviation.

**3. LAND COUNT — call `deck_audit.land_target`; do not derive a count by hand.**

The land count is a computed value, not a percentage read off a table:

```
base(N) = the land count maximizing P(2–4 lands in an opening hand of 7)   → 17 at N=40, 25 at N=60
target  = base(N) + [ 2·(avg MV − 2.5) − 0.25·(cantrips + ramp) ] · (N/60)
```

The land count is a function of deck size, curve and acceleration only — there is **no
per-archetype term**. Average mana value already carries how fast or slow a deck plays, so a
control deck lands more only because its curve is higher, not because of a seat bonus.

The opening hand is a fixed 7 cards at every deck size, so the land *fraction* that produces a
good opener is not scale-invariant and a percentage carried over from 60-card constructed is
wrong at 40 cards. Solving the opening hand per deck size is what makes the base correct; the
curve and acceleration terms then shape the count around it.

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/land_math.py \
    --run <run-token> --deck <deck-dir> [--avg-mv <projected>] [--accel <n>]
```

Without the optional flags it derives avg MV and `accel_count` from the deck as it stands; pass them at step 3 when the mainboard does not exist yet. On the commander formats it prints `NOT APPLICABLE for commander` and defers to Burgess/Karsten — those formats do not use this function and their `land_target_trace` is `null` by design.

Record the returned dict **verbatim** as `land_math.target`. Its `recommended_land_count` is the
count you build to. Do not recompute, round, or adjust any of its numbers by hand — the same
function is what Phase 6 audits against, so a hand-derived count creates a disagreement the audit
will flag.

Two fields need reading, not just recording:
- `clamped: true` means the target ran outside the sane land-fraction band and the guardrail bit.
  That is a signal your projected avg MV is extreme for this deck size — re-check it before
  accepting the number rather than treating the clamped value as the answer.
- `adjustment` is how far the deck's curve, acceleration and seat moved it off `base_lands`. A
  deviation from `recommended_land_count` needs a thesis-grounded reason stated in
  `land_math.deviation`, and should stay within 1 of it.

**Composition, not count.** Read `dossier.mana_infrastructure` before choosing *which* lands fill
the slots — `enters_tapped`, `conditionally_tapped` and `self_bounce` are flags the audit cannot
see. These change composition, never the count: a self-bouncing land swaps a land rather than
adding one, and an MDFC with a land back fills a land slot. Note these in
`land_math.composition_notes`.

**Re-derive after FILL.** This step runs on the *projected* avg MV. After step 5, recompute avg MV
from the actual mainboard and call `land_target` again. If the recommendation moved by more than
1, adopt the new count and adjust the list — the same recount-on-a-moved-denominator discipline as
the Counts Principle. Record both calls in `land_math`.

**4. MANA SOURCES.** Count colored pips across core-color cards only. Compute each core color's pip share. Distribute producing lands proportionally. If `splash_colors` is non-empty, allocate 2–3 dedicated sources per splash color out of the remaining land slots; splash pips are excluded from the proportional math. State the pip counts and the derived split:

> "14 blue pips, 8 black pips (64% / 36%). Targeting 11 blue sources and 6 black sources out of 17 total lands."

**Land-property census — required only when a locked-pipeline core card's function scales with a property of lands you control** (a land-type word — Island, Swamp…; "basic land"; snow; your land count / Domain). For each such property, enumerate from `type_line` which pool lands have it: a land has a type iff its type line says so — `Land — Island Mountain` IS an Island; "basic" is a supertype, not a land type. Record the census in `land_math` as `{"<property>": [<qualifying pool lands>]}` and allocate that property's sources from the qualifying set first. Excluding or capping a census member is a decision with a stated mechanism cost (e.g. its enters-tapped cost against this deck's thesis turn). No qualifying core card → no census.

**5. FILL.** For every card: quote `oracle_text` from the working pool cache before including it; verify against `card_pool_rules`; build a running restrictions checklist.

Read `taxonomic_profile.resource_exchange` alongside the oracle text — it is the card's resource ledger (`Mana:`/`Cards:`/`Board:`/`Life:` labels; empty = neutral). When the key is absent (cube tagged before the pillar existed), derive the same labels from oracle text for the cards you evaluate. Two obligations follow:
- Every mainboard card tagged `Cards: Extra-Cost` or `Board: Sacrifice-Cost` must have its cost **fed**, stated as a count per the Counts Principle: how many cards in this list can pay that cost when it matters?
- Every `Mana: Ongoing-Cost` card gets one line in the mana reasoning stating how this deck keeps paying it.

**Harvest the rejected builds (from Step 0).** The losing builds' keystones are FILL candidates for the locked build — a card another lens surfaced does not die just because its build lost. Review each and include any that fit the locked slot allocation **role-for-role**; do NOT add a new role or widen a slot to fit one (that re-blends the builds the judge rejected). Record what you pull in as `skeleton_selection.harvested_from_rejected`. Also resolve every `weak_keystones` entry the judge flagged: replace the card or justify it with thesis grounds here — never carry an unresolved one to Phase 9.

**6. COUNT-DEPENDENT VERDICTS (the Counts Principle).** For every inclusion or rejection whose value turns on how many other cards qualify (cost reducers, tribal/type-matters payoffs, storm/spell-count triggers, graveyard counts, devotion, threshold, metalcraft, delirium, domain, affinity), state the count as a numerator/denominator against **this deck's list** — not an adjective. Compute it against the mainboard you actually built; if you later swap a card and a denominator moves, recount.

This step is also where every Phase 5A `count_dependent: true` card gets its verdict — INCLUDE or CUT, with the count against this mainboard. A deferred card that reaches Phase 6 without a verdict is an incomplete step 6.

> "Helm of Awakening discounts every nonland card with a generic component: 18 of the 24 nonland cards qualify. INCLUDE."

**7. Record your derivation** as `build_output` (this feeds the grill bundle and Phase 10):
`macro_archetype`, `projected_avg_mv`, `deck_identity` (2–4 sentences), `thesis_turn` and `default_role` (copied from the locked pipeline's thesis), `slot_allocation`, `land_math`, `pip_math`, `count_dependent_verdicts` (step 6's output — one entry per card flagged at 5A, so the Challenger's item 9 recount has a target), `mainboard` (name/qty/role), `sideboard` (name/qty/role/when_to_board), `restrictions_checklist`, and `skeleton_selection` (Step 0's record: `{archetype_family, grounds, skeleton, critic_findings, weak_keystones: [{card, role, missing_clause, resolution}], strongest_alternative, false_choice, thesis_risk, harvested: [{card, role, taken: bool, why}]}`). Phase 6b appends `structural_checks`, `structural_responses`, `coverage`, and `failure_modes`. Phase 10 appends `analysis_body` — the free-form observations under `## ANALYSIS`, everything after `### DECK IDENTITY` and before the generated sections. It is the **only** prose `render_save.py` takes from you; every other section of `analysis.md` is derived from the deck arrays, so leaving this key out yields an analysis with tables and no argument.

## Phase 5C — the pre-flight checks (deterministic)

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/validate_build.py \
    --run <run-token> --deck <deck-dir>
```

It exits nonzero on any failure. Every check is a string or number comparison — none is a judgment:

1. Mainboard count (summing `qty`) == `deck_size` (+ commander). Sideboard == `sideboard_size`.
2. Every `name` exists by **exact string match** in the working pool cache (synthesized basics count — they are in the cache).
3. Copy counts obey `card_pool_rules` — cross-check with `cube_search.get_max_copies`. **Basic lands are exempt**: unlimited copies unless the user explicitly restricted them.
4. Every nonland card is **usable** in `core_colors` ∪ `splash_colors` (or the commander's identity) — test it with `effective_cost.best_mode(card, core_colors, splash_colors)` returning non-`None`, **not** by hand-checking raw `color_identity`. A card whose printed identity is off-colour but which has a colourless/in-colour replacement mode (e.g. Street Wraith's cycling, a kicker card cast in its base colour) is legal; `best_mode` returns the matched mode, and `search_pool` already stamped it with `usable_as`. Re-deriving the raw-identity subset here would contradict the pool gate and wrongly reject those cards — call the same helper. Record each off-identity inclusion's `usable_as` so Phase 9 knows it is in for that mode only.
5. ≤ 3 cards for each splash color, and every splashed card is in `splash_candidates`.

Fix any failure directly (you built the deck; you repair it), then re-run until all pass. Do not proceed to Phase 6 with a failing check, and never hand-patch a validator to make it agree.

## Phase 6b — structural gate invocation

Write `role_counts` + `coverage_declaration` + `macro_archetype` + `thesis_turn` to a `checks.json` in the run dir, then:

```
PYTHONPATH=. PYTHONIOENCODING=utf-8 python skills/build-deck/scripts/structural.py \
    --run <run-token> --deck <deck-dir> --checks <checks.json>
```

It qty-expands the mainboard, pulls `threat_profile` from the cube dossier, prints the formatted report and writes `structural.json`; exit 1 means FAIL. Thresholds live in `cuber/deck_checks.py` and are never re-derived by hand.

**Inputs you assemble first:** `role_counts` counts the mainboard cards whose assigned role is a pipeline payoff or enabler (functional copies, qty-expanded). A value is either a plain int (every copy fully reliable) or a per-copy list mixing `{"qty": k}` entries with weighted ones: `{"card": "<name>", "weight": 0.8, "why": "<mechanism>"}`.

**Reliability weights are mandatory for conditional copies — effects in general, not just tutors.** A functional copy whose access or effect is conditional may not count as a full copy: a tutor whose cost can eat the fetched piece, a cast-from-hand-only trigger, an effect that needs another piece already on the battlefield, a symmetric effect the opponent can exploit first. Declare it at a weight below one with a one-line mechanism-grounded `why` — `assembly_check` raises on a discount without one. The weight is a builder claim, stated conservatively from oracle text. Name the mechanism in `why`; no ratio-count digits.

`coverage_declaration` maps each of the five threat classes — `wide_boards`, `single_large_threat`, `noncreature_permanents`, `stack`, `graveyard` — to either `{"cards": [<mainboard names>]}` or `{"conceded": "<one-line mechanism reason>"}`. A concession is legitimate (a fast enough clock answers everything) but it must be written; the cheapest lie is the class you never mention.

## `build_output.failure_modes` — six entries, mitigation XOR accepted

Reason through each mode against THIS deck. Mitigate only when doing so does not cost the deck's identity or winning plan — and when you don't mitigate, the acceptance states that cost. Each mode maps to exactly one of two shapes:

```json
"failure_modes": {
  "flood":             {"mitigation": "<mechanism line naming the cards or plan that address it>"},
  "screw":             {"accepted": "<what mitigating would cost the deck's identity or winning plan>"},
  "decapitation":      {"mitigation": "..."},
  "gas-out":           {"mitigation": "..."},
  "raced":             {"accepted": "..."},
  "disruption-fizzle": {"mitigation": "..."}
}
```

| Mode | The question it answers |
|------|------------------------|
| `flood` | What do excess lands do here — what turns a surplus land into action? |
| `screw` | Which hands are keepable on 2 lands, and what digs you out? |
| `decapitation` | What is the line when the key piece is answered on sight? |
| `gas-out` | What happens when the hand is empty? The storm/spell-count failure: the mana is there, the cards are not. What refuels a deck that must keep playing cards? Ground the answer in the deck's count of `Cards: Net-Positive` + `Cards: Self-Replacing` cards (resource_exchange). |
| `raced` | Against the fastest clocks in `dossier.threat_profile`, does this deck win or interact before it dies? |
| `disruption-fizzle` | The critical turn meets one piece of interaction — a counterspell, removal mid-chain. Does the plan survive, retry, or fold? Distinct from `decapitation`: this is the key TURN being interacted with, not the key CARD being answered on sight. |

A `mitigation` names the cards or plan in this list that address the mode, grounded in their oracle text. An `accepted` is legitimate — but it must state the identity/plan cost explicitly; "unlikely" or "not relevant here" is not a cost. The Challenger reviews all six as a checklist (its item 13); a missing mode or an empty reasoning is automatically UNSATISFIED and comes back as a BLOCKING finding.

The structural-gate report is stored as `build_output.structural_checks` and ships in the grill bundle. **Assembly and coverage are HARD gates** (see SKILL.md Phase 6b): a failure is repaired and re-run, not rationalized. `curve` and `goldfish` are WARN-tier — each flag gets one line in `build_output.structural_responses`.

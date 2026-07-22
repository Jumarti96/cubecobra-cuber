# build-deck reference — Phases 5–6b: build mechanics

Read at the start of Phase 5; covers the lightweight sweep, the Step-0 sketch-and-select gate, the seven-step build procedure, the pre-flight checks, and the Phase 6b structural-gate invocation. Mechanics only — the IRON RULE, the Counts Principle, and the gate semantics are in SKILL.md.

The build works from the whole filtered pool (the working pool cache), bounded by `core_colors`, `splash_colors`, and the named `splash_candidates`. There is no separate legal/index split — the grill bundle ships the full `working_pool`, and the sideboard and absence audit see the rest of the cube through it.

## Phase 5A — lightweight sweep

Record a short sweep before committing the list. It is **not** a total-coverage record of every pool card — only two bounded lists:

```json
{
  "run_token": "run-…",
  "pipeline_payoff": "<name>",
  "swept_at": "<ISO 8601 UTC>",
  "include_candidates": [
    { "card": "High Tide", "reason": "<one line, grounded in this card's oracle_text and THIS pipeline>" }
  ],
  "considered_but_excluded": [
    { "card": "Helm of Awakening", "reason": "<one-line mechanism; count-dependent claims obey the Counts Principle>" }
  ]
}
```

- `include_candidates` — the cards you are building from. One oracle-grounded line each, scoped to this pipeline.
- `considered_but_excluded` — a **bounded** list of cards a reader would reasonably expect in this deck that you rejected. Not every off-plan card in the pool; the ones worth explaining. Each gets a one-line mechanism reason. This list becomes the `### CARDS CONSIDERED BUT EXCLUDED` section of the analysis (Phase 10).

Write it to `_workspace/<run-token>/sweep.json` (kept in the workspace; it is not a saved deck file).

## Phase 5B — the build steps (Step 0, then the seven)

**Step 0 — SKETCH → JUDGE → LOCK (every build, before you classify).** Do not pick a build and run with it. Pin the archetype family, sketch a few **builds of that one archetype**, have an independent judge pick one, then build from the winner. This runs on **every** build — when the pool supports only one build the sketches converge and the judge simply confirms the commitment; there is no "clean pipeline" skip. (Rationale: a single builder committing greedily both varies wildly run-to-run and develops blind spots — it silently never considers a whole viable **build** of the archetype. Independent parallel sketchers, one per lens, are how three genuinely different builds get considered instead of one mind's first instinct three times.)

*0a. Pin the archetype family, then dispatch one sketcher per lens.* The sketches are **builds of ONE archetype**, not competing archetypes — the family is already pinned by the locked `thesis.default_role` + the Phase 1 intent, so do not re-open it here.

- **Pin the `archetype_family` (one line, grounded).** Map `default_role` → macro-archetype: `combo` → **combo**; `aggressor` → **aggro** *or* **tempo**; `controller` → **control** *or* **midrange**. Break the two-way ties with the intent and the curve/interaction shape of the `include_candidates` (e.g. "aggressor + a two-mana interaction-heavy curve + Competitive → **tempo**"). State the family and the one-line grounds; it is fixed for every sketch below.
- **Assign 2–3 lenses** — each a different *build interpretation* of the pinned family — from this menu (starting points; pick only lenses the locked pipeline + `include_candidates` genuinely support). Default 3; drop to 2 only when the pool supports just two distinct builds, and say why (this replaces "do not fabricate divergence" — you never span archetypes now, so the only over-reach left is inventing a build the cards can't make):

  | Family | Interpretation lenses (assign 2–3 the pool supports) |
  |---|---|
  | Combo    | fastest goldfish · most redundant assembly · most resilient to disruption |
  | Aggro    | lowest-curve / most explosive · most reach & evasion · most resilient to sweepers |
  | Tempo    | most proactive clock · most interaction-dense · most card-advantage-leaning |
  | Control  | most proactive finisher · most reactive attrition · most engine-forward |
  | Midrange | most threat-dense / aggressive · most grindy value · most flexible toolbox |

- **Dispatch one sketcher subagent per lens, in parallel** (SKILL.md Phase Protocol markers apply — announce the wave, verify each report's BEGIN/END before use). Each is independent and blind to the others. State the contract as a recipe.
  - *Input bundle (EXACTLY):* the assigned `lens` (one line); the fixed `archetype_family` + its grounds; the locked `thesis` (`kill_mechanism`, `goldfish_turn`, `default_role`); the Phase 1 intent + power level; the slot band table below + format / deck size N (+ commander identity if any) + `core_colors` / `splash_colors`; and the Phase 5A `include_candidates` slice **with each card's `oracle_text`**. Give it **no other sketch, no signal of your preference, and no wider pool or dossier**.
  - *Build only from the provided slice* (IRON RULE — never from prior knowledge; do not invent cards). The family is fixed and the slice is cluster-scoped, so staying on-pipeline is bounded for free.
  - *Output (fixed shape) — one sketch:* `{macro_archetype (= the fixed family), lens, slot_table (% + count per the table below), land_pip_implication (one line), keystone_package, rationale (one line tying THIS build to its lens AND the thesis kill_mechanism)}`. The **keystone_package** is the payoff cluster + the 3–5 load-bearing cards that define THIS build's plan — not the full deck — each with its assigned role and its `oracle_text` quoted from the slice (the judge verifies role-fit from it and gets no pool). The build must deliver the thesis `kill_mechanism` by the `goldfish_turn`.

*0b. Dispatch the shape judge (independent subagent; the SKILL.md Phase Protocol markers apply — announce it, verify BEGIN/END before use).* Its input bundle is EXACTLY: the 2–3 returned sketches (all one `archetype_family`, differing by lens — shape + keystone names/roles + those keystones' oracle text), the locked pipeline `thesis` (`kill_mechanism`, `goldfish_turn`, `default_role`), the Phase 1 intent + power level, the slot band table below + format / deck size N (+ commander identity if any), and `core_colors` / `splash_colors`. Give it **no working pool, no dossier, and no signal of which sketch you prefer** — finding a better card in the pool is Phase 9's job; this judge only chooses among the builds the sketchers produced. State its contract as a recipe:
- *Rubric:* pick the build whose shape + keystone package best delivers the thesis kill mechanism by the goldfish turn, consistent with `default_role` and the intent, with each keystone's oracle text actually supporting its assigned role. A slot deviation from the bands is acceptable **only** with a thesis-grounded reason. Do **not** rank by "fewest deviations" — the most convincing plan wins even if it deviates more. A lens is a design brief, not a virtue: do **not** reward or penalize a build for its lens per se (e.g. do not dock the resilient build merely for being slower than the fast one) — judge on thesis delivery + intent fit.
- *Output (fixed shape):* a ranked pick with one line of grounds per sketch; `weak_keystones` (any keystone whose oracle text does not support its assigned role); `false_choice` (an informational note if the builds are not materially distinct). One whole build wins — the judge never blends sketches and never names a pool card.

*0b-bis. Record the phase.* Sketchers and judge are independent agents (however your environment dispatches them); the run is not allowed to continue on an unrecorded 5B. On success: `python -m cuber.orchestrator record <run_id> phase_05b_sketch_judge --mode independent --agents-file <file>` with every sketcher report **and** the judge report verbatim. If any dispatch fails: `python -m cuber.orchestrator fail <run_id> phase_05b_sketch_judge --error "..."` and stop — never sketch or judge inline to keep the build moving (see `references/orchestrator.md`).

*0c. Lock the winner.* Adopt the judge's picked build as the skeleton; steps 1–4 below now **record and refine** it rather than choose a build fresh. Record the fixed `archetype_family` and the winner's `lens`. Two obligations flow into FILL (step 5): resolve every `weak_keystones` entry, and **harvest** the rejected builds. Record the whole selection as `build_output.skeleton_selection` (step 7).

**1. CLASSIFY — lock the selected skeleton's classification.** The `archetype_family` was fixed in Step 0; record it, the winner's `lens`, and the projected average MV. This records the locked choice; it is not a fresh pick.

**2. ALLOCATE SLOTS — proportional to N.** State every slot as a percentage AND an absolute count `round(N × proportion)`, each with a one-sentence rationale tied to THIS pipeline. Land % is of deck_size N; nonland proportions are % of nonland cards.

| Slot                  | Tempo   | Combo   | Aggro   | Midrange       | Control |
|-----------------------|---------|---------|---------|----------------|---------|
| Lands                 | 30–34%  | 30–36%  | 30–35%  | 38–42%         | 42–47%  |
| Interaction           | 25–35%  | 10–20%  | 10–15%  | 20–30%         | 35–45%  |
| Threats/Payoffs       | 10–18%  | 5–15%   | 45–55%  | 30–40%         | 5–10%   |
| Engine & Infra.       | 20–30%  | 40–50%  | 0–10%   | 0% (absorbed)  | 10–20%  |

**Midrange Engine & Infra. note:** Midrange does not reserve a separate Engine budget — the expectation is that Threats/Payoffs cards pull double duty. Prefer cards that generate value on their own, but don't reject a strong threat solely because it lacks explicit value text.

The ranges are guidance; the rationale must justify any deviation.

**3. LAND COUNT.** State the baseline, then every modifier explicitly, even when zero:
- **Cantrips:** −1 land per 3 one-mana filtering/draw spells
- **Mana dorks/rocks:** −0.5 land per 2 cheap non-land mana sources (MV ≤ 2)
- **MDFCs with a land back:** −0.5 if spell side is situational; −0.3 if spell side is a primary engine piece

> "Baseline: 16 (40% of N=40). Modifiers: −1 cantrip, −0 infra, −0 MDFC. Final: 15 lands."

Read `dossier.mana_infrastructure` before choosing the mana base — `enters_tapped`, `conditionally_tapped` and `self_bounce` are flags the audit cannot see. A self-bouncing land swaps a land rather than adding one.

**4. MANA SOURCES.** Count colored pips across core-color cards only. Compute each core color's pip share. Distribute producing lands proportionally. If `splash_colors` is non-empty, allocate 2–3 dedicated sources per splash color out of the remaining land slots; splash pips are excluded from the proportional math. State the pip counts and the derived split:

> "14 blue pips, 8 black pips (64% / 36%). Targeting 11 blue sources and 6 black sources out of 17 total lands."

**Land-property census — required only when a locked-pipeline core card's function scales with a property of lands you control** (a land-type word — Island, Swamp…; "basic land"; snow; your land count / Domain). For each such property, enumerate from `type_line` which pool lands have it: a land has a type iff its type line says so — `Land — Island Mountain` IS an Island; "basic" is a supertype, not a land type. Record the census in `land_math` as `{"<property>": [<qualifying pool lands>]}` and allocate that property's sources from the qualifying set first. Excluding or capping a census member is a decision with a stated mechanism cost (e.g. its enters-tapped cost against this deck's thesis turn). No qualifying core card → no census.

**5. FILL.** For every card: quote `oracle_text` from the working pool cache before including it; verify against `card_pool_rules`; build a running restrictions checklist.

Read `taxonomic_profile.resource_exchange` alongside the oracle text — it is the card's resource ledger (`Mana:`/`Cards:`/`Board:`/`Life:` labels; empty = neutral). When the key is absent (cube tagged before the pillar existed), derive the same labels from oracle text for the cards you evaluate. Two obligations follow:
- Every mainboard card tagged `Cards: Extra-Cost` or `Board: Sacrifice-Cost` must have its cost **fed**, stated as a count per the Counts Principle: how many cards in this list can pay that cost when it matters?
- Every `Mana: Ongoing-Cost` card gets one line in the mana reasoning stating how this deck keeps paying it.

**Harvest the rejected builds (from Step 0).** The losing builds' keystones are FILL candidates for the locked build — a card another lens surfaced does not die just because its build lost. Review each and include any that fit the locked slot allocation **role-for-role**; do NOT add a new role or widen a slot to fit one (that re-blends the builds the judge rejected). Record what you pull in as `skeleton_selection.harvested_from_rejected`. Also resolve every `weak_keystones` entry the judge flagged: replace the card or justify it with thesis grounds here — never carry an unresolved one to Phase 9.

**6. COUNT-DEPENDENT VERDICTS (the Counts Principle).** For every inclusion or rejection whose value turns on how many other cards qualify (cost reducers, tribal/type-matters payoffs, storm/spell-count triggers, graveyard counts, devotion, threshold, metalcraft, delirium, domain, affinity), state the count as a numerator/denominator against **this deck's list** — not an adjective. Compute it against the mainboard you actually built; if you later swap a card and a denominator moves, recount.

> "Helm of Awakening discounts every nonland card with a generic component: 18 of the 24 nonland cards qualify. INCLUDE."

**7. Record your derivation** as `build_output` (this feeds the grill bundle and Phase 10):
`macro_archetype`, `projected_avg_mv`, `deck_identity` (2–4 sentences), `thesis_turn` and `default_role` (copied from the locked pipeline's thesis), `slot_allocation`, `land_math`, `pip_math`, `mainboard` (name/qty/role), `sideboard` (name/qty/role/when_to_board), `restrictions_checklist`, and `skeleton_selection` (Step 0's record: `{chosen, archetype_family, chosen_lens, rejected_sketches: [{lens, slot_table, keystones, why_rejected}], judge_grounds, weak_keystones, false_choice_note, harvested_from_rejected: [{card, from_lens, role}]}`). Phase 6b appends `structural_checks`, `structural_responses`, `coverage`, and `failure_modes`.

## Phase 5C — the pre-flight checks (deterministic)

Write `_workspace/<run-token>/_tmp_validate_build.py` and run these before the grill. Every check is a string or number comparison — none is a judgment:

1. Mainboard count (summing `qty`) == `deck_size` (+ commander). Sideboard == `sideboard_size`.
2. Every `name` exists by **exact string match** in the working pool cache (synthesized basics count — they are in the cache).
3. Copy counts obey `card_pool_rules` — cross-check with `cube_search.get_max_copies`. **Basic lands are exempt**: unlimited copies unless the user explicitly restricted them.
4. Every nonland `color_identity` ⊆ `core_colors` ∪ `splash_colors` (or the commander's identity).
5. ≤ 3 cards for each splash color, and every splashed card is in `splash_candidates`.

Fix any failure directly (you built the deck; you repair it), then re-run until all pass. Do not proceed to Phase 6 with a failing check, and never hand-patch a validator to make it agree.

## Phase 6b — structural gate invocation

```python
from cuber import deck_checks
report = deck_checks.run_structural_checks(
    mainboard_cards,            # one dict per copy (expand qty)
    macro_archetype,            # from Phase 5B step 1
    thesis_turn,                # from the locked pipeline's thesis
    role_counts,                # {"payoff": n | [copy entries], "enabler": ...} — functional copies, reliability-weighted
    coverage_declaration,       # see below
    threat_profile=dossier["threat_profile"],
    seed=0,
)
```

Display `deck_checks.format_checks_report(report)`.

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

A `mitigation` names the cards or plan in this list that address the mode, grounded in their oracle text. An `accepted` is legitimate — but it must state the identity/plan cost explicitly; "unlikely" or "not relevant here" is not a cost. The Challenger reviews all six as a checklist (its item 12); a missing mode or an empty reasoning is automatically UNSATISFIED and comes back as a BLOCKING finding.

The structural-gate report is stored as `build_output.structural_checks` and ships in the grill bundle. **Assembly and coverage are HARD gates** (see SKILL.md Phase 6b): a failure is repaired and re-run, not rationalized. `curve` and `goldfish` are WARN-tier — each flag gets one line in `build_output.structural_responses`.

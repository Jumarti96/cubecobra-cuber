# build-deck reference — Phases 5–6b: build mechanics

Read at the start of Phase 5; covers the lightweight sweep, the seven-step build procedure, the pre-flight checks, and the Phase 6b structural-gate invocation. Mechanics only — the IRON RULE, the Counts Principle, and the gate semantics are in SKILL.md.

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

## Phase 5B — the seven build steps

**1. CLASSIFY.** Choose one macro-archetype that fits the pipeline: Tempo / Combo / Aggro / Midrange / Control. State the classification and the projected average MV.

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

**5. FILL.** For every card: quote `oracle_text` from the working pool cache before including it; verify against `card_pool_rules`; build a running restrictions checklist.

Read `taxonomic_profile.resource_exchange` alongside the oracle text — it is the card's resource ledger (`Mana:`/`Cards:`/`Board:`/`Life:` labels; empty = neutral). When the key is absent (cube tagged before the pillar existed), derive the same labels from oracle text for the cards you evaluate. Two obligations follow:
- Every mainboard card tagged `Cards: Extra-Cost` or `Board: Sacrifice-Cost` must have its cost **fed**, stated as a count per the Counts Principle: how many cards in this list can pay that cost when it matters?
- Every `Mana: Ongoing-Cost` card gets one line in the mana reasoning stating how this deck keeps paying it.

**6. COUNT-DEPENDENT VERDICTS (the Counts Principle).** For every inclusion or rejection whose value turns on how many other cards qualify (cost reducers, tribal/type-matters payoffs, storm/spell-count triggers, graveyard counts, devotion, threshold, metalcraft, delirium, domain, affinity), state the count as a numerator/denominator against **this deck's list** — not an adjective. Compute it against the mainboard you actually built; if you later swap a card and a denominator moves, recount.

> "Helm of Awakening discounts every nonland card with a generic component: 18 of the 24 nonland cards qualify. INCLUDE."

**7. Record your derivation** as `build_output` (this feeds the grill bundle and Phase 10):
`macro_archetype`, `projected_avg_mv`, `deck_identity` (2–4 sentences), `thesis_turn` and `default_role` (copied from the locked pipeline's thesis), `slot_allocation`, `land_math`, `pip_math`, `mainboard` (name/qty/role), `sideboard` (name/qty/role/when_to_board), `restrictions_checklist`. Phase 6b appends `structural_checks`, `structural_responses`, `coverage`, and `failure_modes`.

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

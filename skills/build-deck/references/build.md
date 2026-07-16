# build-deck reference — Phases 5–6b: build mechanics

Read at the start of Phase 5; covers pool tiers, sweep file shapes, the seven-step build procedure, quantitative-verdict specs, the 5D checks, and the Phase 6b invocation. Mechanics only — the binding rules (sweep rules, gate semantics, IRON RULES) are in SKILL.md.

## Phase 5A — pool tiers (`pool_tiers.json`)

| Key | Contents | Why it exists |
|-----|----------|---------------|
| `legal_pool` | **Full records incl. `oracle_text`** for: every card with `color_identity ⊆ core_colors`, **plus** all lands, **plus** all colourless cards, **plus** the bounded `splash_candidates` list from Phase 3 — and nothing else | The sweep's domain, and the Challenger's evidence base. Every include, every oracle citation, every swap must come from here |
| `cube_index` | The **disjoint complement** of `legal_pool` — every cube card *not* in it. Fields: `name`, `colors`, `color_identity`, `cmc`, `type_line`, `rarity`, `tags`. **No `oracle_text`, no `taxonomic_profile`** | What the *opponent* can do; spotting a dead colour. Cheap. |

**Precompute per `legal_pool` card** (machine-derived; this is what every audit otherwise re-scripts): `pips` — a dict of colored-pip counts from `mana_cost` (e.g. `{"U": 2}`); `has_generic` — whether the mana cost contains a generic component; `subtypes` — creature subtypes from `type_line`.

**`legal_pool` and `cube_index` are disjoint, and their union is the whole cube.** Never ship a card in both — that duplication once made a 4-colour bundle 78% *larger* than shipping the raw pool. **Sanity-check before proceeding:** if `len(legal_pool) + len(cube_index) != len(working_pool)`, the tiers overlap or drop cards — fix it before anything else runs.

**Never filter to on-colour cards alone.** A sideboard is built against the *rest of the cube*: "there is no artifact removal in mono-red — every answer in this cube is W/G/multicolour" is a fact you can only see with the whole cube in view. `cube_index` + `dossier.threat_profile` is what makes that possible without paying for 271 oracle texts.

## Phase 5B — sweep entry and file shapes

Each `legal_pool` card gets one entry:

```json
{
  "card": "High Tide",
  "verdict": "INCLUDE | EXCLUDE_CONSIDERED | EXCLUDE_OFFPLAN",
  "reason": "<one line, grounded in this card's oracle_text and THIS deck's pipeline>"
}
```

Sweep rule 5 (rules 1–4 are in SKILL.md):
5. Write the result to `_workspace/<run-token>/attempt-<k>/sweep.json`:

```json
{
  "run_token": "run-…",
  "attempt": 1,
  "pipeline_payoff": "<name>",
  "swept_at": "<ISO 8601 UTC>",
  "legal_pool_count": 138,
  "entries": [ … ]
}
```

## Phase 5C — the seven build steps

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

**4. MANA SOURCES.** Count colored pips across core-color cards only (the precomputed `pips` field). Compute each core color's pip share. Distribute producing lands proportionally. If `splash_colors` is non-empty, allocate 2–3 dedicated sources per splash color out of the remaining land slots; splash pips are excluded from the proportional math. State the pip counts and the derived split:

> "14 blue pips, 8 black pips (64% / 36%). Targeting 11 blue sources and 6 black sources out of 17 total lands."

**5. FILL.** For every card: quote `oracle_text` from `legal_pool` before including it; verify against `card_pool_rules`; build a running restrictions checklist.

**6. QUANTITATIVE VERDICTS (IRON RULE 3).** Every count-dependent inclusion or rejection is recorded — and **a count is computed by `cuber.deck_counts`, never typed by hand**. Each verdict carries the integer AND the recipe that produced it:

```json
{
  "card": "Helm of Awakening",
  "claim": "discounts every nonland card with a generic component in its cost",
  "numerator": 18, "numerator_spec": { "predicate": "generic_reducible", "args": [["Helm of Awakening"]] },
  "denominator": 25, "denominator_spec": { "predicate": "nonland", "offset": -1 },
  "verdict": "INCLUDE"
}
```

- `numerator` / `denominator` are the return values of `deck_counts.resolve(deck, spec)` on **this deck's mainboard array** — compute them, do not transcribe them.
- `numerator_spec` / `denominator_spec` are the machine-readable recipes. A spec is `{ "predicate": <name>, "args": [...], "offset": <int> }`, or a bare int for a fixed literal (e.g. a target deck size). `offset` expresses a relative count such as `nonland - 1` (cards other than this one). Predicates: `nonland`, `lands`, `zero_cost`, `instants_sorceries`, `subtype_count(sub)`, `type_typed_lands(land_type)`, `generic_reducible(exclude_names)`, `color_cards(color)`, `pip_sum(color)`, `pip_sources(color)`, `oracle_matches(regex)`. Add a predicate to `cuber/deck_counts.py` if you need one that does not exist — never inline a bespoke recount.
- `claim` **names the predicate in words, with no count digits** (write "discounts every nonland card with a generic component", not "discounts 17 of 25"). The number lives only in the machine-checked `numerator`/`denominator`. This is what makes the count un-stale-able: there is exactly one copy of it, and Phase 5D recomputes it from the spec.

If you later swap a card and a denominator moves, the spec still recomputes correctly — re-run `deck_counts` and update the stored integers; never leave a transcribed number behind.

**The `*_spec` fields are builder-internal — strip them from the grill bundle (Phase 8).** The Challenger recounts every verdict independently against the deck array (its check 13); handing it the recipe would let it re-run your code instead of verifying you, defeating the cold check. Ship only `card`/`claim`/`numerator`/`denominator`/`verdict` to the Challenger; keep the specs in `build_output.json` on disk for the Phase 5D validator.

**7. Record your derivation** as `build_output` (this feeds the grill bundle and Phase 10):
`macro_archetype`, `projected_avg_mv`, `deck_identity` (2–4 sentences), `thesis_turn` and `default_role` (copied from the locked pipeline's thesis), `slot_allocation`, `land_math`, `pip_math`, `mainboard` (name/qty/role), `sideboard` (name/qty/role/when_to_board), `quantitative_verdicts`, `restrictions_checklist`. Phase 6b appends `structural_checks`, `structural_responses`, `coverage`, and `failure_modes`.

## Phase 5D — the eight deterministic checks

1. Mainboard count (summing `qty`) == `deck_size` (+ commander). Sideboard == `sideboard_size`.
2. Every `name` exists by **exact string match** in `legal_pool`.
3. Copy counts obey `card_pool_rules` — cross-check with `cube_search.get_max_copies`.
4. Every nonland `color_identity` ⊆ `core_colors` ∪ `splash_colors` (or the commander's identity).
5. ≤ 3 cards for each splash color.
6. Quantitative verdicts reproduce — call `deck_counts.check_verdicts(mainboard, quantitative_verdicts)`; it recomputes every `numerator`/`denominator` from its `*_spec` and returns the mismatches. A non-empty result fails the check. This is the **same `cuber.deck_counts` code the build used**, so a passing check means the stored integer and its recipe agree by construction — not two hand-written recounts that might both be wrong.
7. Sweep coverage — every `legal_pool` name appears exactly once in `sweep.json`; `legal_pool_count` matches.
8. No ratio counts in prose — for every mainboard/sideboard `role`, every `sweep.json` `reason`, and every verdict `claim`, `deck_counts.count_digits_in_prose(text)` returns empty. A ratio frame ("17 of the 25", "8 Island-typed", "out of 16 lands") means a number was hand-typed where a spec-backed verdict belongs — promote it to a `quantitative_verdicts` entry or reword qualitatively. Intrinsic card numbers ({R}{R}, "4 damage", "creates 10 Goblins") are not flagged; the guard catches ratio prose, and check 6 is the primary guarantee for every load-bearing count.

Both new checks import the shared module: `from cuber import deck_counts`. The build script and this validator therefore run identical counting logic — the guarantee is that they cannot disagree, so a stale count can never reach the grill.

## Phase 6b — structural gate invocation

```python
from cuber import deck_checks
report = deck_checks.run_structural_checks(
    mainboard_cards,            # one dict per copy (expand qty)
    macro_archetype,            # from Phase 5C step 1
    thesis_turn,                # from the locked pipeline's thesis
    role_counts,                # {"payoff": n, "enabler": m} — functional copies in the mainboard
    coverage_declaration,       # see below
    threat_profile=dossier["threat_profile"],
    seed=0,
)
```

Display `deck_checks.format_checks_report(report)`.

**Inputs you assemble first:** `role_counts` counts the mainboard cards whose assigned role is a pipeline payoff or enabler (functional copies, qty-expanded). `coverage_declaration` maps each of the five threat classes — `wide_boards`, `single_large_threat`, `noncreature_permanents`, `stack`, `graveyard` — to either `{"cards": [<mainboard names>]}` or `{"conceded": "<one-line mechanism reason>"}`. A concession is legitimate (a fast enough clock answers everything) but it must be written; the cheapest lie is the class you never mention.

# build-deck reference — Phase 9: the self-grill

Read at the start of Phase 9. Spawn **two** Agent calls that run in parallel — a Proposer and a Challenger. Neither sees the other's output during generation. Both read only `_workspace/<run-token>/grill_input.json` — never `enriched.json`, the working pool cache, or any other cube data file. Neither may use training-data knowledge of what a card does; every claim cites `oracle_text` from the bundle.

**Report markers (both dispatch prompts mandate this):** the agent's report opens with `=== PROPOSER REPORT — BEGIN ===` or `=== CHALLENGER REPORT — BEGIN ===` and closes with the matching `=== <ROLE> REPORT — END ===` line. The orchestrator verifies both markers before using a report; a report missing either is re-dispatched (SKILL.md Phase Protocol).

The bundle carries `deck`, `audit`, `card_pool_rules`, `restrictions_checklist`, `build_output`, `validation_report`, `working_pool` (the grill's evidence base and what the absence audit scans), and `dossier`.

---

## Proposer Agent

Defend the full deck list (main + sideboard). For every card:
- State its role in the strategy.
- Quote `oracle_text` from the `deck` array in the bundle: `Oracle: "..."`.
- Confirm it fits the locked pipeline (`build_output.deck_identity` / `thesis`).
- Confirm it passes the `card_pool_rules` check and that its `color_identity` is within constraint.
- Where a card's value turns on how many others qualify, state the count against this deck's list (numerator / denominator) — not an adjective.

---

## Challenger Agent

Attack the deck independently. You are the sole verifier for all hard checks. Work the list in order:

1. **Cube membership** — verify each card exists in the bundle's `working_pool` array by exact name; flag phantom inclusions (MUST be removed). Basic lands are exempt.
2. **Oracle text** — read `oracle_text` from the `deck` array independently; does each card actually do what its assigned role claims? For cards whose `taxonomic_profile.resource_exchange` declares `Cards: Extra-Cost` or `Board: Sacrifice-Cost` (or whose oracle text states such a cost), verify the deck feeds that cost — a count against this list, per the Counts Principle.
3. **Restrictions** — check every card against `card_pool_rules`; flag violations.
4. **Identity fit** — does each card contribute to the pipeline the deck was built around? Suggest cuts that do not.
5. **Better alternatives** — is there a card in `working_pool` that fills an occupied slot more efficiently? Check `taxonomic_profile` and `oracle_text` from the bundle.
6. **Proportional validation** — check `build_output.slot_allocation` against accepted deckbuilding ranges for `build_output.macro_archetype`. Flag deviations lacking adequate rationale.
7. **Sideboard cohesion** — a sideboard answers the REST OF THE CUBE, not this deck. Check it against `dossier.threat_profile` and the rest of the cube: which real threat classes does each slot answer, and is any significant threat class left unanswered? Are slots wasted on threats the cube does not contain?
8. **Mana audit re-run** — independently run `mana_audit` on the `deck` array; compare against the bundle's `audit` key; report every discrepancy.
9. **Derivation audit** — recompute `build_output.land_math` and `build_output.pip_math` from the actual `deck` array. Report arithmetic errors. Recount any count-dependent verdict the Proposer or `build_output` states; a verdict that was true of some other list is not true of this one. The builder's stated numbers are claims, not facts. Where a locked-pipeline core card scales with a property of lands you control, verify the land-property census in `land_math` against `type_line` in the bundle: a qualifying pool land missing from the census, or excluded/capped without a stated mechanism cost, is a finding — and a missing census is itself a finding.
10. **Absence audit** — ORACLE TEXT FIRST. Scan `working_pool` for cards NOT in the deck whose oracle text composes with the deck's pipeline or with cards already in the deck, deriving each composition from the oracle text itself. Cross-check `dossier.interaction_chains` for anything you missed — the chain list is a floor, not a ceiling. Name the strongest absences (up to 8). For each: quote the oracle mechanism and state, as a count against this deck's list, what it would do here. You are asking one question: is there a card in this pool that this deck should be running and is not? Reporting an absence is a finding; deciding about it is the builder's call.
11. **Pipeline viability** — can this pipeline actually achieve its stated win condition with the available card pool? If it cannot, state exactly:
    "This pipeline cannot achieve its stated win condition with the available card pool."
12. **Failure-mode review** — `build_output.failure_modes` must contain all six modes: `flood`, `screw`, `decapitation`, `gas-out`, `raced`, `disruption-fizzle` (definitions in the builder's spec; judge each against the `deck` array and `dossier.threat_profile`). Review each as a checklist and mark it **SATISFIED** or **UNSATISFIED**:
    - A `mitigation` is SATISFIED only if the named cards or plan are in the deck and their `oracle_text` supports the claim.
    - An `accepted` is SATISFIED only if it states a real identity/plan cost of mitigating — "unlikely" or "not relevant" is not a cost.
    - A missing mode or an empty reasoning is automatically UNSATISFIED.
    Every UNSATISFIED mark is a **BLOCKING** finding and must come with a concrete suggestion from `working_pool`.

Your own attacks are bound by the Counts Principle. You may not reject a card on a property of the card in isolation. "It is symmetric", "it only reduces generic mana", "it is win-more" are not findings. A finding is a count against this list, with a numerator and a denominator.

**Severity — tag every finding.** Each finding carries `severity: BLOCKING | ADVISORY`. **BLOCKING** = it materially affects legality, the deck's identity, or the winning plan: any hard-check violation (membership, restrictions, mana regression, structural failure, irreproducible count), an absence backed by an oracle-grounded count, an UNSATISFIED failure-mode review. **ADVISORY** = a marginal swap, a role-text quibble, a small proportional deviation. The builder cannot finalize the deck while a BLOCKING finding stands unresolved — tag severity as the evidence warrants, neither inflated nor softened.

**Output, in order:** your ranked findings (most-severe first — name the card, the problem, the `severity` tag, and the specific swap from `working_pool` where one applies), then the absence audit from (10), then the failure-mode checklist from (12).

## Challenger — approval round

After resolving, the orchestrator may message you again with its Resolution Table and the updated deck list. In that round:

- For each of your BLOCKING findings, verify the row: re-run the specific count or oracle check behind it against the updated list. Return **RESOLVED** or **UNRESOLVED** per finding, one line of reason each.
- A CONTEST row stands only on an oracle quote or a count you can reproduce; if the grounds hold, the finding is RESOLVED.
- Raise no new findings in an approval round unless a repair introduced a new hard-check violation.
- Open and close your reply with your report markers.

---

The orchestrator resolves the grill per SKILL.md Phase 9: a Resolution Table row for every finding, repair of every IMPLEMENT row, the approval round while BLOCKING findings remain (two-round cap), and the Re-evaluation Path only on the exact pipeline-viability trigger.

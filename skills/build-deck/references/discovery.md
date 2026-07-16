# build-deck reference — Phases 2–4: discovery mechanics

Read at the start of Phase 2; covers the dossier census, interaction-chain authoring, pipeline discovery, splash evaluation, and commander selection. Mechanics only — the binding rules (dossier admissibility, freeze, IRON RULES) are in SKILL.md.

## Phase 2 Step 0 — reading the dossier census

The machine census gives you, already computed:

| Key | What it answers |
|-----|-----------------|
| `environment` | Colour distribution, top tags, multicolour-reward signal density (domain / kicker / converge / sunburst) |
| `mana_infrastructure` | Every land by colour identity, with `enters_tapped`, `conditionally_tapped` and `self_bounce` flags; `duals_by_pair` with **free** duals separated from self-bouncing Lairs; `basics_in_pool` |
| `structural_census` | Rituals, mana producers with `net_mana`, cost reducers with their exact clause, sacrifice outlets (with `free` flag), tutors, sweepers, haste granters, graveyard hate |
| `tribal_rosters` | Every creature type with ≥4 members, split by colour identity |
| `threat_profile` | What the cube's **other** decks do — graveyard density, artifacts, enchantments, sweepers, lifegain, evasion, and artifact/enchantment answers **by colour**. This is what a sideboard is built against. |
| `pool_limits` | **Probe results, not constraints.** Positive findings name cards; 0-match findings report only that a probe matched nothing. |
| `census_caveat` | The reading rule for all of the above: a regex census proves presence, never absence. |

**Do not re-derive any of this by hand.** If you find yourself sweeping the pool for rituals, counting duals, or tallying a tribe, the answer is already in the dossier.

**But never trust a 0-match as an impossibility.** The census once reported "0 rituals" and agents concluded storm could not be accelerated — while High Tide, Frantic Search, Snap and Turnabout sat in the pool, invisible to the ritual probe. If a pipeline's viability turns on something the census says matched 0 cards, verify by reading oracle text before you rely on it.

**Fixing score** — read from `mana_infrastructure.duals_by_pair[pair]`, using the **`free`** count (Lairs cost a land drop and do not count):
- **GOOD** — ≥ 2 free duals for every pair in the identity
- **THIN** — 1 free dual, or only rare/self-bouncing fixing, for some pair
- **NONE** — 0 free duals for at least one pair

**Colour-count escalation** — apply when evaluating colour count. Skip when the user locked an identity in Phase 1, or when Phase 4 commander selection bound it.

| Colour count | Recommend when |
|-------------|----------------|
| 1 (Mono) | Pipeline is self-contained in one colour; fixing adds nothing |
| 2 | Default starting point |
| 3 | Fixing is GOOD for all pairs in the trio |
| 4 | Multicolour-reward signal present AND fixing GOOD for most pairs, OR `three_plus_color_lands` is deep |
| 5 | Strong multicolour-reward signal AND universal fixing, OR the user explicitly asked |

Never escalate colour count merely because the tag pool is larger. Fixing must justify the jump.

Produce an **Environment Characterization** sentence for the *user* from the dossier before proceeding. (This sentence is for the user. It does not go into any bundle — the dossier's numbers do.)

## Phase 2 Step 0b — authoring interaction chains

**Seed pass — run when `chains_seeded_at` is null (a fresh or never-seeded dossier).** Work through the cube's oracle text systematically, archetype family by archetype family — mana engines (untappers, multipliers, cost reducers, free spells), graveyard loops, sacrifice/death-trigger loops, type-changers, tokens, spells-matter, tribal payoffs, lands-matter — and author a chain for **every engine you find**, not just the ones near the current pipeline candidates. This is deliberately broader than one deck's needs: the seed pass runs once per cube and every future session inherits it. When done, set `chains_seeded_at` to the current ISO 8601 UTC timestamp in `dossier.json`.

**Incremental pass — every session:** read the oracle text of cards in and around the candidate pipelines; author any chain the seed pass missed.

**The chain list is a floor, never a ceiling** (`dossier.chains_caveat`). A pipeline is not thinner for lacking a chain, and a shortlist `thesis` must never require a chain to exist — an engine you derive from oracle text during discovery is exactly as real as a seeded one. Queue it for the Phase 12 write-back and use it now.

Chain format:

```json
{
  "id": "goblin-zombie-deadapult",
  "cards": ["Dralnu's Crusade", "Deadapult", "Skirk Prospector"],
  "mechanism": "Dralnu's Crusade: 'All Goblins are black and are Zombies in addition to their other creature types.' Deadapult: '{R}, Sacrifice a Zombie: This enchantment deals 2 damage to any target.' With Crusade on the battlefield every Goblin is a legal Deadapult sacrifice. Skirk Prospector: 'Sacrifice a Goblin: Add {R}' can fund the activation.",
  "requires": ["Dralnu's Crusade on the battlefield"],
  "color_identity": ["B", "R"]
}
```

Rules, and they are strict:
- `mechanism` **quotes oracle text** and states only how the cards compose. It is a claim that is true or false independent of any deck.
- **No evaluation words.** Not "strong", "the key combo", "worth building around", "a trap". See the admissibility rule in IRON RULE 2.
- Add chains, never verdicts. If you cannot express it as "A's text says X, B's text says Y, therefore Z is legal", it does not belong.
- **`color_identity` is the minimum identity required to execute the CORE mechanism** — the cards without which the chain does not function — not the union of every card named. A redundant or alternative card in another colour (a second sacrifice outlet, an optional enabler, a fund-the-cost helper) is listed in `cards` and described in `mechanism` as optional, but it **must not widen** `color_identity`. Worked example: the `goblin-death-to-damage` chain runs on Pashalik Mons + Skirk Prospector + Mogg War Marshal, all mono-red, so its identity is `["R"]`; Goblin Turncoat is a black *alternative* outlet and does not make the chain `["B","R"]`. Widening the identity hides the engine from every deck in the narrower colours — exactly the deck the chain most helps.


## Phase 2 Step 2 — Pipeline Discovery

**Find all Payoff candidates.**

Query the filtered pool for cards where `taxonomic_profile.structural_roles` contains `"Payload/Payoff"`. These are the win condition candidates.

If no cards have `"Payload/Payoff"`, fall back to cards with `"Standalone Threat"` as implicit payoffs and note this in the output.

**Validate each Payoff against its synergy cluster support.**

For each Payoff candidate:
1. Read its `taxonomic_profile.synergy_clusters`.
2. Count all cards in the pool whose `taxonomic_profile.synergy_clusters` overlap with the Payoff's clusters AND whose `taxonomic_profile.structural_roles` include `"Enabler/Fodder"` or `"Engine/Outlet"`.
3. Viability threshold: `round(N × 0.05)` supporting cards, where N is the target deck size.
4. If supporting card count ≥ threshold → pipeline is **viable**.
5. If supporting card count < threshold → pipeline is **non-viable** (exclude from shortlist).

**Apply color constraint if specified.**

If the user declared a color preference in Phase 1, also exclude Payoffs whose core pipeline cards (the Payoff + its primary support cards) fall outside the stated color identity.

**Build the shortlist.**

Collect all viable pipelines and rank them by intent (from Phase 1):
- `Competitive` → rank by highest count of Interaction/Disruption + Infrastructure/Consistency support cards in the pipeline's clusters
- `Experimental` → rank by highest cross-cluster overlap (Payoff shares synergy clusters with the most distinct card groups)
- `Fun / Niche` → rank by most unusual win condition (rarest synergy_cluster combination in the pool)
- `Specific Constraint` → rank by closest match to the user-stated constraint

Select the top 3–5 for the shortlist.

**Retain every viable pipeline as a structured object.** Each one is:

```json
{
  "payoff_card": "<name>",
  "synergy_clusters": ["..."],
  "support_card_names": ["..."],
  "support_count": 17,
  "viability_threshold": 2,
  "color_identity": ["U", "R"],
  "fixing_score": "GOOD",
  "thesis": {
    "kill_mechanism": "<the payoff's oracle text, and what converts board state into a win>",
    "interaction_chain_ids": ["goblin-zombie-deadapult", "..."],
    "goldfish_turn": 6,
    "default_role": "combo"
  }
}
```

`support_card_names` is a machine-derived cluster-overlap list and it is **fallible** — it will happily list a card whose oracle text is blank in the chosen colours. It is a starting point, never an instruction. Verify every name against oracle text; rejecting one is a correct outcome, not a failure.

`goldfish_turn` is the earliest realistic turn the kill mechanism executes against no resistance, derived from the mana math of the chain itself (oracle-grounded — never a meta claim). `default_role` is `aggressor` / `controller` / `combo`. Both are testable claims, not flavor: Phase 6b's assembly check and the Challenger's pipeline-viability check test the finished list against them.

`thesis` is what makes two sub-archetypes of the same payoff *distinguishable*. It is oracle-grounded and evaluation-free, exactly like `interaction_chains` — **state the mechanism, never the verdict.** Two shortlist entries whose theses do not name different kill mechanisms or different interaction chains are the same pipeline wearing two names — merge them rather than presenting a false choice.

If fewer than 3 viable pipelines exist, include all viable ones without padding.

If no viable pipelines exist, report:
> "No viable pipelines found in the current pool."

Ask whether to lower the viability threshold or change pool rules (restart Phase 0).

Tag density is still shown as context (count of Enabler/Fodder and Engine/Outlet per synergy cluster), but strategy selection is driven by the pipeline shortlist, not tag density alone.

## Phase 3 — Splash Evaluation

After locking the pipeline, scan the full pool for off-color cards whose `taxonomic_profile.synergy_clusters` overlap with the selected pipeline's clusters and whose `taxonomic_profile.structural_roles` include `"Payload/Payoff"` or `"Engine/Outlet"`. These are splash candidates — high-value cards that directly support the strategy but fall outside the core color identity.

For each candidate, check whether it qualifies as a splash:
- Its `color_identity` contains exactly 1 color not in `core_colors`
- No more than 3 cards of that off-color are being considered

If qualified candidates exist, set `splash_colors` to the list of off-color letters (e.g., `["R"]`) **and record the qualifying card names as `splash_candidates`** — a bounded list, at most 3 names per splash color. Otherwise set `splash_colors = []` and `splash_candidates = []`.

Do not present this evaluation to the user or ask for confirmation. Both criteria above are deterministic — this is a filter, not a judgment.

`core_colors`, `splash_colors` and `splash_candidates` define the pool tiers in Phase 5A; `core_colors` and `splash_colors` are also arguments to `deck_audit.mana_audit()` (Phase 6).

**`splash_candidates` is what bounds `legal_pool`.** A splash colour never admits its whole colour — only these named cards. Ignoring this ships ~100 unusable cards per splash colour, since only 3 of them can ever be legally included.

## Phase 4 — Commander Selection (Commander formats only)

Skip this phase for 40-card and 60-card formats.

Run `commander_finder.find_commanders(id, color_identity=chosen_colors)`.

Display the formatted table using `commander_finder.format_commanders_table(candidates)`.

Ask the user to select:
- **1 commander** — any eligible card
- **2 partners** — both must have Partner / Friends forever / Doctor's companion / "Partner with" each other

On selection, derive the **binding color constraint**: the union of commanders' `color_identity`. All non-land cards must have color identity within this set.

---

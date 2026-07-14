# /build-deck: revert building to the orchestrator; keep isolation via process + cold Challenger

Date: 2026-07-14 · Status: approved · Branch: `feat/revert-inline-builder-keep-guards`

## Problem

The pre-Jul-13 `/build-deck` built decks inline in the orchestrator: ~13 min/deck, quality the user
liked. Its one bug: in multi-deck sessions, card verdicts formed for one deck leaked into the next
(the Helm of Awakening incident — a card was never re-evaluated for a new deck because it had been
discarded for a previous one).

The Jul 13 "firewall" (c02d781) moved building to an independent cold Builder agent. It fixed the
leak but made decks worse and 5.1x slower (~70 min/deck). PR #28 (the Cube Dossier) restored cube
facts to the cold agents and improved things — but an independent judge comparing
`opus-ur-grapeshot-storm` (new architecture) vs `opus-old-ur-hard-storm` (old) found the old deck
still better, and latency was unchanged. Root cause: a cold agent re-derives for ~35 min what a warm
orchestrator already knows, and no frozen document fully replaces a warm reasoning context.

**The original bug was narrower than the fix.** The contaminant was skipped/leaked *evaluations*,
not warm building.

## Design

### Architecture

The orchestrator builds and repairs decks inline again (baseline: pre-firewall skill at git
`2b1221a`, Phases 0–11). Isolation relocates into three guards:

1. **Prevention — Fresh-Eyes Sweep** (new phase, before build): for every card in this deck's
   `legal_pool`, the orchestrator records a fresh one-line verdict scoped to *this* deck
   (INCLUDE-candidate / EXCLUDE + reason), saved as `sweep.json` in the deck folder. A card cannot
   be skipped because it was rejected for a previous deck — every card gets a recorded fresh look.
2. **Detection — the cold Challenger**, now the single grill agent:
   - absorbs the Proposer's exhaustive per-card oracle-grounded defense attempt (failures → an
     INDEFENSIBLE list);
   - keeps its quantitative recounts of `quantitative_verdicts`;
   - gains an **absence audit**: scan `legal_pool` + dossier and name the strongest cards/engines
     absent from the deck ("why isn't High Tide here?").
   - TEMPLATES A (Builder), B (Builder-Repair) and C (Proposer) are removed.
3. **Analysis firewall**: excluded-cards content in `## ANALYSIS` is *generated* from this deck's
   `sweep.json` EXCLUDE entries, never free-authored. The analysis body may not reference another
   deck or reasoning formed while building one. The per-run validator additionally fails on any card
   name that is in neither this deck nor its `legal_pool`.

### Adjudication

The warm orchestrator defends its own deck and adjudicates Challenger findings (the verbatim-copy
rule dissolves for same-deck findings — deck-scoped judgment about the deck being built is allowed;
that is what IRON RULE 2 permits). **Hard findings are non-negotiable**: legality violation,
mana-audit regression, a count that fails to reproduce, and the Re-evaluation Path trigger
("pipeline cannot achieve its stated win condition") always force action. Colour lock and
advisory-only colour observations are unchanged. The one-round grill cap stays (hard findings
excepted).

### Dossier

The dossier survives; its primary customer shifts from the cold Builder to the cold Challenger
(a cold auditor without cube knowledge cannot recount, defend, or notice absences), plus it
warm-starts sessions via cached verified facts and persistent `interaction_chains`.

**The census never asserts absence.** A regex census proves presence; it cannot prove absence — the
"0 rituals / storm cannot be accelerated" false constraint (missed High Tide, Frantic Search, Snap,
Turnabout) caused three near-identical storm decks in one session. Every `pool_limits` entry becomes
"probes [list] matched 0 cards" with oracle-quoted `evidence` for positive claims, plus a
`census_caveat` (no-match ≠ doesn't-exist). No archetype-specific regex chasing — engines are model
work, not regex work.

**Engine knowledge lives in the authored `interaction_chains` layer**, populated two ways:
- **Seed**: when a dossier is first built (or chains are unseeded), a dedicated authoring pass reads
  the cube's oracle text archetype-by-archetype and authors chains for every engine found. Recorded
  as `chains_seeded_at`.
- **Write-back**: engines the orchestrator discovers while building are appended **at session end
  only** — never mid-run, so the frozen-before-deck-1 guarantee holds within a session. Chains are
  cube facts (mechanisms + oracle quotes), never deck verdicts.

`dossier_version` is added to the cache validation fingerprint; bumping it invalidates the poisoned
cache.

### Kept from the firewall/dossier era

Bundle tiers (`legal_pool` / `cube_index` / `dossier`); per-run `_workspace/<run-token>/` isolation;
hash integrity gate + prompt-contamination tripwire for spawned agents; template-verbatim prompts
for cold agents; canonical analysis.md format; no-scryfall-links rule; IRON RULE 2 as rewritten
("deck-scoped verdicts never cross a deck boundary").

### Latency

Mostly dissolves with the revert (target: the old ~13–20 min/deck). The orchestrator runs the
Phase-5C legality checks + `deck_audit.mana_audit` on its own list before the grill (pre-flight).
`legal_pool` cards carry precomputed `pips`, `has_generic`, `subtypes` so the Challenger doesn't
script them.

## Out of scope / follow-up

- 4.4 shortlist check: after shipping, verify Phase 3's sub-archetype shortlist yields materially
  different decks now that the false constraint is gone (compare mainboard overlap).
- Rebuilding the three degraded UR storm decks from the poisoned-dossier session is at the user's
  discretion; not part of this change.

## Verification

1. `cuber dossier <id> --rebuild` on dominaria: no absence assertion phrased as impossibility;
   `census_caveat` present; version bump invalidates the old cache; authored chains preserved and
   seeded (High Tide engine present).
2. One UR storm deck built end-to-end: `sweep.json` covers the full `legal_pool`; High Tide gets a
   recorded verdict; pre-flight passes before grill; single Challenger returns per-card defense +
   recounts + absence audit; wall clock ~13–20 min, not ~70.
3. Judge re-comparison vs `opus-old-ur-hard-storm` by a fresh agent: parity or better.
4. Two decks back-to-back in one session: extended validator passes on both analysis.md files;
   deck 2's analysis contains no reference to deck 1's reasoning and no foreign card names.

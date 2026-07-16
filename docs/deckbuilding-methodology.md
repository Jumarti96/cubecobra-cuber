# A Deck-Builder's Pipeline: From Archetype Idea to Finished Deck

A structured, near-algorithmic thought process for building a Magic: the
Gathering deck from a pool of cards. Format-agnostic: every numeric heuristic
is stated as a **ratio of deck size**, with worked numbers for 40-card
(limited), 60-card (constructed), and 100-card (singleton) decks.

---

## How to use this document

The pipeline has ten phases, numbered 0–9. Run them **in order**. Each phase
ends in a **GATE** — an explicit exit criterion. If you cannot pass a gate,
the phase names where to loop back to; do not push forward with a failed gate
behind you, because every later phase silently assumes the earlier gates hold.

Three semantics to keep in mind:

1. **Heuristics are defaults, not laws.** Every number here is the
   percentage-play. Phase 9 defines the only legitimate procedure for
   overriding one.
2. **Gates are cheap; rebuilds are expensive.** The gates exist to catch a
   doomed deck at the one-sentence stage instead of the 40-card stage.
3. **The pipeline is a loop, not a line.** A finished deck that fails Phase 8
   testing re-enters at the phase its failure points to. Expect 2–4 passes
   before a list stabilizes.

---

## The question map

The ten seed questions this pipeline was built around, and where each lives:

| # | Question | Phase |
|---|----------|-------|
| 1 | How to identify the hidden synergies | 2 |
| 2 | How to select the cards that support that synergy | 3 |
| 3 | What to cut and when | 7 |
| 4 | What to look for in the environment or meta | 0, 5 |
| 5 | How to defend from it | 5 |
| 6 | How to balance maximizing your plan vs. protecting it | 6 |
| 7 | When and how to pivot between strategies | 8 |
| 8 | Proportions of each card type by structural function | 4 |
| 9 | How to be careful with the mana curve | 4 |
| 10 | When to ignore any of the questions | 9 |

### The questions you were missing

The seed list covers the *middle* of deck-building well. What it misses is the
beginning (a falsifiable plan), the plumbing (mana, refueling), and the end
(knowing when you're done). An expert also asks:

- **How does this deck actually win — concretely, and by what turn?** Not "it
  has good cards" but a named win condition with a turn range. This is the
  single most-skipped question, and skipping it produces piles, not decks.
  *(Phase 1)*
- **Who's the beatdown — what role does the deck default to?** Aggressor,
  controller, or combo. Most in-game losses trace to role misassignment, and
  role is decided at construction, not at the table. *(Phase 1)*
- **What does failure look like?** Every deck loses to itself sometimes —
  flood, screw, or a synergy package that never assembles. You must know which
  failure mode your deck is buying and at what frequency. *(Phase 6)*
- **How many *functional copies* of each critical effect do I need?**
  Consistency is arithmetic, not vibes. Redundancy math turns "I hope I draw
  it" into a percentage. *(Phase 2)*
- **What does each card do when the plan *doesn't* assemble?** Rate vs.
  synergy — a card's floor is what you're actually paying for its ceiling.
  *(Phase 3)*
- **How does the deck refuel?** Decks don't lose the turn they run out of
  cards; they lose three turns later. Name the card-advantage or velocity
  engine. *(Phase 4)*
- **What *must* my interaction answer — which threat classes, not just how
  many slots?** Eight removal spells that all say "destroy target creature"
  is zero answers to a combo deck. *(Phase 5)*
- **Does the mana base support the spells, pip by pip?** Land *count* is
  Phase 4's easy half; colored *sources per pip requirement* is the half that
  actually kills decks. *(Phase 4)*
- **When is the deck done?** Without an exit criterion, tuning never
  terminates and every loss triggers a rebuild. *(Phase 8)*

---

## Phase 0 — Read the environment

Before touching a single card of your own, characterize the world your deck
will live in. "The meta" is just three measurable things.

**Ask:**
- What is the **clock**? The turn by which the fastest common strategies win
  a goldfish (an undisrupted game).
- What are the **2–3 dominant strategies** — the decks you will face most,
  by frequency, not by fear?
- What **answer types are actually available and played**? (Cheap removal?
  Sweepers? Counterspells? Graveyard hate? Artifact hate?)

**Do:**
- Write one line per dominant strategy: *name — plan — kill turn — weakness*.
- Write the format clock as a single number: "an unanswered deck here wins
  around turn N."
- Note which threat classes go *unanswered* in this environment — that's
  where free wins live.

**Sidebar — why this works:** every later decision (curve height, interaction
count, how greedy your synergy can be) is a function of the clock. A turn-6
engine is a great deck in a turn-8 format and a losing deck in a turn-4
format. You cannot evaluate a card, let alone a deck, without this number.

**GATE:** you can state the clock and each dominant strategy in one line each.
**On failure:** you lack information, not skill — play or watch games in the
environment, or study the card pool itself, until you can.

---

## Phase 1 — State the thesis

**Ask:**
- How does this deck **win**? Name the actual final game state (reduce life
  via wide boards / via one large evasive threat / via combo loop / via
  attrition and inevitability).
- **By what turn**, against no resistance?
- **Who's the beatdown?** Is this deck the aggressor, the controller, or the
  combo player by default?

**Do:** write the thesis as one sentence with all three elements. Examples of
well-formed theses:

> "Sacrifice creatures for value, grind 2-for-1s until the opponent is out of
> resources, win by turn 10+ with recursive threats — controller in most
> matchups."

> "Curve out with cheap evasive creatures, finish with burn, win turn 5–6 —
> beatdown in every matchup."

A malformed thesis names cards instead of a plan ("it's the deck with X and
Y") or has no turn number ("it wins eventually").

**Sidebar — Who's the Beatdown (Flores):** in any matchup, one deck is the
aggressor and one is the defender, and the deck that misassigns its own role
loses. Role is relative — your midrange deck is the beatdown against control
and the defender against aggro — but it has a *default*, and that default is
set by construction. Knowing it now determines your curve, your interaction
shape, and your mulligan rules later.

**GATE:** the thesis names a win condition, a turn range, and a default role.
**On failure:** you don't have a deck idea yet, you have a card you like.
That's fine — go to Phase 2, find what that card's engine is, and come back.

---

## Phase 2 — Map the synergy engine

This is where hidden synergies are found — systematically, not by
inspiration.

**Ask:**
- What does each candidate card **produce** (tokens, treasures, counters,
  card types into the graveyard, triggers, mana, card draw)?
- What does each card **consume** (sacrifice fodder, cards to discard,
  counters to remove, spells cast, creatures that must attack)?
- Which cards **change categories** — type-changers, cost-reducers,
  zone-crossers, doublers, untappers?

**Do:**
1. **Index the pool by produces/consumes**, not by card name. A hidden
   synergy is a producer/consumer match that isn't printed on the same card
   and isn't advertised by a shared keyword. (The advertised synergies — same
   tribe, same mechanic — are the ones everyone sees. The hidden ones cross
   vocabulary: "makes tokens" feeding "needs sacrifice fodder," "cares about
   card types in graveyard" fed by "self-mill.")
2. Read **oracle text**, not card frames or your memory. Category-changing
   words ("is every creature type," "spells cost less," "as though it were in
   your hand") are the highest-yield lines in the pool — they multiply every
   other match.
3. Classify every engine piece into three roles:
   - **Payoffs** — convert the synergy into winning (the reason to do this).
   - **Enablers** — produce the resource the payoffs consume.
   - **Glue** — cards good in the deck that also happen to feed the engine.
4. **Compute critical mass** for each role: how many functional copies must
   the deck contain for the engine to be online when the thesis says so?

**Sidebar — redundancy math:** the chance of having drawn at least one copy
of an effect that makes up fraction *p* of your deck, after seeing *n* cards,
is roughly 1 − (1 − p)^n. Worked table (7 cards = opening hand; ~10 = turn 3;
~13 = turn 6):

| Share of deck | 40-card | 60-card | 100-card | in 7 | in 10 | in 13 |
|---|---|---|---|---|---|---|
| 5%  | 2  | 3  | 5  | ~30% | ~40% | ~49% |
| 10% | 4  | 6  | 10 | ~52% | ~65% | ~75% |
| 15% | 6  | 9  | 15 | ~68% | ~80% | ~88% |
| 20% | 8  | 12 | 20 | ~79% | ~89% | ~95% |

The classic "rule of 8" (8 copies in 60 ≈ 13%) is just this table: an effect
you need reliably by turn 2–3 wants ~13–15% of the deck in functional copies.
An effect you need in your opening hand wants ~20%. And assembly compounds:
two pieces at 10% each are only ~50% assembled even 12 cards deep — which is
why two-card engines need each half at 15%+ or ways to search.

**GATE:** the engine is written down as payoffs / enablers / glue with counts,
and each count meets the critical mass the thesis turn requires.
**On failure:** the pool can't support the engine at critical mass — either
downgrade the engine to a *side* synergy (glue only) and return to Phase 1
for a new thesis, or accept a slower thesis turn and re-check against
Phase 0's clock.

---

## Phase 3 — Select the cards

Fill the engine roles with actual cards, judged in context.

**Ask, for every candidate:**
- What is its **floor** — what does it do when the engine hasn't assembled,
  or was answered?
- What is its **ceiling** — what does it do when everything works?
- In which **quadrants** is it good?

**Do:**
1. Score each candidate twice: **rate** (its floor as a standalone card) and
   **synergy** (its ceiling inside this engine). Write both down; a one-line
   verdict per card is enough.
2. Apply the quadrant test — is the card acceptable when you are
   **opening** (developing, turns 1–3), at **parity** (topdeck war),
   **winning**, and **losing**?
3. Selection rules:
   - Prefer cards good in **3+ quadrants**.
   - A card good in fewer quadrants must be **plan-critical** (a payoff at
     critical-mass count) to earn a slot.
   - **Enablers must pass the floor test hardest** — you'll draw them in
     multiples, and an enabler with no payoff in sight is your worst draw.
   - Beware cards that are only good when you're already **winning**
     (win-more) — they occupy the exact slots resilience needs.

**Sidebar — rate vs. synergy is a portfolio decision:** every synergy card is
a leveraged asset — it returns more than its rate when the engine assembles
and less when it doesn't. Phase 2's math told you the assembly probability;
this phase decides how much of the deck to leverage. High floor + high
ceiling cards are rare and auto-include; the real skill is pricing the
low-floor, high-ceiling cards honestly using that probability instead of
imagining the ceiling every game.

**GATE:** every selected card has a written role (payoff / enabler / glue /
interaction / mana) and a floor you can state without wincing.
**On failure:** candidates keep failing the floor test → the engine demands
too many dead cards; return to Phase 2 and reduce the engine's footprint.

---

## Phase 4 — Build the skeleton

Structure precedes card quality. Fill quotas by **function**, then argue
about which card fills each slot — never the reverse.

**Structural quotas (share of the whole deck):**

| Function | Share | 40-card | 60-card | 100-card |
|---|---|---|---|---|
| Mana (lands + cheap ramp) | 40–45% | 17 lands | 22–26 | 36–38 + 8–12 ramp |
| Proactive plan (threats/engine) | 30–40% | 12–16 | 18–24 | 30–40 |
| Interaction | see below | 5–10 | 8–14 | 8–15 |
| Card flow (draw/velocity) | 8–15% | 3–6 | 5–9 | 8–15 |

Interaction scales with role (from Phase 1): **beatdown** decks run the low
end (interaction only to clear blockers or protect the win), **controller**
decks the high end plus sweepers, midrange in between.

**Curve — a distribution, not an average.** Shape the nonland curve to the
thesis turn. As a share of *nonland* cards:

- **Beatdown:** ~25% at 1 mana, ~35% at 2, ~25% at 3, ~15% at 4+, and
  almost nothing above 5. The deck must use all its mana turns 1–3.
- **Midrange:** peak at 2–3, meaningful 4s and 5s, top end ~2 cards per 40.
- **Controller:** cheap slots are *interaction*, not threats; the curve can
  top higher because the plan is to reach those turns.

Two curve rules that outrank everything: (1) the **2-drop slot** is the most
important in any proactive deck — shortage there loses unwinnable-feeling
games; (2) every card above the thesis turn's mana must win the game or come
close when cast.

**Mana base — count sources per pip, not lands.** For each spell you want on
curve, count deck-wide **sources of its colors**. Rules of thumb: a
single-pip splash card wants ~35% of your mana sources in that color; a
double-pip card cast on curve wants ~55%+ of sources; double-pip in two
different colors early is a mana base all by itself — respect it or cut it.

**Sidebar — card advantage vs. velocity:** card **advantage** is net extra
cards (draw two, 2-for-1 trades); **velocity** is seeing more cards per turn
without net gain (scry, loot, cantrip). Beatdown wants velocity — it converts
cards to damage fast and needs specific pieces, not more total cards.
Controllers want raw advantage — the plan is to trade 1-for-1 forever and win
with the surplus. Fill the card-flow quota with the *matching* kind.

**GATE:** all quotas filled; curve matches the declared role; every
double-pip-on-curve card has its source count. **On failure:** the pool
can't fill a quota (usually interaction or 2-drops) → the *color pair or
engine choice* is wrong for this pool; return to Phase 2 or 3.

---

## Phase 5 — Check the deck against the environment

Now hold the skeleton up against Phase 0's notes. Two tests.

**The speed test:** compare your thesis turn to the format clock.
- Thesis turn **≤ clock**: you may build greedy and lean on the low end of
  the interaction quota.
- Thesis turn **= clock + 1 or 2**: you must interact meaningfully on the way
  — every one of those interaction slots is now load-bearing.
- Thesis turn **> clock + 2**: you are the control deck whether you meant to
  be or not; either embrace it (re-run Phase 4 with controller quotas) or
  abandon the thesis.

**The answer-coverage test:** for each dominant strategy from Phase 0, name
the actual cards in your list that interact with it. Check coverage by
**threat class**, not by slot count:

1. Fast wide boards (needs cheap and/or one-to-many answers)
2. A single large or resilient threat (needs unconditional removal)
3. Noncreature permanents — artifacts, enchantments, planeswalkers
4. The stack — spell-based combo and rituals (needs counters or clock)
5. Graveyard recursion (needs exile effects or clock)

You are allowed to **concede a class** — but write it down as a known loss,
and it must not be a class a *dominant* strategy occupies. The cheapest
"answer" to any class is often speed: a fast enough clock answers everything.

**Sidebar — defense is asymmetric:** you don't need to answer what the
environment *can* do, only what it *does* do and what actually beats your
thesis. Interaction that overlaps classes (exile-based removal hits classes
2 and 5; a fast clock pressures 3 and 4) is worth more than its slot.

**GATE:** the speed test passes, and every dominant strategy has either named
answers in your list or a written, deliberate concession.
**On failure:** loop to Phase 4 (re-shape interaction) or, if the thesis turn
itself is the problem, to Phase 1.

---

## Phase 6 — Balance greed against resilience

The seed question — maximize the plan vs. protect it — is really a pricing
problem. This phase prices it.

**Ask:**
- What is the **synergy tax**? Count the cards that are below-rate when the
  engine hasn't assembled. Using Phase 2's math: (tax cards as share of
  deck) × (probability engine is NOT assembled by the thesis turn) = the
  expected dead weight per game. Keep it under roughly one card per game.
- Walk the three **failure modes** explicitly:
  - **Flood** — draw your 40%-mana deck's worst half: what do extra lands do?
    (Mitigations: land-count discipline, channel/cycling-style lands,
    mana sinks.)
  - **Screw** — miss land drop 3: which hands were keepable? (Mitigation:
    the curve rules from Phase 4, cheap card velocity.)
  - **Decapitation** — the opponent answers your key piece **on sight**:
    what is the line? A deck whose honest answer is "I lose" needs either
    **protection** (cheaper: 2–3 slots that shield the piece) or a **Plan B**
    (costlier: a second, independent win route at its own critical mass).
- Which is right, protection or Plan B? Protection when the engine is
  compact (1–2 key cards) and the format's answers are narrow. Plan B when
  the engine is wide (many replaceable pieces) or the format answers
  everything — half-protecting a piece in a removal-dense format is the
  worst of both.

**Sidebar — threat density vs. answer density:** answers trade at best
1-for-1 and are dead against the wrong threat; threats demand answers on the
*opponent's* side. This is why the resilient version of a synergy deck
usually adds **redundant threats**, not more protection: each extra credible
threat taxes their answers, while each protection spell is dead whenever they
don't interact.

**GATE:** the deck has a written line for each of the three failure modes,
and the synergy tax is priced and accepted.
**On failure:** tax too high or no decapitation line exists → return to
Phase 3 and swap the lowest-floor synergy cards for higher-floor glue.

---

## Phase 7 — The cut loop

You are at 45+ cards for a 40-card deck (or the equivalent). Cutting is an
algorithm, not a mood.

**In order:**
1. **Quotas are immune.** Never cut below a Phase 4 quota to keep a cool
   card. If a cut would break a quota, the cut must be *within* that
   function (a worse interaction spell for a better one), not across it.
2. **Cut packages, not singletons.** If a synergy package must shrink below
   its Phase 2 critical mass, cut the **entire package** — payoffs first,
   then its dedicated enablers. Three leftover engine cards below critical
   mass are three dead draws wearing a theme costume.
3. **Win-more goes first.** Cards good only in the winning quadrant
   (Phase 3 notes) are the first individual cuts.
4. **Then cut from the top of the curve.** Expensive cards need to justify
   themselves per Phase 4's rule; ties break toward the cheaper card.
5. **Lowest floor among duplicated effects.** Where two cards fill the same
   role, keep the higher floor unless the ceiling is plan-critical.
6. **Recount after every cut.** Any card whose value is a count of other
   cards (cost reducers, type-matters payoffs, threshold-style cards) must be
   re-verified against the *new* list — cuts silently turn countable payoffs
   into blanks.

**When to cut:** in one sitting, at the end, from a written over-list —
never during selection. Selection with the knife already out makes you
timid in Phase 3, and timid selection misses the hidden synergies this
pipeline exists to find.

**Sidebar — cut from strength:** the hardest and most correct cuts are the
good-rate cards that don't serve the thesis. A deck of 23 thesis cards beats
a deck of 23 individually stronger cards pulling in three directions. If a
cut feels easy, check you aren't just cutting the low-rate *engine* piece the
thesis needs (rule 2 protects you here).

**GATE:** exact deck size, all quotas intact, all counts recomputed.
**On failure:** can't reach size without breaking a quota → the deck is
trying to be two decks; return to Phase 1 and pick one thesis.

---

## Phase 8 — Stress-test and iterate

**The goldfish protocol** (no opponent, 10 hands):
- Play 10 solo games. Record for each: turn the thesis executed, cards that
  were dead in hand, mulligan decisions.
- **Mulligan test:** deal 20 opening hands; a keepable rate under ~80%
  (or any 6-card hand you couldn't keep) means the curve or mana fails
  Phase 4, whatever the quota table said.
- **Dead-card test:** any card dead in 3+ of 10 hands goes on the cut watch
  list — check whether its Phase 2 critical mass was optimistic.

**The revision rule:** change **at most 3 cards per iteration**, and write
down which question each change answers. Bulk changes destroy the
information your testing just bought.

**When to pivot (the seed question "when and how"):** pivot when the thesis
fails **structurally**, not statistically:
- The engine can't reach critical mass by the thesis turn even after tuning
  (Phase 2 math was wrong), or
- The thesis turn cannot beat or survive the clock (Phase 5 keeps failing),
  or
- The pool/format shifted and a dominant strategy now attacks your engine's
  exact axis.

Losses alone — even several — are *samples*, not signals; the sample sizes
available to a human are far too small to distinguish a 45% deck from a 55%
one. Pivot on structure, tune on results.

**How to pivot:** keep the **chassis** — the mana base and the
generically-good interaction, which are thesis-independent — and swap the
**engine** (payoffs + dedicated enablers). Then re-enter the pipeline at
Phase 1 with the new thesis; Phases 4–7 will mostly re-validate.

**GATE — the "done" criterion:** three consecutive goldfishes execute the
thesis within one turn of target, no card is dead in 3+ of 10 hands, and the
mulligan test passes. The deck is now *done* — further changes require a new
failure observation, not a new idea.
**On failure:** the recorded failures name their phase — dead cards → 2/3,
curve/mana stumbles → 4, losing to the environment → 5, structural thesis
failure → pivot via Phase 1.

---

## Phase 9 — When to break the rules

Every number in this document is a default. Experts break them constantly —
but by procedure, not by mood. The procedure:

1. **Name the rule and the reason.** A quota or heuristic may be broken only
   for a **named reason tied to the thesis**. "This deck runs 15 lands
   because 20% of its nonland cards make mana and the curve stops at 3" is a
   named reason. "It'll be fine" is not.
2. **Know which rules bind harder for you.** The more **linear** the deck
   (all-in on one engine), the more the curve and redundancy rules bind —
   linear decks die precisely by stumbling. The more **powerful** the
   format, the more rate beats synergy — in high-power pools the synergy tax
   compounds because opponents punish dead cards harder. The more
   **interactive** the format, the more the floor test (Phase 3) binds.
3. **Every broken rule is a written bet.** State what you expect to observe
   in Phase 8 because you broke it ("I cut to 4 interaction; I expect to
   race everything — if I lose to aggro twice in testing, the bet failed").
   A broken rule whose bet fails gets restored — no relitigating.
4. **Break rules one at a time.** Two simultaneous broken rules can't be
   attributed when the deck underperforms.

**Sidebar — why judgment comes last:** the questions in this pipeline aren't
scripture; they're the compressed experience of thousands of decks. You earn
the right to override them the same way that experience was earned — by
running the loop, writing down bets, and letting Phase 8 grade them. After
enough passes, the pipeline stops being a checklist and becomes the way you
see card pools. That is the actual goal of this document.

**GATE:** none. This phase is the judgment that supervises all the others —
and it closes the loop back to Phase 0, because the next deck starts with
reading the environment your last deck just changed.

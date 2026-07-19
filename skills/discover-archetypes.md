---
name: discover-archetypes
description: Discover every playable draft archetype in a locally cached cube — core strategies, thin support shells, and single-card build-arounds alike — with the exact cards that make each one work. Use this whenever the user asks what archetypes, strategies, game plans, decks, or synergies a cube supports, wants an archetype map, asks "what can I draft out of this cube", or wants build-arounds/niche archetypes surfaced — even if they don't say the word "archetype." Supports a default organic-discovery mode and a guided-coverage mode where the user specifies which cards must be classified (e.g. "classify all rares, mythics, and multicolor uncommons").
---
# /discover-archetypes — Archetype & Strategy Discovery

Discover every viable draft archetype in a locally cached cube — from deeply-supported core
strategies down to single-card build-arounds — and produce a ranked report naming the cards that
make each one work. Starts from the `taxonomic_profile` taxonomy in `enriched.json`, then reasons
past the tags using oracle text, colors, and card type to surface synergies the tagger couldn't
pre-label. No rarity is excluded — commons count as much as mythics.

---

## IRON RULE

**Never assume what a card does from prior knowledge.**
Every card placed in an archetype MUST be justified by its `oracle_text` as it appears in
`enriched.json` — whether or not the card carries a matching tag. If you can't point to oracle
text (or a color/type/CMC fact) that earns a card its spot, leave it out.

Tags are a **starting hypothesis, not a ceiling.** The four-pillar taxonomy
(`macro_archetypes`, `synergy_clusters`, `structural_roles`, `mechanical_functions`) is what the
tagger could label reliably in isolation, one card at a time — it cannot see the cross-card
combos that define real draft archetypes. A big graveyard-bound creature with no `Reanimator` tag
is still a reanimation target if the cube also contains a reanimation effect that can put it into
play from the graveyard; a cheap artifact with no `Sacrifice` tag is still fodder if a sac outlet
in the cube can eat it for value. Once a candidate archetype is hypothesized from a keystone card,
actively hunt for untagged support rather than stopping at the tag boundary — that hunt is the
core value of this skill over just reading `taxonomic_profile.synergy_clusters` off the shelf.

---

## Discovery Is Exhaustive and Non-Judgmental

A thin archetype is not a failed one — it's a `Build-Around`. Do not omit an archetype because it
only has three supporting cards; report it at the tier it earns. Never say an archetype is "too
weak to matter" or "not worth drafting" — the tier label carries that signal; let the user decide.

---

## Prerequisites

The cube must be fetched, enriched, and **tagged** — this skill starts from `taxonomic_profile`,
so tagging is not optional here the way it is for `/analyze-cube`'s basic stats:
```
cuber fetch <id>
cuber enrich <id>
cuber tag <id>
```

**Finding the cube folder:** Run `cuber list` to find `<slug>`. Use `cubes/<slug>/` for all file
path operations below.

**Check tag coverage before starting.** Read `cubes/<slug>/enriched.json` and check whether any
`board == "mainboard"` card has a non-null `taxonomic_profile`:
- If **none** do: stop and instruct the user — "No cards are tagged yet. Run `cuber tag <id>`
  first, then re-run this skill."
- If **some but not all** mainboard cards are tagged: proceed, and note in the final report how
  many mainboard cards were untagged going in (they can still be pulled into an archetype during
  the cross-tag enrichment step — being untagged just means they didn't count as a *seed*).

---

## Step 0 — Choose the Mode

Two modes. Default to **Organic Discovery** unless the user's request contains an explicit
coverage rule.

### Organic Discovery (default)
Let archetypes emerge from whatever synergy clusters and macro archetypes actually have support
in this cube. No card is required to land anywhere — some cards are just goodstuff and that's a
legitimate outcome.

### Guided Coverage
The user supplies a rule about what must be covered. Examples and how to handle them:

| User instruction | How it changes the run |
|---|---|
| "Classify all rares, mythics, and multicolor uncommons into at least one archetype if possible." | After normal discovery, take every card matching that filter that's still unplaced and run a dedicated cross-tag search (Step 3's technique, widened) to find it a home before finalizing. |
| "Make sure every Payload/Payoff card ends up somewhere." | Same idea, filtered on `structural_roles` containing `Payload/Payoff` instead of rarity/color. |
| "Only look at my UB and BR cards." | Narrow the entire seed pool (Step 1) to cards whose `color_identity` fits those pairs before hypothesizing anything. |

When running Guided Coverage:
1. Parse the instruction into a concrete filter over `rarity` / `colors` / `color_identity` /
   `taxonomic_profile` fields.
2. Run Steps 1–4 normally.
3. For any card matching the filter that's still unplaced after Step 3, widen the `--oracle`
   search and consider secondary/weaker archetype fits — don't stop at the first miss.
4. If a card genuinely cannot be justified in *any* archetype even after widening, say so plainly
   in the report ("could not be placed — no archetype in this cube uses its effect"). Never force
   a card into an archetype its oracle text doesn't support just to satisfy the coverage rule —
   an honest miss is more useful to the user than a fabricated fit.

State the active mode (and the parsed filter, if Guided) at the top of the final report.

---

## Step 1 — Aggregate Seeds

Generate a run token unique to this invocation AND atomically create its directory before writing anything. The token is a microsecond-precision UTC timestamp plus a full 32-char uuid4 hex — e.g. `run-20260709T041210123456-a3f9c1e2b4d64f7a8c9e0f1a2b3c4d5e`:
```
python -c "import datetime,uuid,os; t='run-'+datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')+'-'+uuid.uuid4().hex; os.makedirs(os.path.join('cubes','<slug>','_workspace',t)); print(t)"
```
This prints the token AND creates `cubes/<slug>/_workspace/<run-token>/`. `os.makedirs` runs with the default `exist_ok=False`, so it fails with `FileExistsError` if that directory already exists — a collision signal that another concurrent run grabbed the same token. If the command errors, run it again (it mints a fresh token every invocation); retry up to 3 times, then stop and report rather than reusing the directory. Never create the directory by hand or with `exist_ok=True`. The high-entropy token keeps concurrent runs on the same cube from colliding on the same filename or overwriting each other's files.

Write a small script to `cubes/<slug>/_workspace/<run-token>/aggregate_seeds.py` that reads
`cubes/<slug>/enriched.json` and buckets mainboard cards by taxonomy, so you're reasoning over
counts instead of scrolling raw JSON. Roughly:

```python
import json, collections
data = json.load(open("cubes/<slug>/enriched.json", encoding="utf-8"))
cards = [c for c in data["cards"] if c.get("board", "mainboard") == "mainboard"]

by_cluster = collections.defaultdict(list)
by_macro = collections.defaultdict(list)
niche_keystones = []  # any-rarity cards with a Payload/Payoff role and a thin cluster

for c in cards:
    tp = c.get("taxonomic_profile")
    if not tp:
        continue
    for cluster in tp.get("synergy_clusters", []):
        by_cluster[cluster].append(c["name"])
    for macro in tp.get("macro_archetypes", []):
        by_macro[macro].append(c["name"])
    if "Payload/Payoff" in tp.get("structural_roles", []):
        niche_keystones.append(c["name"])

print(json.dumps({
    "cluster_counts": {k: len(v) for k, v in sorted(by_cluster.items(), key=lambda x: -len(x[1]))},
    "macro_counts": {k: len(v) for k, v in by_macro.items()},
    "clusters": by_cluster,
    "niche_keystones": niche_keystones,
    "total_mainboard": len(cards),
    "untagged_mainboard": sum(1 for c in cards if not c.get("taxonomic_profile")),
}, indent=2))
```

Run it and read the output. This tells you, per synergy cluster, how many cards already carry
that tag — the raw material for hypotheses in Step 2. (If a coverage filter is active, restrict
`cards` to the matching subset first.)

### Keyword-ability scan (safety net for untagged shared keywords)

Tags can miss a real archetype built around a shared keyword ABILITY (Defender, Menace, Flying,
etc.) rather than a creature type or a listed synergy cluster — e.g. a payoff that reads "for each
creature with defender you control" next to several plain Walls with no shared tag between them.
`cuber tag`'s prompt now proactively tags this pattern as a free-form `"<Keyword> Matters"`
synergy_cluster (so it should already surface as a normal Step 1 bucket on newly-tagged cubes), but
treat this scan as a safety net regardless — it also catches cubes tagged before that fix shipped
and any keyword the tagger still misses:
1. Scan payoff-shaped cards (`structural_roles` containing `Payload/Payoff`, or any card that reads
   oddly generic for its cluster) for oracle text that explicitly counts a keyword ability — phrases
   like "with <keyword>" or "creatures with <keyword>".
2. For each one found, search for bearer cards sharing that keyword, independent of tags:
   `cuber search <id> --oracle "<keyword>"` (e.g. `--oracle "defender"`).
3. If 3+ cards share the keyword (a payoff plus bearers), treat it as its own hypothesis in Step 2,
   named after the keyword (e.g. `Defenders`), exactly like any other candidate.

You may optionally also read `cubes/<slug>/exports/analysis.json` → `archetype_clusters` for a
precomputed distribution, but it's a convenience cross-check, not a replacement for the script
above (it may be stale if generated before the most recent tagging pass).

---

## Step 2 — Hypothesize Archetypes

From the Step 1 output:
- Every `synergy_cluster` with 1+ cards is a candidate archetype (name it after the cluster, e.g.
  `Reanimator`, `Aristocrats/Sacrifice`, `Tokens`).
- Every entry in `niche_keystones` is a candidate **Build-Around**, even if its cluster has no
  other seeds yet, and regardless of rarity — limited environments are frequently anchored by
  uncommon payoffs, not just rares/mythics, so don't let rarity gate whether a payoff gets a look.
- Two clusters that share most of their card pool (e.g. `Aristocrats/Sacrifice` and `Tokens`
  heavily overlapping) may be worth merging into one archetype rather than reported twice — use
  judgment; don't force a split the cube doesn't support.

At this point you have a working list of archetype names and their seed cards. Nothing is final —
Step 3 is where the untagged support gets found and Step 5 is where weak hypotheses get cut.

---

## Step 3 — Cross-Tag Enrichment (the important step)

For each candidate archetype, actively search for supporting cards whose `oracle_text` fits even
though they lack the matching tag. Prefer `cuber search` over hand-scanning JSON:

```
cuber search <id> --oracle "<regex for the effect>" --color <relevant colors> --rarity <r>
cuber search <id> --tag "<Synergy Cluster>" --color <relevant colors>
cuber search <id> --cmc-min 5 --type Creature --color <relevant colors>
```

Work the archetype from both ends:
- **From the payoff outward**: what does the engine/payoff card actually need? (e.g. a
  reanimation spell's oracle text says "creature card from your graveyard" — so any creature with
  a graveyard-friendly effect, or simply a big body worth cheating in, is a candidate target,
  tagged or not.)
- **From a strong but untagged card inward**: does this card's oracle text quietly support an
  archetype you've already hypothesized? (e.g. a card with "sacrifice a creature: draw a card" has
  no `Aristocrats/Sacrifice` tag but is obviously an outlet.)

Every card you add this way needs a one-line justification quoting the oracle text (or naming the
color/type/CMC fact) that earns it the slot. This is what separates "cross-tag inference" from
"guessing" — see the worked examples below.

---

## Step 4 — Assign Tiers

Tiers are a judgment call grounded in what you found, not a rigid card-count formula — treat these
as reasoning guidelines:

| Tier | What it looks like |
|---|---|
| **Core** | Multiple payoff/payload cards plus real enabler and engine depth across the curve and, usually, more than one color. A drafter could build a full, functional deck around this with room to cut. |
| **Supported** | A genuine payoff exists and it has some enablers, but the shell is thin — playable, not deep. A drafter would need to stay open to goodstuff to fill out the deck. |
| **Build-Around** | Anchored by one (occasionally two) distinctive keystone with light or incidental support. Still worth drafting around if you open the keystone, but you're building the archetype, not finding it. |

Report every archetype you found at whatever tier it earns — do not drop `Build-Around` entries.

---

## Step 5 — Self-Grill Gate (Hard Gate)

Run this before presenting anything to the user. Do not skip it.

1. **Membership audit** — every named card must exist in `enriched.json` by exact name. Extract
   the full name list once and check every card mentioned in the draft report against it:
   ```powershell
   $json = Get-Content "cubes/<slug>/enriched.json" -Raw | ConvertFrom-Json
   $all_names = $json.cards | ForEach-Object { $_.name }
   @("Card A", "Card B") | ForEach-Object { if ($all_names -contains $_) { Write-Host "OK: $_" } else { Write-Host "MISSING: $_" } }
   ```
   Replace or drop any card that fails.
2. **Oracle text audit** — re-read the oracle text for every cross-tag inclusion (any card placed
   in an archetype it wasn't tagged for) and confirm the quoted justification actually matches
   `enriched.json`. If it doesn't hold up, drop the card or the archetype.
3. **Payoff-plus-enabler check** — for every archetype tiered `Core` or `Supported`, confirm it
   has at least one payoff/payload card AND at least one enabler or engine card. An archetype with
   only enablers and no payoff (or vice versa) isn't real yet — demote it to `Build-Around` or cut
   it.
4. **Coverage check** (Guided mode only) — confirm every card the user's rule required has either
   been placed or explicitly reported as unplaceable with a reason.

Report the result plainly, e.g. `Self-grill: ✅ all cards verified, 2 archetypes merged, 1 dropped
for lacking a payoff` — or the equivalent if something failed and was fixed.

---

## Worked Examples

These illustrate the *reasoning pattern* — in a real run, only cards confirmed present in that
cube's `enriched.json` may be named.

### Example 1 — Cross-tag inference (Build-Around → Core)

Seed: `Xu-Ifit, Osteoharmonist` carries a `Reanimator` synergy-cluster tag and its oracle text
reads (illustrative) "you may cast target creature card from a graveyard without paying its mana
cost." That alone is a `Build-Around` — one keystone, no visible support yet.

Cross-tag search: `cuber search <id> --cmc-min 5 --type Creature --color B,G` turns up
`Bygone Colossus` — no `Reanimator` tag, but its oracle text describes a large body with an ETB
value effect and no evasion, making it a textbook reanimation target: cheap to discard or mill,
expensive to hard-cast, high impact when cheated in. A search for discard/mill outlets
(`--oracle "discard"` or `--oracle "mill"`) finds the enablers that get it into the graveyard.

Result: what looked like a single-card Build-Around becomes a `Supported` or `Core` **Reanimator**
archetype — engine (Xu-Ifit), payload (Bygone Colossus), enablers (discard/mill) — with the
target's inclusion justified entirely by its oracle text, not its tags.

### Example 2 — Core archetype from a well-tagged cluster

`Aristocrats/Sacrifice` shows 9 cards in the Step 1 aggregation, spanning `Enabler/Fodder` (token
generators), `Engine/Outlet` (sacrifice outlets that drain or draw), and `Payload/Payoff` (a
finisher that scales with creatures dying). Multiple payoffs, real enabler depth across two
colors → tier as `Core`. Report the 5-6 most load-bearing cards (one clear payoff, the best
outlet, 2-3 of the deepest enablers) and note the total support count for the rest.

### Example 3 — Niche Build-Around from a single rare

A single mythic has no synergy-cluster peers at all but its `structural_roles` includes
`Payload/Payoff` and its oracle text describes a unique, powerful effect (e.g., doubling counters
or triggering off a rare card type). No other card in the cube shares its tag. Tier it
`Build-Around`, name it after its effect (not the card), and note explicitly that it's a
single-card anchor — that's useful signal for a drafter deciding whether to speculate on it.

---

## Step 6 — Output

Produce both a report and a data file. Verify non-basic card names before writing (Step 5 should
already have caught this).

### `cubes/<slug>/archetypes.md`

State the active mode at the top, then group by tier (`Core` → `Supported` → `Build-Around`).
Per archetype:

```
### <Archetype Name> — <Tier>
**Colors:** <color identity lean, e.g. BG>  **Macro lean:** <Aggro/Midrange/Control/etc.>
**Keystones:** [Card](scryfall url), [Card](scryfall url)
**Core cards:** [Card], [Card], [Card], [Card], [Card] (+N more supporting this archetype)
**Key themes:** <synergy clusters / mechanical functions involved>
**Why it works:** one or two sentences, citing oracle text for any cross-tag inclusion.
```

Hyperlink non-basic card names to Scryfall: `[Card Name](https://scryfall.com/search?q=!"Card+Name")`.

### `cubes/<slug>/archetypes.csv`

Columns: `archetype, tier, colors, macro_archetype, keystones, core_cards, support_count, key_themes, rationale`.
`keystones` and `core_cards` are semicolon-separated card names; `rationale` is the one-line "why
it works" from the report.

**Quote any field containing a comma.** This is standard CSV escaping, but it's easy to forget on
free-text descriptive fields — `colors` is the usual trap (e.g. `W (R/G, B/W secondary)` has a
literal comma). An unquoted comma silently shifts every column after it for that row, corrupting
the archetype without any visible error — this exact bug has happened before. After writing the
file, re-read it with a CSV parser (not just by eye) and confirm every row's `tier` value is still
one of `Core`/`Supported`/`Build-Around` as a cheap corruption check.

**Name each card with its single, exact `enriched.json` name — never join two names together.**
Some cubes contain both a paper card and its Alchemy (`A-`-prefixed) rebalance as two distinct cube
entries. Reference each by its own exact name; if both qualify for the same archetype, list them as
two separate semicolon-separated entries. Never write a joined form like `"A-Card Name / Card
Name"` — that string matches neither real card and will fail membership verification.

Confirm both paths after writing:
```
Report written to: cubes/<slug>/archetypes.md
Data written to: cubes/<slug>/archetypes.csv
```

---

## Tool Selection Table

| Task | How |
|------|-----|
| Resolve cube slug | `cuber list` |
| Check tag coverage | `enriched.json` → any mainboard card with non-null `taxonomic_profile` |
| Aggregate seeds by cluster/macro archetype | Write + run `cubes/<slug>/_workspace/<run-token>/aggregate_seeds.py` (Step 1) |
| Optional precomputed cross-check | `cubes/<slug>/exports/analysis.json` → `archetype_clusters` |
| Find untagged support by effect | `cuber search <id> --oracle "<regex>" --color <c> --rarity <r> --cmc-min/--cmc-max --type <t>` |
| Find support by existing tag | `cuber search <id> --tag "<Synergy Cluster>"` |
| Read oracle text | Read `cubes/<slug>/enriched.json` — never training data |
| Verify card membership | PowerShell check against extracted `$all_names` list before naming any card |
| Write the report | Write tool → `cubes/<slug>/archetypes.md` |
| Write the data file | Write tool → `cubes/<slug>/archetypes.csv` |

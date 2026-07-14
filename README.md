# Cubecobra Cuber

A local Python toolkit for managing your Magic: The Gathering cubes on [CubeCobra](https://cubecobra.com). Fetch your cube as a structured project, edit it locally, enrich with Scryfall metadata, tag cards by function using AI, analyze statistics, build decks with an AI that debates itself, and export a file ready to import back into CubeCobra.

## What It Does

- **Set a current cube** with `cuber use <id>` — all commands then work without typing the cube ID every time; `.cuber-config.json` stores it locally (gitignored)
- **Fetch** any public CubeCobra cube into a local project folder — full JSON snapshot, primer, card list, and metadata all separated into editable files
- **Add cards** quickly with `cuber + "Card Name"` (shorthand for `add-card`); `x N` / `*N` inline count modifier adds multiple copies in one shot
- **Remove cards** quickly with `cuber rm "Card Name"` (shorthand for `remove-card`); removes 1 copy by default, `--all` for all copies; same inline count modifier support
- **Scale copy counts** with `cuber x N [cards...]` (multiply) and `cuber div N [cards...]` (floor-divide) — useful for constructed cubes with intentional multiples
- **Search by name** with `cuber search-card "Serra"` — fuzzy substring match within the cube; falls back to Scryfall with `--scryfall` or on no results; standard filter flags apply
- **Batch edit interactively** with `cuber ops` — a REPL where `+`, `-`, `=`, `*`, `/` stage operations that you review and confirm before applying; `undo`, `reset`, `list`, and `done` control the session
- **Add cards** to your cube (single card, batch list, or from a file) with automatic Scryfall enrichment on the next `enrich` run; supports multiple copies
- **Remove cards** from your cube by name — removes 1 copy by default, or all copies with `--all`
- **Clean up duplicates** with `dedup` — collapses repeated rows in one command
- **Track changes** locally: see what you've added, removed, or retagged since the last CubeCobra fetch
- **Enrich** cards with Scryfall metadata: oracle text, color identity, CMC, power/toughness, rarity
- **Tag** cards by functional role (removal, ramp, card draw, etc.) using AI that reads oracle text — not assumptions
- **Analyze** your cube's color distribution, CMC curve, rarity breakdown, and archetype coverage
- **Export** an `import-ready.csv` you can upload directly to CubeCobra's "Replace with CSV" importer — tags are optional
- **Build decks** in any format (40-card draft, 60-card constructed, Commander) with an AI that identifies deck identity, validates the mana base, respects restrictions, and debates itself before showing you the list
- **Suggest improvements** with reasoned cut/add proposals and an AI challenger verifying each one
- **Create set cubes** from any retail MTG set (e.g., every card in Edge of Eternities)

---

## Prerequisites

- Python 3.9 or newer
- An LLM provider with an OpenAI-compatible endpoint (Claude, OpenAI, Groq, Ollama, etc.) — only needed for AI features (`tag`, `build-deck`, `suggest-cube`, `/tag-cube`, `/build-deck`, `/suggest-cube`, `/set-cube`)
- `curl` on your PATH (used as a fallback if CubeCobra blocks Python requests)

---

## Setup

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd cubecobra-cuber

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your LLM provider (only needed for AI features)
cp .env.example .env
# Edit .env and fill in LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# 5. Install Claude Code skills
python scripts/install_skills.py
# Copies skills/*.md into .claude/skills/ where Claude Code reads them.
# Re-run this any time you edit a skill or pull updates.
```

**Optional: install as a command**

```bash
pip install -e .
# Now `cuber fetch obc` works in addition to `python -m cuber fetch obc`
```

The examples below use the short `cuber` form. If you haven't run `pip install -e .`, prefix each command with `python -m` instead.

---

## Quick Start

```bash
# Fetch your cube (replace 'obc' with your cube's short ID)
cuber fetch obc

# Enrich with Scryfall metadata (oracle text, color identity, etc.)
cuber enrich obc

# See statistics
cuber stats obc

# Tag cards by function using AI (requires .env with LLM config)
cuber tag obc

# Export a file ready to upload to CubeCobra
cuber export obc
```

Then in CubeCobra: **your cube → List tab → Export → Replace with CSV Import** — upload `cubes/<slug>/exports/import-ready.csv`.

---

## How Enrich Works

`cuber enrich` reads `mainboard.csv` and fetches Scryfall data for each card using a three-tier identifier strategy:

1. **Set + Collector Number** (`Set=MH3`, `Collector Number=42`) → fetched as `{set: "mh3", collector_number: "42"}`. Locks in the exact printing.
2. **Set only** (`Set=M11`, no Collector Number) → fetched as `{name: "Lightning Bolt", set: "m11"}`. Constrains to the correct set.
3. **Name only** → fetched as `{name: "Counterspell"}`. Scryfall's canonical printing is used.

**Skip-if-enriched:** Cards already in `enriched.json` with a matching `scryfall_id` (and matching set/CN if specified) are skipped — no Scryfall call is made for them. This makes re-enriching after a card swap fast. The output reports how many were skipped vs. fetched: `Skipped 500 (already enriched). Fetched 40 new/changed cards.`

**`--refresh`** bypasses all skip logic and re-fetches every card from Scryfall.

**Set column preservation:** `_backfill_mainboard_csv` never overwrites a non-empty `Set` column in `mainboard.csv`. Your intended set codes survive every enrich run.

---

## Cube Project Structure

After fetching, each cube lives under `cubes/` in a folder named after the cube's title (the slug). Commands accept either the **short ID** (e.g. `obc`) or the **title slug** (e.g. `my-vintage-cube`) — short ID is tried as a folder name first, then looked up in `meta.json`.

```
cubes/
  my-vintage-cube/
    remote/                ← pristine CubeCobra snapshot (never edit these)
      cube.json            ← full cubeJSON at last fetch
      mainboard.csv        ← CubeCobra's card list at last fetch
    meta.json              ← title, short-id, slug, format, owner, fetched date
    primer.md              ← cube description / primer (editable)
    mainboard.csv          ← your working card list (edit via CLI or directly)
    maybeboard.csv         ← your working maybeboard
    enriched.json          ← Scryfall-enriched card data (auto-generated)
    tagged.csv             ← cards with AI functional tags (auto-generated)
    dossier.json           ← deck-independent cube facts (written by `cuber dossier`)
    decks/
      aggro-rg/            ← deck built by /build-deck (one folder per deck)
        deck.json          ← full deck data (cards, mana audit, restrictions)
        deck.csv           ← same deck as a human-readable CSV
        deck.mwDeck        ← Magic Workstation format for MTGO import
        analysis.md        ← deck analysis with YAML frontmatter (dashboard-ready)
    exports/
      import-ready.csv     ← assembled by `cuber export`, upload this to CubeCobra
      analysis.json        ← stats snapshot (written by `cuber stats --json`)
      analysis.md          ← stats as Markdown tables (written by `cuber stats --md`)
```

**`remote/` is the last known CubeCobra state — never edit it.** Your edits go into the working files. `cuber status` shows the diff between remote and working. `cuber export` assembles the upload file when you're done.

---

## CLI Command Reference

All commands follow `python -m cuber <command> [options]` or `cuber <command>` after `pip install -e .`.

The `<id>` argument accepts either the CubeCobra short ID (e.g. `obc`) or the local title slug (e.g. `my-vintage-cube`). The slug — the folder name under `cubes/` — takes priority; the short ID is used as a fallback.

### Current Cube

| Command | Description | Example |
|---------|-------------|---------|
| `use <id>` | Set the current working cube. Writes `.cuber-config.json` (local, gitignored). All other commands use it when no `<id>` is passed. | `cuber use obc` |
| `use --clear` | Remove the current cube config. | `cuber use --clear` |

### Cube Lifecycle

| Command | Description | Example |
|---------|-------------|---------|
| `fetch <id>` | Download a public cube from CubeCobra. Creates the full project folder. | `cuber fetch obc` |
| `fetch <id> --dry-run` | Print the CubeCobra URL without downloading. | `cuber fetch obc --dry-run` |
| `add-card [id] <names...>` | Add one or more cards to the mainboard. Names are verified against Scryfall by default — typos are corrected to the canonical name; unknown names are rejected. Stubs are hydrated on the next `enrich`. `id` is optional when `cuber use` is set. | `cuber add-card obc "Lightning Bolt" "Brainstorm"` |
| `add-card <id> <names...> --no-verify` | Add cards without Scryfall verification (bulk imports with known-good names). | `cuber add-card obc --from-file known-cards.txt --no-verify` |
| `add-card <id> <names...> --count N` | Add N copies of each named card. | `cuber add-card obc "Lightning Bolt" --count 4` |
| `add-card <id> --from-file <path>` | Add cards from a text file (one name per line). | `cuber add-card obc --from-file new-cards.txt` |
| `add-card <id> --stdin` | Add cards from stdin (newline-separated). | `echo "Lightning Bolt" \| cuber add-card obc --stdin` |
| `add-card <id> <names...> --maybeboard` | Send added cards to the maybeboard instead. | `cuber add-card obc "Teferi" --maybeboard` |
| `swap <id> <old> <new>` | Atomically replace one card with another. Verifies the new card on Scryfall before removing the old one — aborts without changes if the new card is not found or the old card isn't in the cube. | `cuber swap obc "Dark Ritual" "Cabal Ritual"` |
| `swap <id> <old> <new> --maybeboard` | Operate on the maybeboard instead. | `cuber swap obc "Card A" "Card B" --maybeboard` |
| `remove-card <id> <names...>` | Remove cards from the mainboard. Removes **1 copy** of each named card by default. | `cuber remove-card obc "Lightning Bolt"` |
| `remove-card <id> <names...> --count N` | Remove exactly N copies. | `cuber remove-card obc "Lightning Bolt" --count 2` |
| `remove-card <id> <names...> --all` | Remove **all copies** of each named card. | `cuber remove-card obc "Lightning Bolt" --all` |
| `remove-card <id> --from-file <path>` | Remove cards listed in a file (one name per line). | `cuber remove-card obc --from-file cuts.txt` |
| `remove-card <id> <names...> --maybeboard` | Remove from maybeboard instead. | `cuber remove-card obc "Teferi" --maybeboard` |
| `+ <names...>` | Shorthand for `add-card` using the current cube. Supports inline count modifier: `cuber + "Serra Angel" x 3` adds 3 copies. | `cuber + "Lightning Bolt"` |
| `+ <names...> --count N` | Add N copies of each named card. | `cuber + "Serra Angel" --count 2` |
| `rm <names...>` | Shorthand for `remove-card` using the current cube. Removes 1 copy by default. Inline `x N` / `*N` modifier for count. `rm "Card" --all` removes all copies. | `cuber rm "Dark Ritual"` |
| `x <N> [cards...]` | Multiply existing copy counts by N. Reports before/after for each card. | `cuber x 2 "Lightning Bolt"` |
| `div <N> [cards...]` | Floor-divide existing copy counts by N. Prompts before removing the last copy of any card. | `cuber div 2 "Serra Angel"` |
| `search-card <query>` | Fuzzy name search within the cube (case-insensitive substring). Shows Name, CMC, CI, Type, Rarity, Scryfall URL. Falls back to Scryfall when not found. | `cuber search-card "Serra"` |
| `search-card <query> --scryfall` | Bypass cube and search Scryfall directly. | `cuber search-card "Lightning" --scryfall` |
| `search-card <query> --color W,U` | Filter results by color identity (subset match). | `cuber search-card "Angel" --color W` |
| `search-card <query> --type <str>` | Filter by type line substring. | `cuber search-card "Serra" --type creature` |
| `search-card <query> --rarity <r>` | Filter by exact rarity: common/uncommon/rare/mythic. | `cuber search-card "Serra" --rarity rare` |
| `search-card <query> --cmc-min N --cmc-max N` | Filter by CMC range. | `cuber search-card "Angel" --cmc-max 4` |
| `ops` | Interactive batch editing REPL. Position-free grammar: `+ "Bolt" * 3 "Serra Angel" * 2`, `- "Bolt"`, `= "Bolt" 4`. Stage operations with `+`, `-`, `=`, `* N`, `/ N`; review with `list`; undo with `undo [N]`; apply with `done`; exit without applying with `quit`. | `cuber ops` |
| `dedup [id]` | Remove duplicate rows, keeping one copy of each card name. | `cuber dedup obc` |
| `status [id]` | Show cards added, removed, or retagged since last fetch. | `cuber status obc` |
| `export [id]` | Assemble `exports/import-ready.csv` from `mainboard.csv`. Validates all card names against Scryfall (using `enriched.json` as a cache for already-verified cards). Blocks export if any card names are not found. | `cuber export obc` |
| `export [id] --skip-scryfall` | Skip Scryfall validation entirely (offline use). | `cuber export obc --skip-scryfall` |

### Enrichment & Tagging

| Command | Description | Example |
|---------|-------------|---------|
| `enrich <id>` | Look up each card on Scryfall; hydrate stubs from `add-card`. Auto-fetches if needed. Respects `Set` and `Collector Number` columns to lock in the intended printing. Skips cards that are already correctly enriched. | `cuber enrich obc` |
| `enrich <id> --refresh` | Re-fetch Scryfall data for all cards, ignoring existing enriched state (bypass 7-day cache). | `cuber enrich obc --refresh` |
| `stats <id>` | Print color, CMC, rarity, and type distributions (5 Unicode bar charts by default). No file written unless `--json` or `--md` is specified. | `cuber stats obc` |
| `stats <id> --color` | Show only the color identity chart. Multiple flags can be combined. | `cuber stats obc --color --rarity` |
| `stats <id> --cmc` | Show only the CMC distribution chart (includes mean/median/stdev if enriched). | `cuber stats obc --cmc` |
| `stats <id> --rarity` | Show only the rarity breakdown chart. | `cuber stats obc --rarity` |
| `stats <id> --types` | Show only the card type chart. | `cuber stats obc --types` |
| `stats <id> --guild` | Show multicolor guild breakdown (all 10 2-color pairs + 3+ color). | `cuber stats obc --guild` |
| `stats <id> --all` | Show all charts: 5 defaults + guild breakdown. | `cuber stats obc --all` |
| `stats <id> --by <dim> --metric <m>` | Cross-breakdown table: group by dimension, show mean/median/stdev/count/sum of metric. Requires `enriched.json`. Dimensions: `color`, `color-category`, `rarity`, `type`, `creature`, `guild`. Metrics: `cmc`, `power`, `toughness`. | `cuber stats obc --by color --metric cmc` |
| `stats <id> --json` | Write `exports/analysis.json` (also prints charts to terminal). | `cuber stats obc --json` |
| `stats <id> --md` | Write `exports/analysis.md` with YAML frontmatter and Markdown tables (also prints charts). | `cuber stats obc --md` |
| `tag <id>` | AI-tag all cards using oracle text. Writes `tagged.csv`. Requires LLM config. | `cuber tag obc` |
| `tag <id> --overwrite` | Replace existing tags instead of merging. | `cuber tag obc --overwrite` |
| `dossier <id>` | Build the **cube dossier** — deck-independent cube facts, cached at `cubes/<id>/dossier.json`. Mana infrastructure (with tapped/self-bounce land flags), structural censuses (rituals, sweepers, sacrifice outlets, cost reducers), tribal rosters, threat profile, and pool limits. Used by `/build-deck`. | `cuber dossier obc` |
| `dossier <id> --rebuild` | Recompute even if a fresh dossier is cached. Authored `interaction_chains` are preserved. | `cuber dossier obc --rebuild` |
| `dossier <id> --json` | Print the full dossier as JSON instead of a summary. | `cuber dossier obc --json` |
| `search <id>` | Search the local enriched card pool by any combination of criteria. | `cuber search obc --color B --type creature` |
| `search <id> --color W,U` | Filter by color identity (subset match). | `cuber search obc --color W,U` |
| `search <id> --type <str>` | Substring match on type line. | `cuber search obc --type instant` |
| `search <id> --cmc-min N --cmc-max N` | CMC range filter (inclusive). | `cuber search obc --cmc-min 1 --cmc-max 2` |
| `search <id> --oracle <pattern>` | Regex search on oracle text (case-insensitive). | `cuber search obc --oracle "draw a card"` |
| `search <id> --tag <tag>` | Filter by functional tag; comma-separate to require multiple. | `cuber search obc --tag removal` |
| `search <id> --rarity <r>` | Exact rarity match: common/uncommon/rare/mythic. | `cuber search obc --rarity rare` |
| `search <id> --limit N` | Cap results at N (default 25). | `cuber search obc --type creature --limit 50` |

### Packages

| Command | Description | Example |
|---------|-------------|---------|
| `packages search` | List popular CubeCobra packages (most votes first). | `cuber packages search` |
| `packages search <keywords>` | Search packages by keyword. Shows ID (truncated), title, card count, vote count. | `cuber packages search "removal"` |
| `packages search <keywords> --show-cards` | Also print card names under each package. | `cuber packages search "shocklands" --show-cards` |
| `add-package <id> <package-id>` | Fetch a CubeCobra package by ID and add all its cards to the cube's mainboard. Cards arrive pre-enriched — no separate `enrich` run needed. Skips cards already in the cube by default. | `cuber add-package obc e3fd8469-e67a-4844-92c5-933bb3dd54fc` |
| `add-package <id> <package-id> --allow-duplicates` | Add all package cards even if already in the cube. | `cuber add-package obc <id> --allow-duplicates` |

### Utilities

| Command | Description | Example |
|---------|-------------|---------|
| `list` | List all locally cached cubes with title, slug, card count, and fetch date. | `cuber list` |
| `diff <id1> <id2>` | Compare two cubes — shared cards, unique cards, and stat deltas. | `cuber diff obc vintage` |
| `fetch-set <code>` | Fetch every card from a retail set and create a full cube project. | `cuber fetch-set eoe` |
| `fetch-set <code> --include-basics` | Include basic lands. | `cuber fetch-set dmu --include-basics` |

---

## How Export Works

CubeCobra does not have a public write API. All changes are applied through the CubeCobra UI via CSV import.

When you're done editing locally:

```bash
cuber export obc
```

This assembles `cubes/<slug>/exports/import-ready.csv` from your current `mainboard.csv`. If `tagged.csv` exists (written by `cuber tag` or `/tag-cube`), those tags are merged in automatically. If it doesn't exist, the export proceeds without tags — **no LLM key is required to export**.

Then in CubeCobra:

1. Go to your cube on CubeCobra
2. Click **List** tab → **Export** → **Replace with CSV Import**
3. Upload `cubes/<slug>/exports/import-ready.csv`

Your card list, tags, and notes are applied in one step.

---

## Skills (Claude Code Slash Commands)

These skills run inside Claude Code and use your local cube data as context. Invoke them by typing the command in your Claude Code session while in this project directory. All skills require `cuber fetch` and `cuber enrich` to have been run first.

### `/tag-cube <id>`

AI-tags every card in a cube by reading oracle text from `enriched.json`. Shows a tag summary table and asks for confirmation before writing `tagged.csv`. Tags are merged with any existing ones (use `cuber tag <id> --overwrite` to replace instead).

Does **not** require a separate `cuber tag` run — this skill is the interactive version.

**Example:** `/tag-cube obc`

---

### `/analyze-cube <id>`

Full stats dashboard plus deep environmental analysis: color distribution, CMC curve, rarity, card types, archetype tag density, environment characterization, archetype viability matrix, per-color breakdown, mana and fixing inventory, interaction density, drafting signals, and notable cards. All metrics are informational — no thresholds trigger errors or warnings. Requires `enriched.json`; tag-dependent sections (archetype matrix, interaction density, notable cards) additionally require `cuber tag <id>`.

After the analysis, optionally generates a formatted **primer document** for the cube. You choose which of 7 sections to include; the skill writes to `primer.md` (or `primer_ai.md` if you decline to overwrite an existing primer).

**Example:** `/analyze-cube obc`

---

### `/discover-archetypes <id>`

Discovers every viable draft archetype in a cube — deeply-supported core strategies down to single-card build-arounds — with the cards that make each one work. Starts from `taxonomic_profile` tags but actively hunts for untagged supporting cards by reasoning over oracle text (a big graveyard-bound creature with no `Reanimator` tag is still a reanimation target if the cube has a reanimation effect). Considers all rarities. Supports a default organic-discovery mode and a guided-coverage mode where you specify what must be classified (e.g. "classify every rare, mythic, and multicolor uncommon"). Writes a tiered report (`Core` / `Supported` / `Build-Around`) to `archetypes.md` plus a machine-readable `archetypes.csv`. Requires `cuber tag <id>` to have been run first.

**Example:** `/discover-archetypes obc` → "what archetypes does this cube support?"

---

### `/build-deck <id>`

Builds a deck from your cube in any supported format. Uses a discovery-first approach: the skill finds viable win conditions in the pool before any strategy is declared, presents a shortlist of 3–5 pipelines, lets you pick or override, then assembles the deck with proportionally-reasoned slot allocations. An independent cold-Challenger grill gate runs before the final list is shown.

**Supported formats:**
- **40-card draft** — standard cube draft deck (default sideboard: 8)
- **60-card constructed** — with sideboard (default: 15)
- **Commander-60** — 60 cards + 1 commander (or 2 partners)
- **Commander-100** — classic 100-card EDH

**Phase flow:**
- **Phase 0 — Card Pool Definition:** Mints a collision-safe run token and creates this run's private `_workspace/<run-token>/` directory (concurrent runs can never touch each other's files), then optionally restricts the pool (copy limits per rarity, specific card exclusions). The skill infers a `card_pool_rules` object from natural language and confirms before proceeding.
- **Phase 1 — Interview:** Cube, format, optional color preference, intent (Competitive / Experimental / Fun / Specific Constraint), power level.
- **Phase 2 — Discovery:** Builds/loads the **cube dossier** (`cuber dossier <id>`), then finds Payoff candidates via `taxonomic_profile.structural_roles`, validates each against Enabler/Fodder and Engine/Outlet counts per `synergy_clusters`, and produces a viable pipeline shortlist. Also authors the dossier's `interaction_chains` — oracle-grounded card combinations that tags alone cannot express ("card A changes card B's type so card C can eat it").
- **Phase 3 — Strategy Selection:** Shows the shortlist with a recommendation based on your intent. You accept, pick another, or describe your own constraint.
- **Phase 4 — Commander Selection** (commander formats only): finds valid commanders, handles partners.
- **Phase 5 — Deck Build:** The orchestrator builds the deck — after a mandatory **Fresh-Eyes Sweep** in which every card in the deck's legal pool gets a recorded, fresh verdict scoped to *this* deck (saved as `sweep.json`; this is what prevents a card rejected for a previous deck from being silently skipped). All slot allocations are expressed as proportions of deck size N, with rationale for each. Mana sources are derived from pip demand, and a deterministic pre-flight validator runs before the grill.
- **Phases 6–9:** Mana audit, sideboard, grill bundle, self-grill: a single cold-context **Challenger agent** audits the deck from a hashed bundle — hard legality checks, an exhaustive per-card oracle defense (INDEFENSIBLE list), quantitative-verdict recounts, and an **absence audit** ("what strong pool card is missing?") from a context that has never seen another deck — derived oracle-text-first, with engines that no `interaction_chains` entry records reported as new chain candidates for the session-end write-back. The orchestrator adjudicates findings; legality violations, audit regressions, and counts that fail to reproduce are non-negotiable. One grill round by default; a second only on a hard finding.
- **Re-evaluation:** If the self-grill challenger declares a pipeline fundamentally broken, the skill automatically tries the next pipeline from the Phase 3 shortlist without restarting discovery. A *colour-allocation* observation, by contrast, is advisory only — the deck is always built in the colours you locked.

**Isolation model — what crosses between decks, and what never does.** The orchestrator builds warm
(it knows the cube); decks stay isolated by three guards, not by a cold builder:

| Knowledge | Scope | Crosses between decks? |
|---|---|---|
| Cube facts, interaction chains, pool limits | the cube | **Yes** — via the dossier |
| Card-quality verdicts | the (card, list) pair | **Never** — the Fresh-Eyes Sweep forces every legal-pool card to be re-evaluated fresh per deck |
| Grill findings, repair lessons, build narratives | one deck's run | **Never** — and the analysis firewall keeps them out of the output |

The dossier is frozen *before the first deck is built* (new interaction chains are written back only
at session end), so it is structurally incapable of carrying a finding about any deck, and every deck
in a session embeds the same `dossier_sha256`. Together with the sweep and the cold Challenger's
absence audit, that is what lets you build many decks in one session without deck 2 inheriting deck
1's conclusions — a cost reducer correctly cut from a deck whose kill is an activated ability must be
**re-evaluated from scratch** for the next deck, where it may discount most of the list.

**Example:** `/build-deck obc` → "40-card, Competitive intent, surprise me on colors"

---

### `/suggest-cube <id>`

Analyzes your cube for weaknesses (color gaps, archetype starvation, power outliers) and proposes specific card swaps with oracle text evidence. A self-grill gate verifies each cut and add before you see the recommendations. Applies changes via CLI commands on approval.

**Example:** `/suggest-cube obc`

---

### `/set-cube <set-code>`

Creates a full cube project from all cards in a retail MTG set. Identifies mechanical themes by reading oracle text (never from training data), assesses draft viability, and optionally suggests cuts to reach a target size. All standard commands (`status`, `add-card`, `remove-card`, `export`, etc.) work identically on a set cube.

**Example:** `/set-cube eoe` or `/set-cube` → "build me a cube from Edge of Eternities"

---

## LLM Configuration

Copy `.env.example` to `.env` and configure your provider:

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.anthropic.com/v1
LLM_MODEL=claude-sonnet-4-6
```

Any OpenAI-compatible endpoint works:

| Provider | LLM_BASE_URL | LLM_MODEL |
|----------|-------------|-----------|
| Claude (Anthropic) | `https://api.anthropic.com/v1` | `claude-sonnet-4-6` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Groq | `https://api.groq.com/openai/v1` | `llama3-70b-8192` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3` |

AI features: `cuber tag`, `/tag-cube`, `/build-deck`, `/suggest-cube`, `/set-cube`. All other commands work without an LLM key.

---

## Acknowledgements

Skill design patterns — iron rule (oracle text only), self-grill gate, human-readable + JSON sidecar, and the tool selection table convention — are adapted from [dan-blanchard/mtg-skills](https://github.com/dan-blanchard/mtg-skills) (0BSD license). The mana audit formulas (Burgess + Karsten) and commander detection logic are also adapted from that project. Highly recommended as a companion for deck construction and rules questions.

# Cubecobra Cuber

A local Python toolkit for managing your Magic: The Gathering cubes on [CubeCobra](https://cubecobra.com). Fetch your cube as a structured project, edit it locally, enrich with Scryfall metadata, tag cards by function using AI, analyze statistics, build decks with an AI that debates itself, and export a file ready to import back into CubeCobra.

## What It Does

- **Fetch** any public CubeCobra cube into a local project folder — full JSON snapshot, primer, card list, and metadata all separated into editable files
- **Add cards** to your cube (single card, batch list, or from a file) with automatic Scryfall enrichment on the next `enrich` run; supports multiple copies
- **Remove cards** from your cube by name — removes all copies by default, or exactly N copies with `--count`
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
    analysis.json          ← statistics from last `stats` run (auto-generated)
    decks/
      aggro-rg/            ← deck built by /build-deck (one folder per deck)
        deck.json          ← full deck data (cards, mana audit, restrictions)
        deck.csv           ← same deck as a human-readable CSV
        deck.mwDeck        ← Magic Workstation format for MTGO import
        analysis.md        ← deck analysis with YAML frontmatter (dashboard-ready)
    exports/
      import-ready.csv     ← assembled by `cuber export`, upload this to CubeCobra
```

**`remote/` is the last known CubeCobra state — never edit it.** Your edits go into the working files. `cuber status` shows the diff between remote and working. `cuber export` assembles the upload file when you're done.

---

## CLI Command Reference

All commands follow `python -m cuber <command> [options]` or `cuber <command>` after `pip install -e .`.

The `<id>` argument accepts either the CubeCobra short ID (e.g. `obc`) or the local title slug (e.g. `my-vintage-cube`). The slug — the folder name under `cubes/` — takes priority; the short ID is used as a fallback.

### Cube Lifecycle

| Command | Description | Example |
|---------|-------------|---------|
| `fetch <id>` | Download a public cube from CubeCobra. Creates the full project folder. | `cuber fetch obc` |
| `fetch <id> --dry-run` | Print the CubeCobra URL without downloading. | `cuber fetch obc --dry-run` |
| `add-card <id> <names...>` | Add one or more cards to the mainboard. Names are verified against Scryfall by default — typos are corrected to the canonical name; unknown names are rejected. Stubs are hydrated on the next `enrich`. | `cuber add-card obc "Lightning Bolt" "Brainstorm"` |
| `add-card <id> <names...> --no-verify` | Add cards without Scryfall verification (bulk imports with known-good names). | `cuber add-card obc --from-file known-cards.txt --no-verify` |
| `add-card <id> <names...> --count N` | Add N copies of each named card. | `cuber add-card obc "Lightning Bolt" --count 4` |
| `add-card <id> --from-file <path>` | Add cards from a text file (one name per line). | `cuber add-card obc --from-file new-cards.txt` |
| `add-card <id> --stdin` | Add cards from stdin (newline-separated). | `echo "Lightning Bolt" \| cuber add-card obc --stdin` |
| `add-card <id> <names...> --maybeboard` | Send added cards to the maybeboard instead. | `cuber add-card obc "Teferi" --maybeboard` |
| `swap <id> <old> <new>` | Atomically replace one card with another. Verifies the new card on Scryfall before removing the old one — aborts without changes if the new card is not found or the old card isn't in the cube. | `cuber swap obc "Dark Ritual" "Cabal Ritual"` |
| `swap <id> <old> <new> --maybeboard` | Operate on the maybeboard instead. | `cuber swap obc "Card A" "Card B" --maybeboard` |
| `remove-card <id> <names...>` | Remove cards from the mainboard. Removes all copies of each named card by default. | `cuber remove-card obc "Lightning Bolt"` |
| `remove-card <id> <names...> --count N` | Remove only N copies (for constructed cubes with intentional multiples). | `cuber remove-card obc "Lightning Bolt" --count 2` |
| `remove-card <id> --from-file <path>` | Remove cards listed in a file (one name per line). | `cuber remove-card obc --from-file cuts.txt` |
| `remove-card <id> <names...> --maybeboard` | Remove from maybeboard instead. | `cuber remove-card obc "Teferi" --maybeboard` |
| `dedup <id>` | Remove duplicate rows, keeping one copy of each card name. | `cuber dedup obc` |
| `status <id>` | Show cards added, removed, or retagged since last fetch. | `cuber status obc` |
| `export <id>` | Assemble `exports/import-ready.csv` from `mainboard.csv`. Validates all card names against Scryfall (using `enriched.json` as a cache for already-verified cards). Blocks export if any card names are not found. | `cuber export obc` |
| `export <id> --skip-scryfall` | Skip Scryfall validation entirely (offline use). | `cuber export obc --skip-scryfall` |

### Enrichment & Tagging

| Command | Description | Example |
|---------|-------------|---------|
| `enrich <id>` | Look up each card on Scryfall; hydrate stubs from `add-card`. Auto-fetches if needed. | `cuber enrich obc` |
| `enrich <id> --refresh` | Re-fetch Scryfall data for all cards (bypass 7-day cache). | `cuber enrich obc --refresh` |
| `stats <id>` | Print color, CMC, rarity, and type distributions. Writes `analysis.json`. | `cuber stats obc` |
| `tag <id>` | AI-tag all cards using oracle text. Writes `tagged.csv`. Requires LLM config. | `cuber tag obc` |
| `tag <id> --overwrite` | Replace existing tags instead of merging. | `cuber tag obc --overwrite` |

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

Full statistics dashboard: color distribution, CMC curve, rarity, card types, and archetype tag density. All metrics are informational — no thresholds trigger errors or warnings.

**Example:** `/analyze-cube obc`

---

### `/build-deck <id>`

Builds a deck from your cube in any supported format. Runs a structured interview, identifies the deck's archetype identity from tag density, validates the mana base using established formulas (Burgess + Karsten), enforces any restrictions you specify, and runs a two-agent self-grill debate before showing the final list.

**Supported formats:**
- **40-card draft** — standard cube draft deck (17 lands, default sideboard: 8)
- **60-card constructed** — with sideboard (default: 15)
- **Commander-60** — 60 cards + 1 commander (or 2 partners)
- **Commander-100** — classic 100-card EDH

**Restrictions:** The skill understands natural-language restrictions like "up to 2 copies of commons or uncommons, 1 copy of rares, no infinite combos." Both the builder and the self-grill challenger enforce restrictions mechanically.

**Example:** `/build-deck obc` → "40-card BG graveyard deck, up to 1 rare, no infinite combos"

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

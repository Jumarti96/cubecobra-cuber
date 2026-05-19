## Why

Managing Magic: The Gathering cubes on CubeCobra is done entirely through a web UI with no local tooling — making bulk edits, AI-assisted tagging, statistical analysis, and deck building slow and manual. This project builds a local Python toolkit that bridges CubeCobra and Scryfall, enabling AI-powered workflows on top of cube data you own.

## What Changes

This is a greenfield project — no existing code is being modified.

- **New**: Python package `cuber/` with CLI entry point (`python -m cuber`)
- **New**: CubeCobra client that fetches public cube data (CSV/JSON) without authentication
- **New**: Scryfall client with SQLite lazy cache for per-card metadata enrichment
- **New**: Canonical `enriched.json` format joining CubeCobra and Scryfall data
- **New**: LLM abstraction (`llm.py`) using OpenAI-compatible endpoint, provider-agnostic
- **New**: AI tagger that reads oracle text and assigns functional tags (semicolon-separated, CubeCobra-importable)
- **New**: Stats engine for color/type/rarity/CMC distribution reporting
- **New**: Exporter that writes `tagged.csv` directly importable via CubeCobra's "Replace with CSV" UI
- **New**: Five Claude Code skills: `/tag-cube`, `/analyze-cube`, `/build-deck`, `/suggest-cube`, `/set-cube`
- **New**: `fetch-set` command that builds a cube from all cards in a given retail MTG set
- **New**: `diff` command for comparing two cubes
- **New**: `README.md` for GitHub with setup, quickstart, and full command/skill reference

## Capabilities

### New Capabilities

- `cubecobra-client`: Fetch public cube data from CubeCobra (CSV, JSON, plaintext); handle 403/UA issues; write raw.csv + meta.json per cube
- `scryfall-client`: Per-card Scryfall API lookups with SQLite caching; batch fetch via /cards/collection; set-card queries for fetch-set
- `cube-data-model`: Card and Cube dataclasses; canonical enriched.json schema joining CubeCobra and Scryfall fields
- `stats-engine`: Color identity distribution, CMC curve, rarity breakdown, card type breakdown, archetype tag density — all informational, never hard gates
- `llm-abstraction`: OpenAI-compatible LLM call layer; configured via LLM_API_KEY / LLM_BASE_URL / LLM_MODEL env vars; no provider SDK in feature code
- `ai-tagger`: Prompt builder that feeds oracle text to the LLM and produces functional tags; writes tagged.csv in CubeCobra-importable format
- `cli-commands`: Typer-based CLI — fetch, enrich, stats, tag, export, fetch-set, list, diff
- `skill-tag-cube`: Claude Code skill — reads enriched.json, calls AI tagger, writes tagged.csv
- `skill-analyze-cube`: Claude Code skill — stats dashboard + archetype coverage report + analysis.json sidecar
- `skill-build-deck`: Claude Code skill — interview → skeleton → self-grill gate → 40-card deck output
- `skill-suggest-cube`: Claude Code skill — analyze gaps → propose swaps → self-grill gate → user approval → updated tagged.csv
- `skill-set-cube`: Claude Code skill — fetch all cards from a retail set → identify mechanical identity → analyze for draft viability → optional cuts to target size

### Modified Capabilities

_(none — greenfield project)_

## Impact

- **Dependencies**: `typer`, `httpx`, `sqlite3` (stdlib), `python-dotenv`, `openai` (used only in llm.py as OpenAI-compatible client)
- **New files**: All files in `cuber/`, `skills/`, `cubes/` (gitignored), `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`
- **External APIs**: CubeCobra public endpoints (no auth), Scryfall REST API (no auth, rate-limited to 10 req/sec), user-configured LLM endpoint
- **Data at rest**: `cubes/{short-id}/` folders — raw.csv, enriched.json, tagged.csv, meta.json, optional decks/

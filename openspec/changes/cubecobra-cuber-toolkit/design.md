## Context

CubeCobra is the primary platform for hosting and managing Magic: The Gathering cube lists online. It has a limited public read API (no authentication required for public cubes) and a write API that requires session cookies and CSRF tokens. Scryfall is the de-facto standard card database for MTG software — free, well-documented, and comprehensive.

This project runs entirely on the user's local machine. There is no server component. The user interacts through two surfaces: a Python CLI for data operations and Claude Code skills (slash commands) for AI-assisted analysis and deck building.

Key external constraints:
- CubeCobra returns HTTP 403 to requests with default Python `urllib` User-Agent
- Scryfall enforces a 10 req/sec rate limit; bulk fetch via `/cards/collection` (75 cards per call) is preferred for large cubes
- The user's LLM provider is not fixed — must be swappable via env vars

## Goals / Non-Goals

**Goals:**
- Fetch any public CubeCobra cube locally with a single command
- Enrich cube cards with full Scryfall metadata (oracle text, color identity, CMC, P/T, rarity)
- AI-tag cards by functional role using oracle text only (never training-data assumptions)
- Produce a `tagged.csv` that CubeCobra can import directly via "Replace with CSV" — zero manual reformatting
- Provide Claude Code skills for tagging, analysis, deck building, cube improvement, and set-based cube creation
- Self-grill (two-agent debate) gates on /build-deck and /suggest-cube before presenting output
- LLM provider is pluggable via three env vars; no provider lock-in in feature code

**Non-Goals:**
- Authenticated CubeCobra write operations (deferred to a future phase)
- A web UI or any server component
- Support for private/unlisted CubeCobra cubes
- Real-time CubeCobra sync (fetch is always explicit, on-demand)
- Scryfall bulk data download (~500MB) — lazy per-card cache is sufficient for typical cube sizes

## Decisions

### D1: Python package `cuber/` with `python -m cuber` invocation

**Decision**: All Python modules live in a `cuber/` package. Primary invocation is `python -m cuber <command>`. A `pyproject.toml` entry point (`cuber = "cuber.cli:app"`) enables `cuber <command>` after `pip install -e .` with zero code changes.

**Rationale**: `python -m cuber` works immediately in any venv without installation. The entry point pivot requires one command and no code changes. This is the Python community standard for internal tools that may later be distributed.

**Alternatives considered**: Single `cuber.py` script at root — simpler but not package-importable by skills; hard to split into modules cleanly.

---

### D2: Typer for CLI

**Decision**: Use [Typer](https://typer.tiangolo.com/) as the CLI framework.

**Rationale**: Typer derives commands from Python type hints, auto-generates help text and shell completions, and requires minimal boilerplate. It wraps Click under the hood, so switching to raw Click later is trivial.

**Alternatives considered**: `argparse` (stdlib, more verbose, no auto-help generation), `click` directly (equally capable but more boilerplate than Typer for typed args).

---

### D3: SQLite lazy cache for Scryfall data

**Decision**: Scryfall data is fetched per-card on demand and cached in `cubes/.cache/scryfall.db` (SQLite). Cache key is card name (normalized). Batch fetch via `/cards/collection` (75 cards/call). No bulk data download.

**Rationale**: A 360–540 card cube requires ~5–8 batch API calls (~5 seconds). SQLite is zero-infrastructure, portable, and queryable. The 500MB bulk download is unnecessary for typical usage.

**Risk**: Scryfall data can change (errata, new prints). Mitigation: cache TTL of 7 days; explicit `cuber enrich --refresh` flag to bust cache.

**Alternatives considered**: Full bulk data download (~500MB) — faster for large cubes but heavyweight for day-one; in-memory cache — lost between runs.

---

### D4: enriched.json as the CLI ↔ Skills contract

**Decision**: `cubes/{short-id}/enriched.json` is the single handoff file between CLI data operations and Claude Code skills. Skills read this file; they do not call the CLI as a subprocess.

**Rationale**: Skills have full LLM context and can reason over the enriched JSON directly. Subprocess calls from skills are fragile (venv path, stderr parsing). The file contract is explicit, version-stable, and inspectable.

**Alternatives considered**: Skills call CLI as subprocess and parse stdout — brittle; skills re-implement data fetching — duplication.

---

### D5: CubeCobra short ID as folder name

**Decision**: Cube data folders are named by CubeCobra short ID (vanity URL slug, e.g., `obc`, `vintage-540`). If no short ID exists, fall back to a slugified cube title. `meta.json` inside the folder stores the full UUID and other metadata.

**Rationale**: Short IDs are human-readable, stable, and already used in CubeCobra sharing links. They are never longer than ~20 chars and contain no spaces or special characters. The UUID (needed for API calls) is stored in `meta.json`, not baked into the path.

---

### D6: LLM abstraction via OpenAI-compatible endpoint

**Decision**: All LLM calls go through `cuber/llm.py`, which uses the `openai` Python SDK pointed at a configurable base URL. Configuration: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` env vars. No other provider SDK is imported anywhere in the codebase.

**Rationale**: The OpenAI SDK supports any OpenAI-compatible endpoint (Claude via API gateway, Groq, Ollama, local models). This gives full provider flexibility without maintaining multiple client implementations.

**Constraint**: Prompts must be plain chat-format (system + user messages). No provider-specific features (tool use, vision, extended thinking) unless a graceful degradation path exists for providers that don't support them.

---

### D7: Tags as semicolons in CubeCobra CSV format

**Decision**: The `tags` column in `tagged.csv` uses semicolons as separators (e.g., `removal;creature-removal;aggro`), matching CubeCobra's own export format. This makes the output directly importable via CubeCobra's "Replace with CSV" feature without any transformation.

**Rationale**: Reverse-engineered from CubeCobra's own CSV exports. Tags with spaces are fine; semicolons are the delimiter.

---

### D8: Self-grill pattern (two parallel agents) in /build-deck and /suggest-cube

**Decision**: Before presenting final output, both `/build-deck` and `/suggest-cube` run a self-grill: two parallel subagents (Proposer + Challenger) debate the recommendation. The Proposer defends; the Challenger verifies oracle text, checks correctness of role assignments, and surfaces better alternatives. Both agents must cite oracle text from `enriched.json` — never training-data assumptions.

**Rationale**: Adopted from dan-blanchard/mtg-skills, where this pattern catches oracle text misreadings, color pip issues, and archetype density failures before the user sees the output. The cost (one extra LLM call pair) is justified by the quality gate.

---

### D9: User-Agent and 403 handling for CubeCobra

**Decision**: `cubecobra.py` sends `User-Agent: Mozilla/5.0 (compatible; CubeCobraClient/1.0)` on all requests. If a 403 is still received, fall back to `subprocess` call to `curl` with the same header.

**Rationale**: CubeCobra's CDN/WAF blocks default Python `urllib`/`requests` UAs. This is documented behavior observed by other CubeCobra tooling (e.g., dan-blanchard's `cubecobra-fetch`).

## Risks / Trade-offs

**CubeCobra API surface is undocumented** → Endpoints discovered by reading open-source server code and community tooling. If CubeCobra changes URL structure, `cubecobra.py` breaks. Mitigation: pin to the three well-known public endpoints; add a `--dry-run` flag that prints the URL before fetching.

**Scryfall rate limit** → Fetching a 540-card cube cold takes ~8 batch calls (~8 seconds). Fine for interactive use; would be a problem for bulk operations on many cubes. Mitigation: batch via `/cards/collection` (75/call); SQLite cache means subsequent runs are instant.

**LLM token cost for tagging** → A 540-card cube with full oracle text could be a large prompt. Mitigation: `tagger.py` sends cards in batches of 50; the `tag` command shows a cost estimate before proceeding.

**Card name apostrophes break shell quoting** → Adopted from dan-blanchard: all JSON files with card names are written via the Write tool, never via shell echo/here-doc. Skills must follow the same pattern.

**CubeCobra CSV format could change** → The 19-column format is read from the open-source download route. If columns are added/removed, `exporter.py` breaks. Mitigation: write a schema version to `meta.json`; warn if CubeCobra CSV columns don't match expected headers.

## Open Questions

~~Should `cuber enrich` automatically trigger `cuber fetch` if `raw.csv` is missing, or fail fast and prompt the user?~~
**Resolved (D10):** Auto-trigger `fetch` if `raw.csv` is missing. See D10 below.

~~Should `/build-deck` output be written to `cubes/{id}/decks/` by default, or ask the user for an output path?~~
**Resolved (D11):** Fixed path `cubes/{short-id}/decks/`. See D11 below.

~~For `fetch-set`, should basic lands be excluded by default (with an `--include-basics` flag), or included and let the user decide via skill?~~
**Resolved (D12):** Exclude basics by default; `--include-basics` flag to opt in. See D12 below.

---

### D10: enrich auto-triggers fetch when raw.csv is missing

**Decision**: If `raw.csv` is not present when `cuber enrich` is run, the command automatically runs `fetch` first without prompting, then proceeds with enrichment.

**Rationale**: The most common flow is `fetch` then `enrich` in sequence. Failing fast adds friction with no benefit — the user almost always wants both. The auto-trigger behavior is logged to stdout so it is visible.

---

### D11: /build-deck writes to fixed path cubes/{short-id}/decks/

**Decision**: Deck files are always written to `cubes/{short-id}/decks/{deck-name}.json`. The deck name is derived from the strategy + colors stated in the interview (e.g., `aggro-rw.json`).

**Rationale**: Fixed paths make decks discoverable and consistent. The `cubes/` directory is already the local state store for all cube-related data.

---

### D12: fetch-set excludes basic lands by default

**Decision**: `cuber fetch-set {code}` excludes basic lands (Plains, Island, Swamp, Mountain, Forest, Wastes) and tokens by default. The `--include-basics` and `--include-tokens` flags opt back in.

**Rationale**: A cube of "every card in a set" is almost universally understood to mean non-basic, non-token cards. Basics and tokens clutter the cube list and are rarely useful in a drafted cube context.

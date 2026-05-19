## 1. Project Scaffolding

- [x] 1.1 Create `.venv` via `python -m venv .venv` and activate it
- [x] 1.2 Create `pyproject.toml` with project metadata, entry point `cuber = "cuber.cli:app"`, and dev dependencies
- [x] 1.3 Create `requirements.txt` listing: `typer`, `httpx`, `python-dotenv`, `openai`
- [x] 1.4 Create `.env.example` with `LLM_API_KEY=`, `LLM_BASE_URL=`, `LLM_MODEL=`
- [x] 1.5 Create `.gitignore` excluding `.venv/`, `cubes/`, `.env`, `__pycache__/`, `*.pyc`, `.cache/`
- [x] 1.6 Create `cuber/` package directory with empty `__init__.py`
- [x] 1.7 Create `skills/` directory
- [x] 1.8 Install dependencies: `pip install -r requirements.txt`

## 2. Core Data Layer

- [x] 2.1 Implement `cuber/cube.py`: `Card` and `Cube` dataclasses matching the canonical enriched.json schema; include `card_faces` optional field for DFCs
- [x] 2.2 Implement `cuber/cube.py`: `load_enriched(short_id)` and `save_enriched(cube, short_id)` helpers; `load_meta(short_id)` and `save_meta(meta, short_id)`
- [x] 2.3 Implement `cuber/cube.py`: `load_raw_csv(short_id)` that parses CubeCobra's 19-column CSV into a list of dicts; validates column headers and sets `schema_warning` in meta if mismatched

## 3. CubeCobra Client

- [x] 3.1 Implement `cuber/cubecobra.py`: `fetch_cube(short_id)` using `httpx` with `User-Agent: Mozilla/5.0 (compatible; CubeCobraClient/1.0)`; try CSV download first
- [x] 3.2 Implement `cuber/cubecobra.py`: 403 fallback — retry using `subprocess` call to `curl` with the same User-Agent header
- [x] 3.3 Implement `cuber/cubecobra.py`: write `cubes/{short_id}/raw.csv` and `cubes/{short_id}/meta.json` after successful fetch; create cube directory if it doesn't exist
- [x] 3.4 Implement `cuber/cubecobra.py`: `fetch_set(set_code, exclude_basics=True, exclude_tokens=True)` using Scryfall `/cards/search?q=set:{code}` with pagination; writes to `cubes/{set_code}/`

## 4. Scryfall Client

- [x] 4.1 Implement `cuber/scryfall.py`: SQLite schema for card cache (`cubes/.cache/scryfall.db`) with columns matching enriched.json card fields plus `cached_at` timestamp
- [x] 4.2 Implement `cuber/scryfall.py`: `lookup_cards(names)` using `/cards/collection` endpoint (75 cards per batch); 100ms delay between batches; returns list of Scryfall card objects
- [x] 4.3 Implement `cuber/scryfall.py`: cache read/write with 7-day TTL; `refresh=False` parameter to bypass cache
- [x] 4.4 Implement `cuber/scryfall.py`: DFC handling — extract `card_faces` array for `transform` and `modal_dfc` layouts
- [x] 4.5 Implement `cuber/scryfall.py`: graceful handling of cards not found — collect into `missing_cards` list, continue with remaining cards
- [x] 4.6 Implement `cuber/scryfall.py`: `enrich_cube(short_id, refresh=False)` — loads raw.csv, batch-looks up all cards, writes enriched.json; updates `meta.json.card_count` and `meta.json.missing_cards`

## 5. Stats Engine

- [x] 5.1 Implement `cuber/stats.py`: `compute_stats(cube)` returning a dict with color_distribution, cmc_curve (by type), rarity_breakdown, card_type_breakdown
- [x] 5.2 Implement `cuber/stats.py`: ASCII bar chart renderer for CMC curve
- [x] 5.3 Implement `cuber/stats.py`: `compute_tag_density(cube)` — counts cards per tag, flags tags with fewer than 3 cards as informational notes (not errors)
- [x] 5.4 Implement `cuber/stats.py`: `format_stats_report(stats)` for human-readable stdout output
- [x] 5.5 Implement `cuber/stats.py`: `write_analysis_json(stats, short_id)` — saves full stats to `cubes/{short_id}/analysis.json`

## 6. LLM Abstraction

- [x] 6.1 Implement `cuber/llm.py`: load `.env` via `python-dotenv`; validate `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` are set; raise `EnvironmentError` with helpful message if missing
- [x] 6.2 Implement `cuber/llm.py`: `chat(messages, temperature=0.2)` — calls OpenAI SDK with configured base URL; catches API errors and raises typed `LLMError`
- [x] 6.3 Implement `cuber/llm.py`: `estimate_tokens(messages)` — rough token count estimate for cost preview (word count × 1.3)

## 7. AI Tagger

- [x] 7.1 Implement `cuber/tagger.py`: canonical tag vocabulary as a module-level constant
- [x] 7.2 Implement `cuber/tagger.py`: `build_tagging_prompt(cards_batch)` — constructs system + user messages with card name, type_line, oracle_text for each card; instructs LLM to use canonical tags and cite oracle text
- [x] 7.3 Implement `cuber/tagger.py`: `tag_cards(cube, overwrite=False)` — processes cards in batches of 50; shows token estimate and cost preview with confirmation before calling LLM; merges or overwrites tags based on flag
- [x] 7.4 Implement `cuber/tagger.py`: parse LLM response into `{card_name: [tags]}` dict; handle malformed responses gracefully (log warning, skip card)

## 8. Exporter

- [x] 8.1 Implement `cuber/exporter.py`: `write_tagged_csv(cube, short_id)` — writes 19-column CubeCobra CSV with `tags` column as semicolon-separated string; handles apostrophes in card names safely
- [x] 8.2 Implement `cuber/exporter.py`: `write_deck_json(deck, short_id, deck_name)` — writes deck to `cubes/{short_id}/decks/{deck_name}.json` using deck schema

## 9. CLI Commands

- [x] 9.1 Implement `cuber/__main__.py`: single-line entry point importing and calling the Typer app
- [x] 9.2 Implement `cuber/cli.py`: Typer app with `fetch` command — calls `cubecobra.fetch_cube()`; supports `--dry-run` flag
- [x] 9.3 Implement `cuber/cli.py`: `enrich` command — calls `scryfall.enrich_cube()`; supports `--refresh`; if raw.csv is missing, auto-triggers `fetch` first with a logged notice before proceeding
- [x] 9.4 Implement `cuber/cli.py`: `stats` command — loads enriched.json, calls `stats.compute_stats()`, prints report, writes analysis.json; fails with clear message if enriched.json missing
- [x] 9.5 Implement `cuber/cli.py`: `tag` command — calls `tagger.tag_cards()`, writes tagged.csv via exporter; supports `--overwrite`
- [x] 9.6 Implement `cuber/cli.py`: `export` command — loads enriched.json, writes tagged.csv from current tags
- [x] 9.7 Implement `cuber/cli.py`: `fetch-set` command — calls `cubecobra.fetch_set()`; supports `--include-basics` and `--include-tokens` flags (both default False)
- [x] 9.8 Implement `cuber/cli.py`: `list` command — scans `cubes/` for meta.json files, prints table with short_id, title, card_count, fetched_at
- [x] 9.9 Implement `cuber/cli.py`: `diff` command — loads enriched.json for both cubes, computes shared/unique cards and stat deltas, prints table and writes sidecar JSON to `/tmp/cube-diff.json`

## 10. Skills

- [x] 10.1 Write `skills/tag-cube.md`: skill header, iron rule (oracle text only), step-by-step workflow referencing enriched.json, confirmation prompt before writing tagged.csv, tool selection table
- [x] 10.2 Write `skills/analyze-cube.md`: skill header, step-by-step analysis workflow, tool selection table (maps tasks → CLI commands), balance-checks-are-informational reminder, analysis.json sidecar instruction
- [x] 10.3 Write `skills/build-deck.md`: skill header, iron rule, interview sequence (cube → strategy → colors → power level → restrictions), deck skeleton structure (lands/engine/threats/interaction), self-grill gate (Proposer + Challenger roles, both must cite oracle text), deck output table format, deck JSON write instruction
- [x] 10.4 Write `skills/suggest-cube.md`: skill header, iron rule, analysis pipeline, gap identification criteria, self-grill gate (Proposer + Challenger roles), recommendations table format, user approval gate, tagged.csv update instruction, balance-checks-are-informational reminder
- [x] 10.5 Write `skills/set-cube.md`: skill header, iron rule, set code resolution step, inclusion interview (basics/tokens/rarities), mechanical identity analysis from oracle text, draft viability assessment, optional size reduction workflow with self-grill, output path convention

## 11. README

- [x] 11.1 Write `README.md`: project overview section explaining what the toolkit does in plain language
- [x] 11.2 Write `README.md`: prerequisites and setup section (Python 3.11+, venv, pip install, .env config)
- [x] 11.3 Write `README.md`: Quick Start section (fetch → enrich → tag → export → upload to CubeCobra)
- [x] 11.4 Write `README.md`: full CLI command reference table with descriptions and examples
- [x] 11.5 Write `README.md`: skills (slash commands) reference with descriptions and example prompts
- [x] 11.6 Write `README.md`: note on tagged.csv being directly importable via CubeCobra "Replace with CSV"
- [x] 11.7 Write `README.md`: acknowledgements section crediting dan-blanchard/mtg-skills for skill patterns

## 12. Validation

- [x] 12.1 Test `python -m cuber fetch` against a known public CubeCobra cube; verify raw.csv and meta.json are written correctly
- [x] 12.2 Test `python -m cuber enrich` on the fetched cube; verify enriched.json contains oracle_text, color_identity, and cmc for all cards; check SQLite cache is populated
- [x] 12.3 Test `python -m cuber stats`; verify ASCII bar chart renders and analysis.json is written
- [x] 12.4 Test `python -m cuber tag` with a small cube (≤20 cards); verify tagged.csv columns match CubeCobra format exactly; verify tags are semicolon-separated
- [x] 12.5 Test `python -m cuber fetch-set` with a small set; verify basic lands are excluded by default
- [x] 12.6 Test `python -m cuber list` and `python -m cuber diff` with two cubes
- [ ] 12.7 Verify tagged.csv can be imported into CubeCobra via "Replace with CSV" without errors

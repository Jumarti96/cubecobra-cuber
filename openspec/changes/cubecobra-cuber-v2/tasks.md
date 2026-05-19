## 1. cube_manager.py — Fetch & Disassemble

- [x] 1.1 Implement `cuber/cube_manager.py`: `slugify(name)` helper — lowercase, replace spaces/punctuation with hyphens, strip leading/trailing hyphens; append short-id suffix on collision
- [x] 1.2 Implement `cube_manager.py`: `fetch_and_disassemble(short_id)` — calls `/cube/api/cubeJSON/<id>` (with curl fallback for 403); writes `remote/cube.json` and `remote/mainboard.csv`; extracts and writes `meta.json`, `primer.md`, `mainboard.csv` (working copy), `maybeboard.csv`; creates `exports/` and `decks/` subdirs
- [x] 1.3 Implement `cube_manager.py`: `meta.json` schema — `{ title, short_id, slug, format, owner, fetched_at, card_count, missing_cards, schema_warning }`
- [x] 1.4 Implement `cube_manager.py`: working `mainboard.csv` is a copy of `remote/mainboard.csv` on first fetch; on re-fetch, merge strategy: add new remote cards, preserve local removals, warn on conflicts (card in remote but locally deleted)
- [x] 1.5 Implement `cube_manager.py`: `primer.md` extraction — write `cube.json.description` as Markdown; prepend `# {cube.name}\n\n`; handle None/empty description gracefully

## 2. add-card Command

- [x] 2.1 Implement `cube_manager.py`: `add_cards(short_id, names, board="mainboard")` — normalize names (strip whitespace, deduplicate within batch); detect existing names in target CSV and warn+skip; append stub rows `{name},,,,,,,,,,,,,,,,,,,` to target CSV; print summary of added/skipped
- [x] 2.2 Implement `cuber/cli.py`: `add-card` command with `<short_id>` positional arg and `[names...]` variadic positional; `--from-file <path>` option (reads one name per line); `--stdin` flag (reads from stdin, newline-separated); `--maybeboard` flag; `--force` flag (allows adding duplicates)
- [x] 2.3 Write `cuber/cli.py` `add-card`: validate short_id resolves to an existing cube folder; auto-detect cube slug from `meta.json`; print added cards list and instructions: "Run `cuber enrich <id>` to hydrate new cards."

## 3. status Command

- [x] 3.1 Implement `cube_manager.py`: `cube_status(short_id)` — loads `remote/mainboard.csv` and `mainboard.csv`; computes set diff by card name; returns `{ added: [], removed: [], tag_changed: [], unchanged_count: int }`
- [x] 3.2 Implement `cube_manager.py`: tag_changed detection — compare `tags` column between remote and working CSV for cards present in both; list cards where tags differ
- [x] 3.3 Implement `cuber/cli.py`: `status` command — calls `cube_status()`; prints formatted diff table; shows "Export ready: No (run `cuber export` first)" if any changes exist; "Nothing to export" if clean

## 4. Export Redesign

- [x] 4.1 Implement `cube_manager.py`: `assemble_export(short_id)` — reads `meta.json` + `mainboard.csv` + `tagged.csv`; merges tags into mainboard rows; writes `exports/import-ready.csv` in CubeCobra 19-column format
- [x] 4.2 Implement `cuber/cli.py`: `export` command — calls `assemble_export()`; prints path to `exports/import-ready.csv` and import instructions: "Upload to CubeCobra: cube page → List → Export → Replace with CSV Import"
- [x] 4.3 Ensure `exports/import-ready.csv` column order exactly matches CubeCobra's expected format (Name, CMC, Type, Color, Set, Collector Number, Rarity, Color Category, Status, Finish, image_small, image_normal, Tags, Notes, Maybeboard, scryfall_id, oracle_id, cmc_override, type_override)

## 5. Enrich — Partial Row Handling

- [x] 5.1 Modify `cuber/scryfall.py`: `enrich_cube()` — detect stub rows (cards with empty `oracle_text` in enriched.json OR cards in mainboard.csv not yet in enriched.json); add them to the lookup batch; log count of stubs hydrated
- [x] 5.2 Modify `cuber/cube.py`: `load_raw_csv()` handles rows with only `name` set (all other columns empty/missing); creates a minimal Card object with `name` and `board="mainboard"`; sets `is_stub=True` flag

## 6. Fetch Redesign — CLI Wiring

- [x] 6.1 Modify `cuber/cli.py`: `fetch` command now calls `cube_manager.fetch_and_disassemble()` instead of `cubecobra.fetch_cube()`; prints folder path as `cubes/{slug}/`
- [x] 6.2 Keep `cuber/cubecobra.py` as the HTTP layer (fetch_json, fetch_csv, curl fallback); `cube_manager.py` is the orchestrator that calls it and disassembles the result
- [x] 6.3 Modify `cuber/cli.py`: `list` command reads `meta.json` from all `cubes/*/` subdirs (not just the old `{short-id}/` pattern); displays slug + title + short-id + card-count + fetched-at

## 7. commander_finder.py

- [x] 7.1 Implement `cuber/commander_finder.py`: `is_commander_eligible(card)` — checks `type_line` for "Legendary Creature"; checks `oracle_text` for "can be your commander"; returns `{ eligible: bool, reason: str }`
- [x] 7.2 Implement `commander_finder.py`: partner detection on `oracle_text` — `is_partner(oracle)`: matches "Partner" standalone, "Friends forever", "Doctor's companion"; `partner_with_target(oracle)`: extracts named partner from "Partner with X"; `has_background(oracle)`: detects "Choose a Background"
- [x] 7.3 Implement `commander_finder.py`: `find_commanders(short_id, color_identity=None)` — loads enriched.json; filters by `is_commander_eligible`; optionally filters by color identity subset; returns list of `{ name, color_identity, cmc, type_line, oracle_text, is_partner, partner_with, has_background }` sorted by name
- [x] 7.4 Implement `commander_finder.py`: `format_commanders_table(candidates)` — ASCII table with columns: Name | CI | CMC | Type | Partner flags

## 8. deck_audit.py

- [x] 8.1 Implement `cuber/deck_audit.py`: `pip_demand(cards)` — count colored pips (W/U/B/R/G) across all card `mana_cost` strings; return `{color: count}`
- [x] 8.2 Implement `deck_audit.py`: `land_color_production(lands)` — parse lands from enriched data; infer color production from `oracle_text` ("Add {W}", "Add one mana of any color"), `type_line` (basic land types), and color identity; return `{color: count}`
- [x] 8.3 Implement `deck_audit.py`: `burgess_formula(color_count, commander_cmc, deck_size)` and `karsten_adjustment(ramp_count, deck_size)` — return recommended land count
- [x] 8.4 Implement `deck_audit.py`: `constructed_land_target(ramp_count, avg_cmc, deck_size)` — baseline 24 for 60-card, scaled; adjust for ramp and curve; clamp to [14,18] for 40-card, [20,27] for 60-card
- [x] 8.5 Implement `deck_audit.py`: `color_balance(pip_demand, land_production, total_lands)` — compute pip% vs production% per color; flag gaps > 10pp as WARN, > 15pp as FAIL
- [x] 8.6 Implement `deck_audit.py`: `mana_audit(deck_cards, format, commander_cards=None)` — orchestrate all checks; return `{ land_count, recommended_land_count, land_count_status, ramp_count, avg_cmc, pip_demand, land_color_production, color_balance_status, color_balance_flags, overall_status }`
- [x] 8.7 Implement `deck_audit.py`: `format_audit_report(audit)` — human-readable text output with PASS/WARN/FAIL per section; one-line summary header

## 9. cube_search.py

- [x] 9.1 Implement `cuber/cube_search.py`: `load_merged_pool(short_id)` — loads enriched.json; loads tagged.csv; merges `functional_tags` list onto each card object by name; returns list of merged card dicts
- [x] 9.2 Implement `cube_search.py`: `search_pool(pool, *, color_identity=None, oracle_pattern=None, card_type=None, cmc_min=None, cmc_max=None, tags=None, rarity=None, board="mainboard")` — applies all filters; returns filtered list
- [x] 9.3 Implement `cube_search.py`: `format_search_results(cards, limit=25)` — compact table: Name | CI | CMC | Rarity | Tags | Oracle excerpt (60 chars)

## 10. Deck Builder Skill Rewrite

- [x] 10.1 Rewrite `skills/build-deck.md`: Phase 1 — Interview (format selection: 40-card/60-card/Commander-60/Commander-100; cube selection; strategy; colors; power level; restrictions; sideboard size preference)
- [x] 10.2 Rewrite `skills/build-deck.md`: Phase 2 — Deck Identity (load merged pool via cube_search; tabulate tag density by color; classify archetypes as Strong/Supported/Sparse; propose deck identity sentence; confirm with user)
- [x] 10.3 Rewrite `skills/build-deck.md`: Phase 3 — Commander Selection (if Commander format: call commander_finder; present table; user picks 1 or 2 for partners; derive color constraint from commander color identity)
- [x] 10.4 Rewrite `skills/build-deck.md`: Phase 4 — Deck Build (use cube_search to populate slots; identity-anchored picks; restrictions enforced per pick; verify every card in enriched.json before including)
- [x] 10.5 Rewrite `skills/build-deck.md`: Phase 5 — Mana Audit Gate (run deck_audit; if FAIL on land count or color balance, adjust deck before proceeding to self-grill; report adjustments made)
- [x] 10.6 Rewrite `skills/build-deck.md`: Phase 6 — Sideboard (format-aware default sizes; fill with hate cards and flex slots from cube pool; Challenger evaluates sideboard cohesion)
- [x] 10.7 Rewrite `skills/build-deck.md`: Phase 7 — Pre-Grill Check (cube membership for all cards; restrictions compliance; mana audit gate passed)
- [x] 10.8 Rewrite `skills/build-deck.md`: Phase 8 — Self-Grill (Proposer defends: identity fit, oracle text, restrictions, mana audit; Challenger attacks: cube membership, oracle, restrictions, identity violations, cut alternatives, sideboard relevance, mana audit re-run)
- [x] 10.9 Rewrite `skills/build-deck.md`: Phase 9 — Present Final Deck (table: Card | Board | Role | Rarity | Oracle Excerpt; mana audit summary; restrictions compliance checklist; ask to save)
- [x] 10.10 Rewrite `skills/build-deck.md`: Phase 10 — Save (write `cubes/<id>/decks/<name>.json`; write `cubes/<id>/decks/<name>.csv` with schema from D12; confirm paths)
- [x] 10.11 Write `skills/build-deck.md`: Tool Selection Table (maps each phase task to the right tool: cube_search, commander_finder, deck_audit, enriched.json read, tagged.csv read, Write tool)

## 11. Documentation

- [x] 11.1 Update `README.md`: reflect v2 folder structure (title-slug, remote/, exports/); update Quick Start; update CLI command reference table (add add-card, status; update fetch, export descriptions); update file inventory section
- [x] 11.2 Update `README.md`: update Skills section — /build-deck description reflects formats, deck identity, commander, restrictions; add note about deck.csv output
- [x] 11.3 Update `README.md`: add "How Export Works" section explaining the manual import flow (no push API) with step-by-step instructions
- [x] 11.4 Write `.context-for-design-ai.md`: comprehensive context file for dashboard design AI covering all data schemas, file layouts, commands, skills, and dashboard feature ideas with component-level suggestions

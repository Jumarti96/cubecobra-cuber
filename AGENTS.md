# Agent Context: Cubecobra Cuber

## Project Overview

Local Python toolkit for managing Magic: The Gathering cubes on CubeCobra. Core workflow: fetch cube locally, edit via CLI, enrich with Scryfall metadata, export as CSV for re-import.

## Tech Stack

- Python 3.9+, Typer CLI framework
- No external database — pure CSV + JSON files under `cubes/<slug>/`
- Scryfall API for card verification and enrichment
- OpenAI-compatible LLM endpoints for AI features (tag, analyze, build-deck, suggest, set-cube)

## Architecture

```
cuber/
  cli.py          — all CLI commands (Typer)
  cube_manager.py — CSV/JSON read-write primitives (add, remove, scale, dedup, etc.)
  cubecobra.py    — CubeCobra API client
  scryfall.py     — Scryfall API client
  tagger.py       — AI functional tagger
  deck_checks.py  — deterministic structural gates (curve, assembly, goldfish, coverage)
  deck_audit.py   — mana audit
  dossier.py      — cube dossier builder
  exporter.py     — deck/cube file writers
  orchestrator.py — build-deck run state machine + gates (see below)
```

## Agent Workflows (any CLI)

The workflows live in `skills/` as plain markdown — `skills/<name>.md` or
`skills/<name>/SKILL.md` plus a `references/` directory the workflow reads at
point of use. They are not Claude-specific; any agent CLI can follow them.
`build-deck` is the largest: read `skills/build-deck/SKILL.md` first.

Claude Code users run `python agent_env/install_claude_env.py` to install them
as slash commands. Everything under `agent_env/` is agent-environment setup;
nothing else in the repo depends on it.

## Build-Deck Gates — Do Not Work Around

`cuber/orchestrator.py` tracks a deck build as an explicit state machine, one
directory per run under `runs/<run_id>/`, one JSON artifact per phase.

- `python -m cuber.orchestrator init --cube <id>` starts a tracked run
- `python -m cuber.orchestrator resume [<run_id>]` shows what passed, what
  failed, and where to restart
- `python -m cuber.orchestrator export [<run_id>] --manifest F` is the **only**
  sanctioned way to write a deck; it re-checks every gate first

Two phases (`phase_05b_sketch_judge`, `phase_09_grill`) require **two
independent agents** — agents that did not see each other's output. How you
dispatch them is up to your environment; record it in `dispatch_method`. These
phases cannot be recorded as `inline`, and a deck cannot be exported until they
pass.

If a dispatch fails for any reason, run `orchestrator fail <run_id> <phase>
--error "..."` and stop. Do not substitute an inline check and do not
hand-write a deck file to get around a refused gate.

Each cube lives under `cubes/<slug>/`:
- `mainboard.csv` — working card list
- `maybeboard.csv` — working maybeboard
- `enriched.json` — Scryfall metadata cache
- `tagged.csv` — AI functional tags
- `remote/` — pristine snapshot from last fetch (never edit)
- `decks/`, `exports/` — generated artifacts

## Ops REPL Grammar (Important)

The `cuber ops` command opens an interactive REPL for batch edits. The tokenizer is **position-free** — operators can appear anywhere in the token stream.

### Operator Classes

- **Action-class** (highest priority): `+`, `-`, `=`
- **Scale-class**: `*`, `/`

If both action and scale operators appear in a statement, action-class wins.

### Grammar Rules

```
STATEMENT ::=
  | ( '+' | '-' ) CARD_EXPR { CARD_EXPR }
  | NAME '=' NUMBER
  | ( '*' | '/' ) [FACTOR] CARD { CARD }

CARD_EXPR ::=
  | NAME
  | NAME '*' NUMBER          -- quantity modifier for + and -
```

### Examples

| Input | Meaning |
|-------|---------|
| `+ "Bolt" * 3 "Serra Angel" * 2` | Add 3 Bolts, 2 Angels |
| `+ "Bolt" + "Serra Angel"` | Add 1 Bolt, 1 Angel (redundant `+` as separator) |
| `- "Bolt" * 2` | Remove 2 copies of Bolt |
| `- "Bolt"` | Remove 1 copy of Bolt |
| `= "Bolt" 4` | Set Bolt to exactly 4 copies |
| `"Bolt" = 4` | Set Bolt to exactly 4 copies (position-free) |
| `* 2 "Bolt"` | Multiply Bolt's copies by 2 |
| `"Bolt" * 2` | Multiply Bolt's copies by 2 |
| `* 0 "Bolt"` | Remove all copies of Bolt |

### Net Count State

The REPL maintains an in-memory `net_counts` dict (disk counts + staged ops). This enables:
- Natural cancel-out: `+ "Bolt"` then `- "Bolt"` → net zero
- `-` validation against staged adds (not just disk)
- `=` delta computation: `target - net_counts[name]`

### Control Commands

- `list` — show staged ops
- `undo [N]` — remove staged op [N]
- `reset` — clear all staged ops
- `done` — review and apply
- `quit` — exit without applying

## Breaking Change: remove-card Default

As of the `ops-repl-improvements` change:
- `cuber remove-card "Bolt"` removes **1 copy** (was: all copies)
- `cuber remove-card "Bolt" --all` removes all copies
- Same for `cuber rm "Bolt"` and `cuber rm "Bolt" --all`
- `remove_cards()` in `cube_manager.py` defaults to `count=1` (was `count=None`)
- Passing `count=None` to `remove_cards()` still means "remove all copies"

## Key Conventions

- **Never edit `remote/` files** — they are the last known CubeCobra state
- `cuber status` diffs working files against `remote/`
- `cuber export` assembles `exports/import-ready.csv` from working files
- Card names with spaces must be quoted in shell / REPL
- All AI features read **oracle text only** (never from training data)
- Self-grill gate: two AI agents debate before presenting recommendations

## Common Patterns

```bash
# Fetch and enrich
cuber fetch obc
cuber enrich obc

# Quick edits
cuber + "Lightning Bolt" "Brainstorm"
cuber rm "Dark Ritual"
cuber swap obc "Dark Ritual" "Cabal Ritual"

# Batch editing
cuber ops
# + "Bolt" * 3
# - "Serra Angel"
# = "Island" 10
# done

# Export when ready
cuber export obc
# Upload cubes/<slug>/exports/import-ready.csv to CubeCobra
```

---

## Skills — Canonical Path

**Root `skills/` is the source of truth.** This folder contains the canonical `.md` skill files that are shared with users and installed into their local environment.

**`.claude/skills/` is a local working copy** for the `skill` tool to load from. It is `.gitignore`d and must be regenerated from `skills/` when skills change.

### Setup for agents

When the `skill` tool needs a skill that lives in `skills/`:

1. Check `.claude/skills/` first (the tool loads from there).
2. If `.claude/skills/` is missing or stale, copy from `skills/`:
   ```bash
   # Windows PowerShell
   Copy-Item -Recurse "skills\*" ".claude\skills\"
   ```
3. After editing a skill via the `skill` tool, **sync changes back to `skills/`** so they are committed and shared with users.

**Never commit `.claude/skills/`** — only commit changes to root `skills/`.

# scripts/

Setup and enforcement scripts for the Claude Code environment in this repo.

## Quick start (new clone)

```bash
python scripts/install_claude_env.py
```

Then **restart Claude Code**. Skills and hooks are read at startup; nothing you install here takes effect in a session that is already running.

To verify an existing setup without changing anything:

```bash
python scripts/install_claude_env.py --check    # exit 1 if anything is broken
```

## What's here

| Script | Purpose |
|---|---|
| `install_claude_env.py` | **Start here.** Installs skills, verifies settings + the export-gate hook, smoke-tests the gate. Safe to re-run; safe in CI. |
| `install_skills.py` | Syncs `skills/` → `.claude/skills/`. Called by the above; run it directly if you only edited a skill. |
| `gate_export.py` | PreToolUse hook enforcing the build-deck export gate. Not run by hand — Claude Code invokes it. |

## How the Claude environment is assembled

Three pieces, each with a different scope:

| Piece | Where | Shared with clones? |
|---|---|---|
| Skills | `skills/` → installed to `.claude/skills/` | Source is committed; the installed copy is gitignored |
| Project settings + hooks | `.claude/settings.json` | **Yes** — committed |
| Personal settings | `.claude/settings.local.json` | No — gitignored, merges on top |

**`skills/` is the source of truth.** Edit a skill there and re-run `install_skills.py`. Never edit `.claude/skills/` directly — it is overwritten on every install.

Put machine-specific things (permission allowlists, absolute paths, personal hooks) in `settings.local.json`. If you define the same hook in both files it runs **twice** per tool call; `install_claude_env.py --check` warns when it detects this.

## The build-deck export gate

`gate_export.py` is wired as a `PreToolUse` hook on `Write|Edit|Bash|PowerShell` in `.claude/settings.json`. It blocks any write into `cubes/<id>/decks/` unless the current orchestrator run has a valid `phase_09_grill.json` — so a deck cannot be saved when the Phase 9 grill was skipped, failed, or run inline instead of as independent subagents.

Full command reference: `skills/build-deck/references/orchestrator.md`.

The hook resolves its interpreter at call time and `exec`s it:

```
sh -c 'PY=$(command -v python3 || command -v python); exec "$PY" "$CLAUDE_PROJECT_DIR/scripts/gate_export.py"'
```

`exec` matters — the hook signals a block with **exit 2**, and any wrapper that swallows or re-runs on non-zero would silently disable the gate.

### If the gate blocks you unexpectedly

It is deliberately hard to bypass. In order of preference:

1. Finish the run properly — `python -m cuber.orchestrator resume <run_id>` names the phase to fix.
2. If a subagent dispatch genuinely failed, record it: `python -m cuber.orchestrator fail <run_id> <phase> --error "..."`, then report it rather than working around it.
3. Only if the hook itself is misbehaving, comment it out of `.claude/settings.json` — and treat that as a bug to fix, not a workflow.

Writing a deck by hand to dodge the gate defeats the entire mechanism. If you find yourself wanting to, the gate is telling you something true.

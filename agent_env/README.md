# agent_env/

Setup and enforcement scripts for agent environments.

**Everything AI-environment-related lives here.** The one exception is
`.claude/settings.json`, whose location is fixed by the tool that reads it;
the tooling that maintains it is here.

Nothing in this folder is required to run the workflow. Another CLI needs only
`skills/` (plain markdown) and `cuber/orchestrator.py`.

## Portability

The build-deck gates do **not** depend on Claude Code. `cuber/orchestrator.py`
is plain Python, and `orchestrator export` is the only sanctioned deck writer —
it re-checks every gate in the same function that writes the files. Another CLI
just needs the skills in `skills/` (plain markdown) and that command.

The `gate_export.py` hook below is a Claude-Code-only **backstop** that catches
a deck written by hand instead of through `export`. It is optional; nothing
breaks without it.

## Quick start (new clone)

```bash
python agent_env/install_claude_env.py
```

Then **restart Claude Code**. Skills and hooks are read at startup; nothing you install here takes effect in a session that is already running.

To verify an existing setup without changing anything:

```bash
python agent_env/install_claude_env.py --check    # exit 1 if anything is broken
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

`gate_export.py` is wired as a `PreToolUse` hook on `Write|Edit` in `.claude/settings.json`. It blocks a direct write into `cubes/<id>/decks/` unless the current orchestrator run has a valid `phase_09_grill.json`.

It only matches path-based tools. An earlier version also scanned shell commands for a deck path plus a write verb; that was dropped after it false-positived on every command that merely *named* the path — `grep`, `git commit -m "..."`, even the test harness. The architectural fix (sole-writer `export`) covers that case properly.

Full command reference: `skills/build-deck/references/orchestrator.md`.

The hook resolves its interpreter at call time and `exec`s it:

```sh
S="$CLAUDE_PROJECT_DIR/agent_env/gate_export.py"
[ -f "$S" ] || exit 0                                    # missing script must not block
PY=$(command -v python3 || command -v python) || exit 0   # no python must not block
exec "$PY" "$S"
```

Two details, both learned the hard way:

- **`exec`** — the hook signals a block with **exit 2**, so any wrapper that swallows or re-runs on non-zero silently disables the gate. A `python3 ... || python ...` fallback would have turned every block into an allow.
- **The `[ -f ]` guard** — Python exits `2` on "can't open file", which is *also* the block code. Without the guard, renaming or moving the script makes the hook block every `Write`/`Edit`/`Bash` call in the session, locking you out of your own workspace with no way to fix it. A guard that bricks the workspace when it breaks is worse than no guard.

### If the gate blocks you unexpectedly

It is deliberately hard to bypass. In order of preference:

1. Finish the run properly — `python -m cuber.orchestrator resume <run_id>` names the phase to fix.
2. If a subagent dispatch genuinely failed, record it: `python -m cuber.orchestrator fail <run_id> <phase> --error "..."`, then report it rather than working around it.
3. Only if the hook itself is misbehaving, comment it out of `.claude/settings.json` — and treat that as a bug to fix, not a workflow.

Writing a deck by hand to dodge the gate defeats the entire mechanism. If you find yourself wanting to, the gate is telling you something true.

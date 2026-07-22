# build-deck reference — the run orchestrator

Read at Phase 0 start. Command reference for `cuber/orchestrator.py`, the state machine that tracks a build. The binding rules (what you must do when a dispatch fails) are in SKILL.md.

## What it is, and what it is not

It is a **ledger and a gatekeeper**. It records what each phase did and refuses to let export happen when a gate did not pass.

It is **not a driver**. A Python process cannot dispatch subagents — the Agent tool lives in the harness, not in the script. You still do the phase work yourself; the orchestrator only decides whether what you did counts.

It **cannot prove** a report came from a real subagent — `mode` and `subagent_results` are self-reported. What it does is make evasion explicit: skipping the grill now requires writing a fabricated report to disk under a dispatch id, instead of silently omitting a step. When a dispatch dies, `fail` is the only path that does not require lying.

## Phase sequence

`phase_00_pool` → `phase_01_interview` → `phase_02_identity` → `phase_03_strategy` → `phase_05b_sketch_judge` → `phase_05c_preflight` → `phase_06_mana` → `phase_06b_structural` → `phase_09_grill` → `phase_10_export`

`phase_05b_sketch_judge` and `phase_09_grill` are **subagent phases**. Everything else records with `--mode inline`.

## Commands

| Command | Effect |
|---|---|
| `init --cube <id>` | Creates `runs/<run_id>/`, points `runs/CURRENT` at it, prints the run id |
| `record <run_id> <phase> --mode <inline\|subagent> [--payload-file F] [--subagents-file F] [--retry]` | Validates, then writes the artifact. Invalid input raises **before** anything is written |
| `fail <run_id> <phase> --error "..."` | Writes `phase_XX.FAILED.json`, no passing artifact, **exits 1** |
| `status` / `resume [<run_id>]` | Per-phase PASS/FAILED/INVALID/pending + reasons + the resume point. Exits non-zero while incomplete |
| `gate <run_id> <phase>` | Exit 0 iff that phase is complete and valid |
| `gate-export [<run_id>]` | Exit 0 iff every phase before export is complete |

`<run_id>` is optional for `status` / `resume` / `gate-export` — it falls back to `runs/CURRENT`.

## The artifact envelope

```json
{
  "phase": "phase_09_grill",
  "run_id": "run-...",
  "started_at": "2026-07-22T10:00:00.000000Z",
  "ended_at":   "2026-07-22T10:12:00.000000Z",
  "mode": "subagent",
  "subagent_results": [
    {"role": "proposer",   "dispatch_id": "...", "report": "=== PROPOSER REPORT — BEGIN ===\n...",
     "returned_at": "..."},
    {"role": "challenger", "dispatch_id": "...", "report": "=== CHALLENGER REPORT — BEGIN ===\n...",
     "returned_at": "..."}
  ],
  "payload": { }
}
```

Use the phase's real elapsed times — `started_at == ended_at` on a phase that took ten minutes of subagent work is a tell.

## What the subagent-phase schema enforces

A `record` of `phase_05b_sketch_judge` or `phase_09_grill` is **rejected** unless all of:

- `mode == "subagent"` — there is no flag that relaxes this
- at least **2** entries in `subagent_results`
- every entry has a non-empty `role` and a `dispatch_id`, and **all dispatch ids are distinct** (two results from one dispatch are not two independent agents)
- every `report` contains both the `BEGIN ===` and `END ===` markers
- every `report` is ≥ 200 characters
- the roles cover the phase: `sketcher` + `judge` for 5B, `proposer` + `challenger` for 9 (substring match, so `sketcher-lens-2` counts)

## The export hook

`scripts/gate_export.py` runs as a PreToolUse hook on `Write|Edit|Bash|PowerShell`. It denies (exit 2) any call whose target matches `cubes/<id>/decks/` unless the current run passes `gate-export`.

- **Write / Edit**: matched on the exact `file_path`. This is the path an actual save takes, and the match is precise.
- **Bash / PowerShell**: matched only when the command *both* names the deck directory **and** carries a write verb (`>`, `>>`, `cp`, `mv`, `tee`, `touch`, `Set-Content`, `open(..., 'w')`, the repo's `write_mwdeck` / `write_deck_analysis_md`, …). Merely naming the path — `grep`, `ls`, `cat`, a commit message quoting it — is allowed. This is a **heuristic net**, not a proof: an exotic write verb outside that list would slip through. It exists to close the obvious shell redirect, not to be airtight.

It fails **open** on a malformed event (a crashing hook would wedge every tool call in the session) and **closed** on the thing it guards (an unverified deck write via Write/Edit is always denied).

## Failure semantics

```
python -m cuber.orchestrator fail <run_id> phase_09_grill \
  --error "Challenger dispatch failed: API session limit reached"
```

Then stop and tell the user. A `FAILED` marker blocks the phase until an explicit `--retry`, which **archives** the failure to `phase_XX.FAILED.<timestamp>.json` rather than deleting it — the run directory keeps a permanent record that the gate failed once and what was done about it.

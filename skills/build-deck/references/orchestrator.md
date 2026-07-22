# build-deck reference — the run orchestrator

Read at Phase 0 start. Command reference for `cuber/orchestrator.py`, the state machine that tracks a build. The binding rules (what you must do when a dispatch fails) are in SKILL.md.

## What it is

A **ledger, a gatekeeper, and the deck writer.** It records what each phase did, refuses to continue when a gate did not pass, and performs the export itself.

That last part is what makes the gate real rather than advisory. `orchestrator export` checks every gate and writes the deck files **in the same function**. There is no sanctioned path that writes a deck without passing the gate, so nothing has to intercept you for the gate to hold.

It is **not a driver**. It does not dispatch agents for you (a Python process cannot reach into your harness's agent tool). You still do the phase work; the orchestrator decides whether what you did counts.

Everything here is plain Python with no editor or harness dependency. The skill is fully enforced by these commands alone — under Claude Code, another agent CLI, or a bare terminal.

It **cannot prove** a report came from a real independent agent — `mode` and the reports are self-reported. What it does is make evasion explicit: faking a grill means writing a fabricated report to disk, instead of silently omitting a step.

## Phase sequence

`phase_00_pool` → `phase_01_interview` → `phase_02_identity` → `phase_03_strategy` → `phase_05b_sketch_judge` → `phase_05c_preflight` → `phase_06_mana` → `phase_06b_structural` → `phase_09_grill` → `phase_10_export`

`phase_05b_sketch_judge` and `phase_09_grill` are **independent-agent phases**. Everything else records with `--mode inline`.

## Commands

| Command | Effect |
|---|---|
| `init --cube <id>` | Creates `runs/<run_id>/`, points `runs/CURRENT` at it, prints the run id |
| `record <run_id> <phase> --mode <inline\|independent> [--payload-file F] [--agents-file F] [--retry]` | Validates, then writes the artifact. Invalid input raises **before** anything is written |
| `fail <run_id> <phase> --error "..."` | Writes `phase_XX.FAILED.json`, no passing artifact, **exits 1** |
| `export [<run_id>] --manifest F` | **The only sanctioned deck write.** Checks every gate, writes the four files, records phase 10 |
| `status` / `resume [<run_id>]` | Per-phase PASS/FAILED/INVALID/pending + reasons + the resume point. Exits non-zero while incomplete |
| `gate <run_id> <phase>` | Exit 0 iff that phase is complete and valid |
| `gate-export [<run_id>]` | Exit 0 iff every phase before export is complete |

`<run_id>` is optional for `status` / `resume` / `gate-export` / `export` — it falls back to `runs/CURRENT`.

## Independence is a property, not a mechanism

Phases 5B and 9 require **two agents that did not see each other's output**. They do *not* require any particular harness feature. Record how you achieved it in each result's optional `dispatch_method`:

`claude-subagent` · `separate-process` · `separate-session` · `api-call` · `unspecified`

This is recorded, not gated — so the skill works under Claude Code, another agent CLI, or a plain terminal. `mode: "subagent"` is still accepted and normalised to `independent`, and the old `subagent_results` key is still read.

## The artifact envelope

```json
{
  "phase": "phase_09_grill",
  "run_id": "run-...",
  "started_at": "2026-07-22T10:00:00.000000Z",
  "ended_at":   "2026-07-22T10:12:00.000000Z",
  "mode": "independent",
  "agent_results": [
    {"role": "proposer",   "dispatch_id": "...", "dispatch_method": "claude-subagent",
     "report": "=== PROPOSER REPORT — BEGIN ===\n...", "returned_at": "..."},
    {"role": "challenger", "dispatch_id": "...", "dispatch_method": "claude-subagent",
     "report": "=== CHALLENGER REPORT — BEGIN ===\n...", "returned_at": "..."}
  ],
  "payload": { }
}
```

Use the phase's real elapsed times — `started_at == ended_at` on a phase that took ten minutes of agent work is a tell.

## What the independent-phase schema enforces

A `record` of `phase_05b_sketch_judge` or `phase_09_grill` is **rejected** unless all of:

- `mode == "independent"` — there is no flag that relaxes this
- at least **2** entries in `agent_results`
- every entry has a non-empty `role` and a `dispatch_id`, and **all dispatch ids are distinct** (two results from one dispatch are not two independent agents)
- every `report` contains both the `BEGIN ===` and `END ===` markers
- every `report` is ≥ 200 characters
- the roles cover the phase: `sketcher` + `judge` for 5B, `proposer` + `challenger` for 9 (substring match, so `sketcher-lens-2` counts)

## Exporting

```bash
python -m cuber.orchestrator export <run_id> --manifest _workspace/<tok>/manifest.json
```

```json
{
  "cube_id": "ecl",
  "deck_name": "UR Spells",
  "files": {
    "deck.json":   { },
    "deck.tsv":    "...",
    "deck.mwDeck": "...",
    "analysis.md": "---\n...\n"
  }
}
```

Only the four known filenames are accepted; anything else is refused, so the manifest cannot be used to write outside the deck folder. Every gate is checked **before** the first byte is written — a refusal leaves no partial output.

## Failure semantics

```
python -m cuber.orchestrator fail <run_id> phase_09_grill \
  --error "Challenger dispatch failed: API session limit reached"
```

Then stop and tell the user. A `FAILED` marker blocks the phase until an explicit `--retry`, which **archives** the failure to `phase_XX.FAILED.<timestamp>.json` rather than deleting it — the run directory keeps a permanent record that the gate failed once and what was done about it.

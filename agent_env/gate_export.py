#!/usr/bin/env python3
"""PreToolUse hook: block deck exports that have not passed the Phase 9 grill.

This is the part of the system that does not depend on the model's cooperation.
Claude Code runs it before every Write/Edit/Bash call; it denies (exit 2) any
call that would land a file in ``cubes/<id>/decks/`` unless the current run's
``phase_09_grill.json`` exists and validates.

Wire it up in .claude/settings.local.json:

    "PreToolUse": [{
      "matcher": "Write|Edit|Bash",
      "hooks": [{"type": "command",
                 "command": "python \\"<repo>/agent_env/gate_export.py\\""}]
    }]

Fail-open on malformed input: a hook that crashes on an unexpected event shape
would wedge every tool call in the session. It fails CLOSED on the thing it
actually guards — an unverified deck write is always denied.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cuber import orchestrator as orch  # noqa: E402

#: Matches the build-deck output location: cubes/<cube-id>/decks/<deck-name>/...
DECK_OUTPUT_RE = re.compile(r"cubes/[^/]+/decks/", re.IGNORECASE)

PATH_KEYS = ("file_path", "notebook_path", "path")

def is_deck_output_path(path: str) -> bool:
    if not path:
        return False
    return bool(DECK_OUTPUT_RE.search(str(path).replace("\\", "/")))


def _targets(event: dict):
    """Every string in the event that could name a write target.

    Path-based tools only. An earlier version also scanned shell commands for
    a deck path plus a write verb; it was dropped because it false-positived on
    every command that merely NAMED the path (`grep`, `git commit -m "..."`),
    and because the real fix is architectural: `orchestrator export` is the only
    sanctioned writer, so there is no unguarded shell path worth policing. This
    hook is now a thin backstop against a stray direct write, not the mechanism.
    """
    ti = event.get("tool_input") or {}
    if not isinstance(ti, dict):
        return []
    return [str(ti[k]) for k in PATH_KEYS if ti.get(k)]


def decide(event: dict, root=None):
    """Return ``(allow: bool, reason: str)`` for a PreToolUse event."""
    if not isinstance(event, dict):
        return True, ""

    if not any(is_deck_output_path(t) for t in _targets(event)):
        return True, ""

    run_id = orch.current_run_id(root)
    if not run_id:
        return False, (
            "BLOCKED: deck export attempted with no active run "
            "(runs/CURRENT is missing). Start the build through the orchestrator "
            "so phase_09_grill.json can be verified."
        )

    try:
        orch.assert_export_allowed(root, run_id)
    except orch.GateError as e:
        return False, (
            f"BLOCKED: deck export is gated on the Phase 9 grill.\n"
            f"  run: {run_id}\n"
            f"  {e}\n"
            f"Re-dispatch the failed subagent, or report the skipped gate to the user. "
            f"Do NOT substitute an inline check and do NOT hand-write the artifact."
        )

    return True, ""


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        return 0  # never wedge the session on a malformed event

    try:
        allow, reason = decide(event, os.environ.get("CUBER_RUNS_ROOT"))
    except Exception as e:  # noqa: BLE001 - a hook crash must not block everything
        print(f"gate_export.py error (allowing): {e}", file=sys.stderr)
        return 0

    if allow:
        return 0
    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

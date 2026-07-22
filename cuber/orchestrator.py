"""Deterministic, resumable state machine for the build-deck pipeline.

WHAT THIS IS
------------
A ledger and a gatekeeper — not a driver. A Python process cannot dispatch
Claude Code subagents (the Agent tool lives in the harness, not in this
process), so the orchestrator does not *run* Phase 5B or Phase 9. It records
what happened and refuses to let the run proceed when a gate did not.

The contract:

  * every phase writes exactly one JSON artifact into ``runs/<run_id>/``
  * subagent phases (5B, 9) are only recordable with ``mode="subagent"`` and
    at least two subagent result payloads carrying the BEGIN/END markers
  * a failed dispatch writes ``phase_XX.FAILED.json`` and NEVER a passing
    artifact — there is no code path that substitutes an inline check
  * export is unreachable unless every prior phase is complete

WHAT IT CANNOT DO
-----------------
``mode`` and ``subagent_results`` are self-reported by the caller. This module
cannot prove a report came from a real subagent. What it does is make the
evasion *explicit and greppable*: skipping the grill now requires writing a
fabricated report to disk under a dispatch id, rather than silently omitting a
step. The honest path when a dispatch dies is ``fail_phase`` — and that is the
only path that does not require lying.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# ── phase sequence ────────────────────────────────────────────────────────────

PHASE_POOL = "phase_00_pool"
PHASE_INTERVIEW = "phase_01_interview"
PHASE_IDENTITY = "phase_02_identity"
PHASE_STRATEGY = "phase_03_strategy"
PHASE_SKETCH_JUDGE = "phase_05b_sketch_judge"
PHASE_PREFLIGHT = "phase_05c_preflight"
PHASE_MANA = "phase_06_mana"
PHASE_STRUCTURAL = "phase_06b_structural"
PHASE_GRILL = "phase_09_grill"
PHASE_EXPORT = "phase_10_export"

#: Ordered. ``first_incomplete`` walks this list; export is always last.
PHASES: Tuple[str, ...] = (
    PHASE_POOL,
    PHASE_INTERVIEW,
    PHASE_IDENTITY,
    PHASE_STRATEGY,
    PHASE_SKETCH_JUDGE,
    PHASE_PREFLIGHT,
    PHASE_MANA,
    PHASE_STRUCTURAL,
    PHASE_GRILL,
    PHASE_EXPORT,
)

PHASE_LABELS = {
    PHASE_POOL: "Card Pool Definition",
    PHASE_INTERVIEW: "Interview",
    PHASE_IDENTITY: "Deck Identity",
    PHASE_STRATEGY: "Strategy Selection",
    PHASE_SKETCH_JUDGE: "Sketch -> Judge -> Lock",
    PHASE_PREFLIGHT: "Pre-flight Validation",
    PHASE_MANA: "Mana Audit Gate",
    PHASE_STRUCTURAL: "Structural Gate",
    PHASE_GRILL: "Self-Grill",
    PHASE_EXPORT: "Export",
}

#: Phases that MUST be carried out by independent dispatched subagents.
SUBAGENT_PHASES = frozenset({PHASE_SKETCH_JUDGE, PHASE_GRILL})

#: Role keywords that must each be present among a subagent phase's results.
#: Matched as substrings so "sketcher-lens-2" satisfies "sketch".
REQUIRED_ROLES: Dict[str, Tuple[str, ...]] = {
    PHASE_SKETCH_JUDGE: ("sketcher", "judge"),
    PHASE_GRILL: ("proposer", "challenger"),
}

MIN_SUBAGENTS = 2
MIN_REPORT_CHARS = 200
VALID_MODES = ("inline", "subagent")

STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"
STATUS_INVALID = "invalid"
STATUS_PENDING = "pending"


class GateError(Exception):
    """A gate refused. Never catch this to fall back to an inline check."""


# ── paths ─────────────────────────────────────────────────────────────────────

def default_root() -> Path:
    return Path(os.environ.get("CUBER_RUNS_ROOT") or Path.cwd())


def runs_root(root=None) -> Path:
    return Path(root if root is not None else default_root()) / "runs"


def run_dir(root, run_id: str) -> Path:
    return runs_root(root) / run_id


def artifact_path(root, run_id: str, phase: str) -> Path:
    return run_dir(root, run_id) / f"{phase}.json"


def failed_path(root, run_id: str, phase: str) -> Path:
    return run_dir(root, run_id) / f"{phase}.FAILED.json"


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ── run lifecycle ─────────────────────────────────────────────────────────────

def init_run(root=None, cube_id: str = "") -> str:
    """Create a fresh run directory and point ``runs/CURRENT`` at it."""
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    run_id = f"run-{stamp}-{uuid.uuid4().hex}"
    d = run_dir(root, run_id)
    d.mkdir(parents=True, exist_ok=False)   # collision must be loud, never reused
    (d / "run.json").write_text(json.dumps({
        "run_id": run_id, "cube_id": cube_id, "created_at": _now(),
        "phases": list(PHASES),
    }, indent=2), encoding="utf-8")
    set_current_run(root, run_id)
    return run_id


def set_current_run(root, run_id: str) -> None:
    rr = runs_root(root)
    rr.mkdir(parents=True, exist_ok=True)
    (rr / "CURRENT").write_text(run_id + "\n", encoding="utf-8")


def current_run_id(root=None) -> Optional[str]:
    p = runs_root(root) / "CURRENT"
    if not p.is_file():
        return None
    rid = p.read_text(encoding="utf-8").strip()
    return rid or None


# ── validation ────────────────────────────────────────────────────────────────

def _validate_subagent_results(phase: str, results: Sequence[dict]) -> None:
    if len(results) < MIN_SUBAGENTS:
        raise GateError(
            f"{phase}: requires at least {MIN_SUBAGENTS} dispatched subagent results, "
            f"got {len(results)}. A phase that mandates independent agents cannot be "
            f"satisfied by one agent or by an inline check."
        )

    seen_ids = set()
    for i, r in enumerate(results):
        if not isinstance(r, dict):
            raise GateError(f"{phase}: subagent result #{i} is not an object")

        role = str(r.get("role", "")).strip()
        if not role:
            raise GateError(f"{phase}: subagent result #{i} has no role")

        did = str(r.get("dispatch_id", "")).strip()
        if not did:
            raise GateError(f"{phase}: subagent result #{i} ({role}) has no dispatch_id")
        if did in seen_ids:
            raise GateError(
                f"{phase}: duplicate dispatch_id {did!r} — two results from one "
                f"dispatch are not two independent agents"
            )
        seen_ids.add(did)

        report = str(r.get("report", ""))
        if "BEGIN ===" not in report or "END ===" not in report:
            raise GateError(
                f"{phase}: subagent result #{i} ({role}) is missing the BEGIN/END "
                f"report marker required by the subagent protocol"
            )
        if len(report) < MIN_REPORT_CHARS:
            raise GateError(
                f"{phase}: subagent result #{i} ({role}) report is too short "
                f"({len(report)} < {MIN_REPORT_CHARS} chars) to be a real report"
            )

    roles_blob = " ".join(str(r.get("role", "")).lower() for r in results)
    missing = [kw for kw in REQUIRED_ROLES.get(phase, ()) if kw not in roles_blob]
    if missing:
        raise GateError(
            f"{phase}: missing required subagent role(s): {', '.join(missing)}. "
            f"Got roles: {roles_blob or '(none)'}"
        )


def validate_artifact(data, phase: str) -> None:
    """Raise ``GateError`` unless ``data`` is a valid artifact for ``phase``."""
    if not isinstance(data, dict):
        raise GateError(f"{phase}: artifact is not a JSON object")

    if data.get("phase") != phase:
        raise GateError(f"{phase}: artifact records phase {data.get('phase')!r}")

    for field in ("run_id", "started_at", "ended_at"):
        if not data.get(field):
            raise GateError(f"{phase}: artifact missing required field {field!r}")

    mode = data.get("mode")
    if mode not in VALID_MODES:
        raise GateError(f"{phase}: mode must be one of {VALID_MODES}, got {mode!r}")

    results = data.get("subagent_results")
    if not isinstance(results, list):
        raise GateError(f"{phase}: subagent_results must be a list")

    if phase in SUBAGENT_PHASES:
        if mode != "subagent":
            raise GateError(
                f"{phase}: mode must be 'subagent' (got {mode!r}). This phase requires "
                f"independent dispatched agents; running it inline does not satisfy it."
            )
        _validate_subagent_results(phase, results)


# ── recording ─────────────────────────────────────────────────────────────────

def record_phase(root, run_id: str, phase: str, mode: str,
                 payload=None, subagent_results=None,
                 started_at: str = None, ended_at: str = None,
                 retry: bool = False) -> Path:
    """Validate and write a passing artifact. Raises before writing on any fault."""
    if phase not in PHASES:
        raise GateError(f"unknown phase {phase!r}")

    d = run_dir(root, run_id)
    if not d.is_dir():
        raise GateError(f"run {run_id!r} does not exist — init it first")

    fp = failed_path(root, run_id, phase)
    if fp.exists() and not retry:
        raise GateError(
            f"{phase}: an unresolved {fp.name} is present. Recording a pass over a "
            f"failure requires an explicit retry (retry=True / --retry), which "
            f"archives the failure rather than erasing it."
        )

    now = _now()
    data = {
        "phase": phase,
        "phase_label": PHASE_LABELS.get(phase, phase),
        "run_id": run_id,
        "started_at": started_at or now,
        "ended_at": ended_at or now,
        "mode": mode,
        "subagent_results": list(subagent_results or []),
        "payload": payload if payload is not None else {},
        "recorded_at": now,
    }

    validate_artifact(data, phase)          # never write an invalid artifact

    if fp.exists():                          # retry: archive, don't delete
        fp.rename(d / f"{phase}.FAILED.{_dt.datetime.now(_dt.timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.json")

    out = artifact_path(root, run_id, phase)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def fail_phase(root, run_id: str, phase: str, error: str, detail=None) -> Path:
    """Record a dispatch/gate failure. No passing artifact is ever written."""
    if phase not in PHASES:
        raise GateError(f"unknown phase {phase!r}")

    d = run_dir(root, run_id)
    if not d.is_dir():
        raise GateError(f"run {run_id!r} does not exist — init it first")

    ok = artifact_path(root, run_id, phase)
    if ok.exists():
        ok.rename(d / f"{phase}.SUPERSEDED.{_dt.datetime.now(_dt.timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.json")

    out = failed_path(root, run_id, phase)
    out.write_text(json.dumps({
        "phase": phase,
        "phase_label": PHASE_LABELS.get(phase, phase),
        "run_id": run_id,
        "failed_at": _now(),
        "error": error,
        "detail": detail if detail is not None else {},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


# ── gates ─────────────────────────────────────────────────────────────────────

def assert_phase_complete(root, run_id: str, phase: str) -> dict:
    """Raise ``GateError`` unless the phase artifact exists and validates."""
    fp = failed_path(root, run_id, phase)
    if fp.exists():
        try:
            err = json.loads(fp.read_text(encoding="utf-8")).get("error", "(no error text)")
        except (ValueError, OSError):
            err = "(unreadable failure artifact)"
        raise GateError(f"{phase}: marked FAILED — {err}")

    p = artifact_path(root, run_id, phase)
    if not p.is_file():
        raise GateError(f"{phase}: no artifact at {p} — the phase did not run")

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise GateError(f"{phase}: artifact is unreadable / failed to parse: {e}")
    except OSError as e:
        raise GateError(f"{phase}: artifact is unreadable: {e}")

    validate_artifact(data, phase)
    return data


def assert_export_allowed(root, run_id: str) -> None:
    """Raise unless every phase before export is complete. Grill is named first."""
    assert_phase_complete(root, run_id, PHASE_GRILL)
    for phase in PHASES:
        if phase == PHASE_EXPORT:
            break
        assert_phase_complete(root, run_id, phase)


def phase_status(root, run_id: str, phase: str) -> str:
    if failed_path(root, run_id, phase).exists():
        return STATUS_FAILED
    if not artifact_path(root, run_id, phase).is_file():
        return STATUS_PENDING
    try:
        assert_phase_complete(root, run_id, phase)
    except GateError:
        return STATUS_INVALID
    return STATUS_COMPLETE


def run_status(root, run_id: str) -> Dict[str, str]:
    return {phase: phase_status(root, run_id, phase) for phase in PHASES}


def first_incomplete(root, run_id: str) -> Optional[str]:
    for phase in PHASES:
        if phase_status(root, run_id, phase) != STATUS_COMPLETE:
            return phase
    return None


def phase_error(root, run_id: str, phase: str) -> Optional[str]:
    fp = failed_path(root, run_id, phase)
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8")).get("error")
    except (ValueError, OSError):
        return "(unreadable failure artifact)"


# ── CLI ───────────────────────────────────────────────────────────────────────

_GLYPH = {
    STATUS_COMPLETE: "PASS",
    STATUS_FAILED: "FAILED",
    STATUS_INVALID: "INVALID",
    STATUS_PENDING: "pending",
}


def _print_status(root, run_id: str) -> Optional[str]:
    status = run_status(root, run_id)
    print(f"\nRUN {run_id}")
    print(f"{'phase':<26} {'status':<9} note")
    print("-" * 78)
    for phase in PHASES:
        st = status[phase]
        note = ""
        if st == STATUS_FAILED:
            note = phase_error(root, run_id, phase) or ""
        elif st == STATUS_INVALID:
            try:
                assert_phase_complete(root, run_id, phase)
            except GateError as e:
                note = str(e)
        print(f"{phase:<26} {_GLYPH[st]:<9} {note}")
    nxt = first_incomplete(root, run_id)
    print("-" * 78)
    if nxt is None:
        print("All phases complete. RESUME AT: (nothing — run is finished)")
    else:
        print(f"RESUME AT: {nxt}  ({PHASE_LABELS.get(nxt, nxt)})")
    return nxt


def _load_json_file(path):
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="orchestrator", description=__doc__)
    ap.add_argument("--root", default=None, help="repo root holding runs/")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("init"); p.add_argument("--cube", default="")
    p.add_argument("--root", default=None)

    for name in ("status", "resume"):
        p = sp.add_parser(name); p.add_argument("run_id", nargs="?")
        p.add_argument("--root", default=None)

    p = sp.add_parser("record")
    p.add_argument("run_id"); p.add_argument("phase")
    p.add_argument("--mode", required=True, choices=VALID_MODES)
    p.add_argument("--payload-file"); p.add_argument("--subagents-file")
    p.add_argument("--retry", action="store_true"); p.add_argument("--root", default=None)

    p = sp.add_parser("fail")
    p.add_argument("run_id"); p.add_argument("phase")
    p.add_argument("--error", required=True); p.add_argument("--root", default=None)

    p = sp.add_parser("gate")
    p.add_argument("run_id"); p.add_argument("phase"); p.add_argument("--root", default=None)

    p = sp.add_parser("gate-export")
    p.add_argument("run_id", nargs="?"); p.add_argument("--root", default=None)

    args = ap.parse_args(argv)
    root = args.root or default_root()

    run_id = getattr(args, "run_id", None)
    if run_id is None and args.cmd in ("status", "resume", "gate-export"):
        run_id = current_run_id(root)
        if not run_id:
            print("no active run (runs/CURRENT is missing)", file=sys.stderr)
            return 1

    try:
        if args.cmd == "init":
            print(init_run(root, cube_id=args.cube))
            return 0

        if args.cmd in ("status", "resume"):
            return 0 if _print_status(root, run_id) is None else 1

        if args.cmd == "record":
            path = record_phase(
                root, run_id, args.phase, mode=args.mode,
                payload=_load_json_file(args.payload_file),
                subagent_results=_load_json_file(args.subagents_file) or [],
                retry=args.retry,
            )
            print(f"recorded {path}")
            return 0

        if args.cmd == "fail":
            path = fail_phase(root, run_id, args.phase, error=args.error)
            print(f"FAILED artifact written: {path}", file=sys.stderr)
            print(f"{args.phase} did NOT pass. Do not substitute an inline check; "
                  f"re-dispatch the subagent or surface the failure to the user.",
                  file=sys.stderr)
            return 1

        if args.cmd == "gate":
            assert_phase_complete(root, run_id, args.phase)
            print(f"{args.phase}: OK")
            return 0

        if args.cmd == "gate-export":
            assert_export_allowed(root, run_id)
            print("export allowed")
            return 0

    except GateError as e:
        print(f"GATE REFUSED: {e}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

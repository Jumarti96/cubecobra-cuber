#!/usr/bin/env python3
"""Install and verify the whole Claude Code environment for this repo.

    python scripts/install_claude_env.py            # install + verify
    python scripts/install_claude_env.py --check    # verify only, change nothing

This is the single entry point a new clone runs. It:

  1. installs the skills   (skills/ -> .claude/skills/, via install_skills.py)
  2. verifies the project settings and the build-deck export-gate hook
  3. warns if .claude/settings.local.json duplicates a project hook
  4. smoke-tests the gate end to end (an allow case AND a block case)

Exits non-zero if anything is broken, so it is safe to run in CI.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YEL, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    GREEN = RED = YEL = DIM = OFF = ""

_failures: list = []
_warnings: list = []


def ok(msg):
    print(f"  {GREEN}OK{OFF}    {msg}")


def warn(msg):
    _warnings.append(msg)
    print(f"  {YEL}WARN{OFF}  {msg}")


def bad(msg):
    _failures.append(msg)
    print(f"  {RED}FAIL{OFF}  {msg}")


def head(msg):
    print(f"\n{msg}")


# ── 1. skills ─────────────────────────────────────────────────────────────────

def install_skills(check_only: bool) -> None:
    head("1. Skills (skills/ -> .claude/skills/)")
    installer = ROOT / "scripts" / "install_skills.py"
    if not installer.is_file():
        bad(f"missing {installer}")
        return

    if check_only:
        missing = [p.name for p in (ROOT / "skills").iterdir()
                   if (p.is_dir() and (p / "SKILL.md").is_file()) or p.suffix == ".md"
                   if not (ROOT / ".claude" / "skills" /
                           (p.stem if p.suffix == ".md" else p.name) / "SKILL.md").is_file()]
        if missing:
            bad(f"not installed: {', '.join(missing)} — run without --check")
        else:
            ok("all skills present in .claude/skills/")
        return

    proc = subprocess.run([sys.executable, str(installer)],
                          capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        bad(f"install_skills.py failed:\n{proc.stdout}{proc.stderr}")
        return
    for line in proc.stdout.strip().splitlines():
        if "->" in line:
            print(f"  {DIM}{line.strip()}{OFF}")
    ok("skills installed")


# ── 2. settings + hook wiring ─────────────────────────────────────────────────

def check_settings() -> None:
    head("2. Claude settings & export-gate hook")

    project = ROOT / ".claude" / "settings.json"
    if not project.is_file():
        bad(f"missing {project} — the export gate will not be enforced")
        return

    try:
        data = json.loads(project.read_text(encoding="utf-8"))
    except ValueError as e:
        bad(f".claude/settings.json is not valid JSON: {e}")
        return
    ok(".claude/settings.json parses")

    pre = (data.get("hooks") or {}).get("PreToolUse") or []
    gate_cmds = [h.get("command", "") for entry in pre for h in (entry.get("hooks") or [])
                 if "gate_export.py" in h.get("command", "")]
    if not gate_cmds:
        bad("no PreToolUse hook invoking scripts/gate_export.py — export gate is OFF")
    else:
        ok(f"export-gate hook wired ({len(gate_cmds)} entry)")
        for cmd in gate_cmds:
            if "CLAUDE_PROJECT_DIR" not in cmd and str(ROOT) not in cmd:
                warn(f"hook command may not be portable: {cmd}")

    if not (ROOT / "scripts" / "gate_export.py").is_file():
        bad("scripts/gate_export.py is missing")

    # A project hook duplicated in settings.local.json runs twice per tool call.
    local = ROOT / ".claude" / "settings.local.json"
    if local.is_file():
        try:
            ld = json.loads(local.read_text(encoding="utf-8"))
        except ValueError:
            warn("settings.local.json is not valid JSON (ignored by this check)")
            return
        lpre = (ld.get("hooks") or {}).get("PreToolUse") or []
        if any("gate_export.py" in h.get("command", "")
               for e in lpre for h in (e.get("hooks") or [])):
            warn("settings.local.json ALSO defines the gate hook — it will run twice. "
                 "Remove it from the local file; the project file now covers it.")
        else:
            ok("settings.local.json does not duplicate the gate hook")


# ── 3. orchestrator import ────────────────────────────────────────────────────

def check_orchestrator() -> None:
    head("3. Orchestrator")
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'.'); from cuber import orchestrator as o; "
         "print(len(o.PHASES), o.PHASE_GRILL)"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        bad(f"cannot import cuber.orchestrator:\n{proc.stderr.strip()}")
        return
    n, grill = proc.stdout.split()
    ok(f"cuber.orchestrator imports ({n} phases, gate phase {grill})")


# ── 4. gate smoke test ────────────────────────────────────────────────────────

def _fire_hook(event: dict, runs_root: Path):
    env = {**os.environ, "CUBER_RUNS_ROOT": str(runs_root), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "gate_export.py")],
                          input=json.dumps(event), capture_output=True, text=True,
                          env=env, cwd=str(ROOT))


def smoke_test_gate() -> None:
    head("4. Export-gate smoke test")
    sandbox = ROOT / "_workspace" / "_env_check"
    if sandbox.exists():
        shutil.rmtree(sandbox, ignore_errors=True)
    sandbox.mkdir(parents=True, exist_ok=True)
    try:
        # allow case: an unrelated write must pass
        p = _fire_hook({"tool_name": "Write",
                        "tool_input": {"file_path": "cuber/orchestrator.py"}}, sandbox)
        if p.returncode == 0:
            ok("unrelated write allowed (exit 0)")
        else:
            bad(f"unrelated write was blocked (exit {p.returncode}) — hook is too broad")

        # block case: a deck write with no verified grill must be denied
        p = _fire_hook({"tool_name": "Write",
                        "tool_input": {"file_path": "cubes/demo/decks/d/deck.json"}}, sandbox)
        if p.returncode == 2:
            ok("ungated deck export blocked (exit 2)")
        else:
            bad(f"ungated deck export was NOT blocked (exit {p.returncode}) — "
                f"the gate does not work. A validator that passes everything is a bug.")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


# ── main ──────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="verify only; do not install anything")
    args = ap.parse_args(argv)

    print(f"Claude Code environment for {ROOT.name}")
    print(f"{DIM}{ROOT}{OFF}")

    install_skills(args.check)
    check_settings()
    check_orchestrator()
    smoke_test_gate()

    print("\n" + "-" * 64)
    if _failures:
        print(f"{RED}{len(_failures)} problem(s):{OFF}")
        for f in _failures:
            print(f"  - {f}")
        return 1

    if _warnings:
        print(f"{YEL}{len(_warnings)} warning(s):{OFF}")
        for w in _warnings:
            print(f"  - {w}")

    print(f"{GREEN}Environment OK.{OFF}")
    if not args.check:
        print("\nRestart Claude Code to pick up skills and hooks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

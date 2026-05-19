#!/usr/bin/env python3
"""Sync skills/ → .claude/skills/ so Claude Code can invoke them.

Run this after cloning or after editing any skill in skills/:
    python scripts/install_skills.py

Each skills/<name>.md is copied to .claude/skills/<name>/SKILL.md.
The .claude/skills/ directory is what Claude Code reads when you type /<name>.
"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src_dir = root / "skills"
dst_dir = root / ".claude" / "skills"

if not src_dir.is_dir():
    print(f"ERROR: skills/ directory not found at {src_dir}")
    raise SystemExit(1)

installed = 0
for skill_file in sorted(src_dir.glob("*.md")):
    skill_name = skill_file.stem
    dst_folder = dst_dir / skill_name
    dst_folder.mkdir(parents=True, exist_ok=True)
    dst_file = dst_folder / "SKILL.md"
    shutil.copy2(skill_file, dst_file)
    print(f"  {skill_file.name:30s} -> .claude/skills/{skill_name}/SKILL.md")
    installed += 1

print(f"\n{installed} skill(s) installed. Restart Claude Code to pick up changes.")

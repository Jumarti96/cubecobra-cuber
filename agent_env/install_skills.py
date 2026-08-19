#!/usr/bin/env python3
"""Sync skills/ → .claude/skills/ so Claude Code can invoke them.

Run this after cloning or after editing any skill in skills/:
    python scripts/install_skills.py

Two skill layouts are supported:
  - Flat file:  skills/<name>.md            → .claude/skills/<name>/SKILL.md
  - Directory:  skills/<name>/SKILL.md      → .claude/skills/<name>/ (copied as a
                (plus references/, etc.)      whole tree; stale files are removed)

A name may use only one layout — both skills/<name>.md and skills/<name>/ is an error.
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

flat = {p.stem: p for p in src_dir.glob("*.md")}
dirs = {p.name: p for p in src_dir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}

collisions = sorted(flat.keys() & dirs.keys())
if collisions:
    print(f"ERROR: skill(s) defined as both a flat file and a directory: {', '.join(collisions)}")
    print("Remove one of the two layouts for each name, then re-run.")
    raise SystemExit(1)

installed = 0
for skill_name, skill_file in sorted(flat.items()):
    dst_folder = dst_dir / skill_name
    dst_folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(skill_file, dst_folder / "SKILL.md")
    print(f"  {skill_file.name:30s} -> .claude/skills/{skill_name}/SKILL.md")
    installed += 1

for skill_name, skill_folder in sorted(dirs.items()):
    dst_folder = dst_dir / skill_name
    if dst_folder.exists():
        shutil.rmtree(dst_folder)  # so deleted reference files don't linger stale
    shutil.copytree(skill_folder, dst_folder)
    n_files = sum(1 for p in dst_folder.rglob("*") if p.is_file())
    print(f"  {skill_name + '/':30s} -> .claude/skills/{skill_name}/ ({n_files} files)")
    installed += 1

print(f"\n{installed} skill(s) installed. Restart Claude Code to pick up changes.")

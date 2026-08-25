#!/usr/bin/env python3
"""Sync skills/ → .claude/skills/ so Claude Code can invoke them.

Run this after cloning or after editing any skill in skills/:
    python scripts/install_skills.py            # copy (default)
    python scripts/install_skills.py --link     # link instead of copying
    python scripts/install_skills.py --status   # show what each skill is installed as

`skills/` is the source of truth and the only tracked copy. `.claude/skills/` is a
local working copy that Claude Code reads when you type /<name>.

Two skill layouts are supported:
  - Flat file:  skills/<name>.md            → .claude/skills/<name>/SKILL.md
  - Directory:  skills/<name>/SKILL.md      → .claude/skills/<name>/ (whole tree;
                (plus references/, etc.)      stale files are removed)

A name may use only one layout — both skills/<name>.md and skills/<name>/ is an error.

--link mode
-----------
Installs directory skills as a junction (Windows) or symlink (POSIX) pointing at
`skills/<name>/`, so there is exactly ONE set of files. This removes the failure
mode where someone edits `.claude/skills/<name>/` — the copy Claude Code loads —
and the work is then silently destroyed by the next plain `install_skills.py` run,
or is simply never committed because `.claude/` is untracked.

Flat-file skills are always copied: a directory link cannot stand in for a single
file, and Windows file symlinks need admin. Convert a flat skill to the directory
layout if you want it linked.
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src_dir = root / "skills"
dst_dir = root / ".claude" / "skills"

# How each directory skill was last installed, so a plain run preserves the choice
# instead of silently reverting a link to a copy. Machine-local: .claude/skills/ is
# gitignored, and the mode is a property of this checkout, not of the repo.
MODE_FILE = dst_dir / ".install-mode.json"


def load_modes() -> dict:
    try:
        return json.loads(MODE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_modes(modes: dict) -> None:
    MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODE_FILE.write_text(json.dumps(modes, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def is_link(p: Path) -> bool:
    """True for a symlink OR a Windows directory junction.

    A junction is NOT a symlink to Path.is_symlink() — it reports False — so the
    obvious guard misses it. os.path.isjunction exists from Python 3.12.
    """
    if p.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction and isjunction(p))


def remove_dst(p: Path) -> None:
    """Remove a destination that may be a real directory, a symlink, or a junction.

    shutil.rmtree raises OSError on a link rather than recursing, which is the safe
    behaviour — but it means the plain-copy path crashes on a linked destination if
    we do not unlink first. Unlinking removes the link and never touches the target.
    """
    if not p.exists() and not is_link(p):
        return
    if is_link(p):
        if p.is_symlink():
            p.unlink()
        else:
            os.rmdir(p)  # junction: removes the reparse point, leaves the source intact
    else:
        shutil.rmtree(p)


def make_link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        # Junction, not symlink: works without admin rights or Developer Mode.
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                       check=True, capture_output=True, text=True)
    else:
        dst.symlink_to(src, target_is_directory=True)


def describe(dst: Path, src: Path) -> str:
    """Report how `dst` is installed. `src` is skills/<name>.md for a flat skill
    or skills/<name>/ for a directory skill — the two compare differently."""
    if not dst.exists() and not is_link(dst):
        return "missing"
    if is_link(dst):
        try:
            target = Path(os.path.realpath(dst))
        except OSError:
            return "link (unresolvable)"
        return "linked" if target == src.resolve() else f"linked -> {target} (WRONG TARGET)"
    if src.is_file():
        installed = dst / "SKILL.md"
        if not installed.is_file():
            return "copied (STALE — SKILL.md missing)"
        same = installed.read_bytes() == src.read_bytes()
    else:
        same = not _tree_differs(src, dst)
    return "copied (in sync)" if same else "copied (STALE — re-run install)"


def _tree_differs(a: Path, b: Path) -> bool:
    fa = {p.relative_to(a): p for p in a.rglob("*") if p.is_file()}
    fb = {p.relative_to(b): p for p in b.rglob("*") if p.is_file()}
    if set(fa) != set(fb):
        return True
    return any(fa[k].read_bytes() != fb[k].read_bytes() for k in fa)


ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
mode_group = ap.add_mutually_exclusive_group()
mode_group.add_argument("--link", action="store_true",
                        help="install directory skills as junctions/symlinks and remember it")
mode_group.add_argument("--copy", action="store_true",
                        help="install directory skills as copies and remember it")
ap.add_argument("--status", action="store_true",
                help="report how each skill is currently installed and exit")
args = ap.parse_args()

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

modes = load_modes()

if args.status:
    print("skill                          layout     state")
    for name, skill_file in sorted(flat.items()):
        print(f"  {name:28s} flat       {describe(dst_dir / name, skill_file)}")
    for name, folder in sorted(dirs.items()):
        remembered = modes.get(name, "copy")
        print(f"  {name:28s} directory  {describe(dst_dir / name, folder)}"
              f"   [remembered: {remembered}]")
    raise SystemExit(0)

installed = 0
for skill_name, skill_file in sorted(flat.items()):
    dst_folder = dst_dir / skill_name
    if is_link(dst_folder):
        remove_dst(dst_folder)  # was linked as a directory skill; it is flat now
    dst_folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(skill_file, dst_folder / "SKILL.md")
    print(f"  {skill_file.name:30s} -> .claude/skills/{skill_name}/SKILL.md  (copied)")
    installed += 1

for skill_name, skill_folder in sorted(dirs.items()):
    dst_folder = dst_dir / skill_name
    # A plain run preserves however this skill was last installed. Without that,
    # `install_skills.py` silently reverts a link to a copy and the drift the link
    # was meant to prevent comes straight back.
    if args.link:
        want = "link"
    elif args.copy:
        want = "copy"
    else:
        want = modes.get(skill_name, "copy")

    if want == "link":
        if is_link(dst_folder) and Path(os.path.realpath(dst_folder)) == skill_folder.resolve():
            print(f"  {skill_name + '/':30s} -> .claude/skills/{skill_name}/  (already linked)")
            modes[skill_name] = "link"
            installed += 1
            continue
        remove_dst(dst_folder)
        make_link(skill_folder, dst_folder)
        kind = "junction" if os.name == "nt" else "symlink"
        print(f"  {skill_name + '/':30s} -> .claude/skills/{skill_name}/  ({kind})")
    else:
        remove_dst(dst_folder)  # handles a previously-linked destination safely
        shutil.copytree(skill_folder, dst_folder)
        n_files = sum(1 for p in dst_folder.rglob("*") if p.is_file())
        print(f"  {skill_name + '/':30s} -> .claude/skills/{skill_name}/ ({n_files} files, copied)")
    modes[skill_name] = want
    installed += 1

save_modes(modes)

linked_now = sorted(n for n, m in modes.items() if m == "link" and n in dirs)
print(f"\n{installed} skill(s) installed. Restart Claude Code to pick up changes.")
if linked_now:
    print(f"Linked (edit in place, .claude/skills/<name>/ IS skills/<name>/): {', '.join(linked_now)}")
    print("Plain runs preserve this. Use --copy to go back to copies.")

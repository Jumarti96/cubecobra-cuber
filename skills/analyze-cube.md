---
name: analyze-cube
description: Produce a full statistics dashboard for a locally cached cube
---
# /analyze-cube — Cube Statistics Dashboard

Produce a full statistics dashboard for a locally cached cube: color distribution, CMC curve, rarity, card types, and archetype tag density. All metrics are **informational** — no distribution triggers a warning or error.

---

## Balance Checks Are Informational

A mono-colored cube, a combo-focused cube, or a set with 80% blue cards is valid.
Never tell the user their cube is "unbalanced" or "broken" based on generic reference ranges.
Report what exists; let the user interpret it.

---

## Prerequisites

Fetch and enrich first:
```
cuber fetch <id>
cuber enrich <id>
```

**Finding the cube folder:** In v2, the folder name is the title slug, not the short ID. Run `cuber list` to see all cubes with their slugs and short IDs. Use `cubes/<slug>/` for all file path operations below.

---

## Workflow

### Step 1 — Run stats command

```
cuber stats <id>
```

This prints the human-readable report to stdout and writes `cubes/<slug>/analysis.json`.

### Step 2 — Read and present results

Read `cubes/<slug>/analysis.json` for the structured data. Present:

**Color Identity Distribution**
Counts and percentages for W / U / B / R / G / Multi / Colorless.

**CMC Curve**
Count by CMC bucket (0–7+), split by creature vs. non-creature.

**Rarity Breakdown**
Counts and percentages for Common / Uncommon / Rare / Mythic.

**Card Type Breakdown**
Creature / Instant / Sorcery / Enchantment / Artifact / Planeswalker / Land / Other.

**Archetype Tag Density** (only if tags exist)
Cards per tag, sorted descending. Tags with fewer than 3 cards get an informational note — not a warning.
If no tags: suggest running `/tag-cube <short-id>` first.

### Step 3 — Write analysis.json sidecar

The CLI command writes `cubes/<slug>/analysis.json` automatically.
Confirm its path to the user: "Full analysis: cubes/<slug>/analysis.json"

---

## Tool Selection Table

| Task | Command |
|------|---------|
| Resolve cube slug | `cuber list` |
| Compute all stats | `cuber stats <id>` |
| Read structured results | Read `cubes/<slug>/analysis.json` |
| Check tag density | Read `analysis.json` → `tag_density` field |
| Check if tags exist | Read `cubes/<slug>/enriched.json` → any card with non-empty `tags` |

---

## Interpretation Guidelines

- Color imbalance is intentional in themed cubes. Ask before suggesting changes.
- CMC curve: note anything unusual (e.g., no 1-drops if aggro is a stated archetype).
- Low tag density (< 3 cards) on a tag: flag as informational, not an error.
- If the user asks for suggestions after the analysis, switch to `/suggest-cube`.

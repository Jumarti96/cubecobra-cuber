# build-deck reference — Phases 10–11: render & save specs

Read at the start of Phase 10; covers the display template, format rules, the analysis validator, and every saved-file spec. Mechanics only — the binding rules (derive-never-type header counts, no external links) are in SKILL.md.

## Phase 10 — display template

```
═══════════════════════════════════════════════════════════════════
DECK: {name}  |  {format}  |  {colors}  |  {N} cards
═══════════════════════════════════════════════════════════════════

{Deck identity — 2–4 sentences of prose describing strategy and key interactions.}

MAINBOARD ({spells} spells + {lands} lands = {total})
──────────────────────────────────────────────────────────────────

LANDS ({N})
  Nx BasicLand
  Nx DualLand          Brief note (e.g. "BR dual, enters tapped")
  ...

CREATURES ({N})
CMC  Card                    Qty   Color  Role                    Rar
  1  Vexing Devil            x1    R      Turn-1 threat           R
  ...

INSTANTS & SORCERIES ({N})
CMC  Card                    Qty   Color  Role                    Rar
  1  Lightning Axe           x2    R      Removal/Discard outlet  U
  ...

OTHER SPELLS ({N})
CMC  Card                    Qty   Color  Role                    Rar
  3  Stensia Masquerade      x1    B      Combat pump             U
  ...

SIDEBOARD ({N})
──────────────────────────────────────────────────────────────────
Card                    Qty   Color  Role / When to board in     Rar
Tragic Slip             x2    B      Recursive threats, morbid   C
...

── ANALYSIS ───────────────────────────────────────────────────────
DECK IDENTITY
{2–4 sentences: the strategy, the win condition, the key interaction.
 Use build_output.deck_identity. This subsection is ALWAYS first.}

{Then write freely — about THIS deck. Surface the most interesting
strategic observations: synergy interactions, mechanical calculations,
matchup notes, play patterns, key card interactions. Use tables when
they add clarity. Minimum one substantive observation.}

STRUCTURAL CHECKS
{deck_checks.format_checks_report(build_output.structural_checks), followed by
 one line per structural_responses entry.}

FAILURE MODES
{All six rows from build_output.failure_modes — flood, screw, decapitation,
 gas-out, raced, disruption-fizzle — as a table:
 Mode | Verdict | Reasoning
 Verdict is "mitigation" or "accepted"; Reasoning is the entry's text, verbatim.}

CARDS CONSIDERED BUT EXCLUDED
{The sweep's considered_but_excluded entries, reproduced as card | reason.}

MANA AUDIT: {PASS/WARN/FAIL}
──────────────────────────────────────────────────────────────────
{format_audit_report output — use deck_audit.format_audit_report(audit)}

RESTRICTIONS COMPLIANCE
──────────────────────────────────────────────────────────────────
{checklist of each restriction with pass/fail}
═══════════════════════════════════════════════════════════════════
```

**Format rules:**
- `OTHER SPELLS` covers enchantments, artifacts, planeswalkers, sagas — omit the section if empty
- `INSTANTS & SORCERIES` is one section; do not split instants from sorceries
- No oracle excerpt column in any card table section
- The `── ANALYSIS ──` section is always present; write at least one observation even for simple decks
- Rarity abbreviation: C Common, U Uncommon, R Rare, M Mythic
- `Color` column value is the card's base mana cost colors from the `colors` field (not `color_identity`); kicker pips are excluded; CubeCobra single-letter notation: `B`, `R`, `BR`, `GU`, `C` (colorless); pad all Color values to the same column width for alignment
- **Canonical section names for analysis.md** (strict — do not rename or reorder): `## MAINBOARD`, `## SIDEBOARD`, `## ANALYSIS`, `## MANA AUDIT: {PASS|WARN|FAIL}`, `## RESTRICTIONS COMPLIANCE`; sub-headers: `### LANDS`, `### CREATURES`, `### INSTANTS & SORCERIES`, `### OTHER SPELLS`
- **`## ANALYSIS` always opens with `### DECK IDENTITY`** before any other content. Order within `## ANALYSIS`: `### DECK IDENTITY` → free-form observations → `### STRUCTURAL CHECKS` → `### FAILURE MODES` → `### CARDS CONSIDERED BUT EXCLUDED` → any remaining subsections.
- **`### FAILURE MODES` is a required subsection** of `## ANALYSIS`: a table with one row per mode — all six of `flood`, `screw`, `decapitation`, `gas-out`, `raced`, `disruption-fizzle` — columns `Mode | Verdict | Reasoning`, filled verbatim from `build_output.failure_modes`.
- **No Scryfall links. No external links of any kind.** Card names are plain text everywhere — in every card table, in the ANALYSIS body, and in `analysis.md`. Do not wrap card names in markdown links.

## Phase 10 — analysis validator (`_tmp_validate_analysis.py`)

After writing `analysis.md`, run a light re-parse that asserts:
- each section's summed `Qty` equals the number in that section's own header;
- `spells + lands == total` in the `## MAINBOARD` header;
- the section totals sum to the mainboard/sideboard counts in `deck.json`;
- `analysis.md` contains zero occurrences of `scryfall`;
- `### FAILURE MODES` exists inside `## ANALYSIS` and all six mode names — `flood`, `screw`, `decapitation`, `gas-out`, `raced`, `disruption-fizzle` — appear under it.

Any mismatch is a **hard failure**: regenerate `analysis.md` from the deck arrays. Never hand-patch the output to make the validator agree. This runs on every write of `analysis.md`.

## Phase 11 — saved-file specs

Four files, all into `cubes/<id>/decks/<name>/`.

**Write deck.json** using the Write tool to `cubes/<id>/decks/<name>/deck.json`:
```json
{
  "deck_name": "bg-graveyard",
  "cube_id": "551c6382-d024-4039-8fce-1cf9c23135b3",
  "cube_slug": "innistrad-remastered-set-dmu-dual-lands",
  "built_at": "2026-05-20T14:30:00Z",
  "format": "40-card",
  "strategy": "graveyard midrange",
  "colors": "BG",
  "identity": "Black-Green graveyard midrange with strong threat density",
  "restrictions": { ... },
  "commander": null,
  "mana_audit": { ... },
  "mainboard": [ {card dicts, board: "mainboard"} ],
  "sideboard": [ {card dicts, board: "sideboard"} ]
}
```

JSON rules:
- `cube_id`: the UUID from `meta.json` (`id` field)
- `cube_slug`: the slug from `meta.json` (`slug` field)
- `built_at`: ISO 8601 UTC, second precision, Z suffix — `"2026-05-20T14:30:00Z"`
- Card `board` values: `"mainboard"` / `"sideboard"` (full words, never `"main"` or `"side"`)
- `mana_audit` must include: `land_count`, `recommended_land_count`, `land_count_status`, `ramp_count`, `avg_cmc`, `pip_demand`, `land_color_production`, `color_balance_status`, `color_balance_per_color`, `overall_status`

Use the Write tool (apostrophes in card names break shell quoting).

---

**Write deck.tsv** using the Write tool to `cubes/<id>/decks/<name>/deck.tsv`:
Tab-separated values — no quoting or escaping of any kind. Columns in this exact order:
`name`, `CMC`, `Type`, `Color`, `Set`, `Collector Number`, `Rarity`, `Color Category`, `status`, `Finish`, `board`, `maybeboard`, `image URL`, `image Back URL`, `tags`, `Notes`, `MTGO ID`, `Custom`, `Voucher`

TSV rules:
- Values are separated by tab characters; never use CSV quoting even if a value contains a comma
- One row per card copy (a ×2 card produces 2 identical rows)
- `board` column: `mainboard` or `sideboard` (full words only, never `main` or `side`)
- `tags` field uses semicolons as its internal separator (e.g. `Aristocrats/Sacrifice;Payload/Payoff`)

---

**Write deck.mwDeck** using `exporter.write_mwdeck(mainboard, sideboard, short_id, deck_name)`:
The function writes to `cubes/<id>/decks/<name>/deck.mwDeck` automatically.

---

**Write analysis.md** using `exporter.write_deck_analysis_md(analysis_text, short_id, deck_name, frontmatter)`:

The saved file MUST follow this exact structure. Section order is strict — do not reorder, rename, or omit any section.

**Frontmatter** (exactly these keys, no others):
```yaml
---
deck_name: "<name>"
cube_id: "<UUID from meta.json>"
cube_slug: "<slug from meta.json>"
colors: "<e.g. BR>"
format: "<40-card|60-card|commander-60|commander-100>"
built_at: "<ISO 8601 UTC e.g. 2026-05-24T20:05:35Z>"
mana_audit_status: "<PASS|WARN|FAIL>"
restrictions_status: "<PASS|FAIL>"
---
```

**Section structure** (use `##` for top-level, `###` for sub-sections):

1. `## MAINBOARD ({spells} spells + {lands} lands = {total})`
   - `### LANDS ({N})` — land list in a fenced code block
   - `### CREATURES ({N})` — card table in a fenced code block; omit if empty
   - `### INSTANTS & SORCERIES ({N})` — card table in a fenced code block; omit if empty
   - `### OTHER SPELLS ({N})` — card table in a fenced code block; omit if empty
2. `## SIDEBOARD ({N})` — card table in a fenced code block
3. `## ANALYSIS` — free Markdown body (NOT in a code block). **MUST open with `### DECK IDENTITY`**, then free-form observations (at least one substantive), then `### STRUCTURAL CHECKS` (the `format_checks_report` output in a fenced code block plus any `structural_responses` lines), then `### FAILURE MODES` (the six-row `Mode | Verdict | Reasoning` table from `build_output.failure_modes`), then `### CARDS CONSIDERED BUT EXCLUDED` (the sweep's `considered_but_excluded` entries).
4. `## MANA AUDIT: {PASS|WARN|FAIL}` — audit report in a fenced code block
5. `## RESTRICTIONS COMPLIANCE` — checklist in a fenced code block

Card table columns in fenced code blocks: `CMC  Card  Qty  Color  Role  Rar` (mainboard); `Card  Qty  Color  Role / When to board in  Rar` (sideboard).

**No Scryfall links. No external links of any kind.** Card names are plain text in every fenced code block table and throughout the `## ANALYSIS` body.

**Header counts are derived and then verified.** Every `({N})` in a section header is computed from the deck arrays (sum of `qty`), never hand-written. After writing `analysis.md`, run `_tmp_validate_analysis.py` (see Phase 10) and confirm every check passes. A mismatch is a hard failure — regenerate the file; never hand-patch the number.

The `frontmatter` dict passed to `exporter.write_deck_analysis_md()`:
```python
{
    "deck_name": deck_name,
    "cube_id": cube_id,       # UUID from meta.json
    "cube_slug": cube_slug,   # slug from meta.json
    "colors": colors,         # e.g. "BR"
    "format": format,         # e.g. "40-card"
    "built_at": built_at,     # same timestamp as deck.json
    "mana_audit_status": audit["overall_status"],    # "PASS" / "WARN" / "FAIL"
    "restrictions_status": "PASS",  # or "FAIL" if any check failed
}
```

---

Confirm all four paths:
```
Saved:
  cubes/<id>/decks/<name>/deck.json
  cubes/<id>/decks/<name>/deck.tsv
  cubes/<id>/decks/<name>/deck.mwDeck
  cubes/<id>/decks/<name>/analysis.md
```

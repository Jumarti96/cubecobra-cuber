# build-deck reference — Phase 0: workspace & pool mechanics

Read at the start of Phase 0. Mechanics only — the binding rules (workspace hygiene, confirmation gates, IRON RULES) are in SKILL.md.

## Workspace Setup — run-token minting (steps 1–3)

1. Generate a **run token** unique to this invocation AND atomically create its directory in one step. The token is a microsecond-precision UTC timestamp plus a full 32-char uuid4 hex — e.g. `run-20260709T041210123456-a3f9c1e2b4d64f7a8c9e0f1a2b3c4d5e`. Run:
   ```
   python -c "import datetime,uuid,os; t='run-'+datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')+'-'+uuid.uuid4().hex; os.makedirs(os.path.join('_workspace',t)); print(t)"
   ```
   This prints the token AND creates `_workspace/<run-token>/` in the repo root. `os.makedirs` runs with the default `exist_ok=False`, so it fails with `FileExistsError` if that directory already exists — that failure is your collision signal (another concurrent session grabbed the same token).
2. **On collision:** if the command errors (e.g. `FileExistsError`), just run it again — it mints a fresh token (new microsecond timestamp, new uuid4) every invocation, so a retry cannot reuse the colliding directory. Retry up to 3 times; if it still fails, stop and report the error instead of proceeding. **Never** create the run directory by hand or with `exist_ok=True` — that would silently reuse a directory another run already owns, which is exactly the cross-session contamination this guards against.
3. Track the printed `<run-token>` path for the rest of the session. This is this run's private scratch directory.

## Pool Restrictions — `card_pool_rules` shape

From the user's answer, infer a `card_pool_rules` object:

```json
{
  "base": "cube_mainboard",
  "multipliers": { "common": 2, "uncommon": 2 },
  "only_from": { "rare": ["Card A", "Card B"] },
  "excluded": ["Oko, Thief of Crowns"]
}
```

- `base` is always `"cube_mainboard"` — only the mainboard is supported.
- `multipliers`: per-rarity max copy count (rarity not listed = 1 copy).
- `only_from`: per-rarity allowlist — all other cards of that rarity are excluded.
- `excluded`: specific card names excluded regardless of other rules.

## Working Pool Cache — per-card field lists

Include per-card fields: `name`, `oracle_text`, `mana_cost`, `colors`, `color_identity`, `tags`, `taxonomic_profile`, `cmc`, `type_line`, `rarity`, `power`, `toughness`, `board`.

`tags` and `mana_cost` are **load-bearing, not optional**: `deck_audit.mana_audit()` derives `ramp_count` from `tags` (see `deck_audit.RAMP_TAGS`), and pip-demand math needs `mana_cost`. Omit either and the audit silently computes garbage rather than failing.

Exclude: `image URL`, `image Back URL`, `MTGO ID`, `Custom`, `Voucher`, `status`, `Finish`, `Set`, `Collector Number`, and any other display-only metadata.

**One exemption:** the Phase 11 export needs `Set`, `Collector Number`, and image URLs for `deck.tsv`, which the working pool deliberately excludes. Capture those in Phase 0 alongside the working pool — write `_workspace/<run-token>/export_meta.json` keyed by card name — so Phase 11 never has to re-open `enriched.json`.

## Attempt-Directory Layout

```
_workspace/<run-token>/
  working_pool.json          ← attempt-invariant
  export_meta.json           ← attempt-invariant
  attempt-1/   pool_tiers.json  sweep.json  grill_input.json  _tmp_*.py
  attempt-2/   ...            ← Re-evaluation Path: next pipeline, fresh sweep
```

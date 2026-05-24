# RPDC Local Memory Integration Plan — Option B

**Approved:** 2026-05-24  
**Classification:** OPTION_B_APPROVED / SUPABASE_BACKFILL_NOT_APPROVED / READ_ONLY_BRIDGE  
**Hard constraint:** No scoring formula changes. No model changes. No old velo_verdicts mutation.  

---

## Option B — What it is

Option B uses `data/rpdc_backfill/rpdc_tags_historical.jsonl` as a read-only RPDC memory
bridge. This file was built locally without touching Supabase by running
`scripts/backfill_rpdc_historical_local.py`, which replays the RPDC tag computation
against historical results files.

**Current state of the JSONL:**
- 18,554 rows
- 44 scored dates (2026-03-17 to 2026-05-23)
- 14,810 unique horse IDs (hrs_ format — Racing API origin)
- 13,627 unique normalised horse names
- 9.2% cash window rate (release_score ≥ 3.0)

**What Option B is NOT:**
- It is NOT a Supabase migration
- It is NOT the rpdc_horse_memory table (that is Option A, not approved)
- It is NOT a scoring change — RPDC context is annotation only
- It is NOT a fix for the improvement_score variance gap (that is a separate engineering task)

---

## Why old verdicts remain untouched

`velo_verdicts` contains the immutable historical record of every scored race. Retroactively
enriching them with RPDC context would mutate the audit trail. This is prohibited.

The Option B bridge applies forward only: when a new race is scored, the adapter reads the
JSONL to provide historical context for each runner. Prior verdicts are left as-is.

---

## Architecture — Option B read-only bridge

```
data/rpdc_backfill/rpdc_tags_historical.jsonl
        │
        │ (loaded once at startup into memory dict)
        ▼
scripts/ops/load_rpdc_memory.py
  ├── load_rpdc_memory()          — returns {by_name, by_horse_id, _total_rows, ...}
  ├── lookup_horse_memory()       — returns most recent row strictly before as_of_date
  ├── get_prior_tags()            — returns rpdc_tags list
  └── get_memory_summary_for_runner() — returns full context dict for one runner
        │
        │ (read-only context dict — no writes, no Supabase calls)
        ▼
  Scoring pipeline (future integration point)
  run_prime_today.py → predict_race() → [optional] annotate with RPDC context
```

### Match strategy

Horse ID formats differ between systems:
- RPDC JSONL: `hrs_XXXXXXXX` (Racing API origin — numeric ID prefixed)
- Runner snapshots: `rp_COURSE_horse_name` (Racing Post origin — slug format)

The adapter resolves this in priority order:
1. Exact `horse_id` match (hrs_ format only — most reliable)
2. Normalised horse name match (lowercase, strip country suffix like "(IRE)", collapse whitespace)
3. Name extracted from RP-format slug (`rp_CUR_sun_goddess` → `sun goddess`)

May 24 proxy result: 62.7% match rate (151/241 runners) — classified MODERATE.
Gap is driven by the hrs_/rp_ format mismatch, not missing history.

---

## Scoring integration — current state

**RPDC Option B is currently annotation-only. It does NOT enter the scoring formula.**

As of 2026-05-24:
- Active scoring components: `market_deception_score`, `sqpe_v17`
- `improvement_score` = 0.0872 constant for all runners → zero-variance kill switch fires → excluded
- RPDC context is available via `get_memory_summary_for_runner()` but is NOT injected into any component

The scoring path with and without RPDC Option B is IDENTICAL. See audit:
`data/reports/rpdc_scoring_comparison_2026-05-25.json`

---

## Future integration points (each requires separate operator decision)

### Gate 1 — RPDC annotation in runner context (LOW risk, no scoring change)

The RPDC context dict could be attached to the runner object passed to downstream
consumers (Mission Control, Telegram panel, dashboard) as a read-only annotation.
This would make `rpdc_primary_tag`, `rpdc_cash_window_flag`, `rpdc_release_score`
visible in the output without changing any scores.

**Requirement:** Operator decision. One-line change to `_attach_rpdc_from_row()` to
read from local JSONL instead of (or as fallback to) `runner_release_candidates`.

### Gate 2 — improvement_score variance restoration (MEDIUM risk, scoring change)

The improvement model has 12 features. All 12 are None since Racing API decommission
(2026-05-14). Three features are recoverable from racecard without pipeline change:
`or_vs_field`, `rpr_vs_field`, `age_num`. One feature is recoverable from RPDC JSONL:
`curr_or_minus_last_win_or` (via `or_delta_to_win`).

Injecting these 4 features would partially restore improvement_score variance. Full
restoration requires a separate engineering spec and operator approval. This is NOT
part of Option B.

See audit: `data/reports/improvement_feature_availability_2026-05-25.json`

### Gate 3 — Option A: rpdc_horse_memory Supabase table (HIGH risk — Council required)

A Supabase `rpdc_horse_memory` table would provide persistent, queryable, multi-process
access to RPDC history. This requires:
- Council approval (new table, schema change)
- Migration script reviewed and approved
- Conflict key defined
- Rollback plan documented

This is explicitly NOT approved. See RPDC_SUPABASE_BACKFILL_PROPOSAL.md for the proposal.

---

## Mission Control display

The existing Mission Control chain (`data/mission_control/`) should expose RPDC memory
status. When the JSONL is healthy:

```json
"rpdc_chain": {
  "status": "OPTION_B_LOCAL_MEMORY",
  "memory_rows": 18554,
  "date_range": {"first": "2026-03-17", "last": "2026-05-23"},
  "match_rate_last_card": 62.7,
  "formula_status": "FEATURE_DEGRADED",
  "improvement_score_constant": true,
  "improvement_score_value": 0.0872,
  "active_components": ["market_deception_score", "sqpe_v17"],
  "supabase_backfill": "NOT_APPROVED"
}
```

---

## Daily operations — Option B maintenance

Option B requires zero daily maintenance. The JSONL does not need to be rebuilt each
day. It is a static snapshot (as of 2026-05-24).

To extend the JSONL to include new scored dates (e.g. after May 24 results close):

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/backfill_rpdc_historical_local.py
```

This is safe to re-run — it rebuilds from all available results files and overwrites
the JSONL. No Supabase interaction. Operator can run this at any time.

---

## No Supabase migration — rationale

The local JSONL provides sufficient RPDC context for Option B purposes. Migrating to
Supabase would require:
- Schema approval
- Migration script with rollback
- Conflict key audit
- CI/CD integration
- No net gain in scoring quality (improvement_score still constant regardless of storage)

The Supabase option remains available as Option A when the Council decides to approve it.
Until then, the JSONL is the canonical RPDC memory source.

---

## Immutability rules

```
OLD_VERDICTS_MUTATION:    PROHIBITED — velo_verdicts is immutable audit trail
SCORING_FORMULA_CHANGE:   PROHIBITED — requires separate Council approval
MODEL_CHANGE:             PROHIBITED — requires evidence gate + operator decision
ROUTER_CHANGE:            PROHIBITED — requires evidence gate
STAKING_CHANGE:           PROHIBITED — paper ledger only until promotion gate
TELEGRAM_PICK_CHANGE:     PROHIBITED — format locked (see feedback_sigma_process.md)
PLAYBOOK_G_CHANGE:        PROHIBITED — requires learning loop evidence gate
SUPABASE_MIGRATION:       NOT_APPROVED — requires Council decision
NINE_DATE_INGEST:         NOT_APPROVED — each date requires individual operator sign-off
                          (see RPDC_NINE_DATE_INGEST_APPROVAL_PACKET.md)
```

---

## Summary classification

```
OPTION_B_APPROVED:                    2026-05-24
LOCAL_JSONL_PATH:                     data/rpdc_backfill/rpdc_tags_historical.jsonl
ADAPTER_PATH:                         scripts/ops/load_rpdc_memory.py
MEMORY_ROWS:                          18,554
MEMORY_DATE_RANGE:                    2026-03-17 → 2026-05-23
MAY24_MATCH_RATE:                     62.7% (MODERATE)
FORMULA_STATUS:                       FEATURE_DEGRADED
IMPROVEMENT_SCORE_VARIANCE_RESTORED:  NO
SCORING_CHANGE:                       NONE
SUPABASE_MUTATED:                     NO
OLD_VERDICTS_MUTATED:                 NO
OPTION_A_STATUS:                      NOT_APPROVED
NINE_DATE_INGEST_STATUS:              NOT_APPROVED
```

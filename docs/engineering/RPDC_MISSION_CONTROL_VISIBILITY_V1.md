# RPDC Mission Control Visibility V1

**Prepared:** 2026-05-24  
**Classification:** MISSION_CONTROL_CHAIN / DISPLAY_SPEC / NO_SCORING_CHANGE  
**Hard constraint:** Mission Control is display-only. No scoring decisions, no weight changes, no formula mutations derive from this output.

---

## Purpose

Mission Control is the operator's daily health dashboard. This document defines what
RPDC-related information Mission Control must expose, in what format, and what each
field means. The goal is to make the FEATURE_DEGRADED state visible without hiding
any information about the current operational status.

**The operator must never be surprised by the formula state.** If improvement_score
is excluded, that must be visible. If RPDC tags are available but unapplied to scoring,
that must be visible. If learning is blocked, that must be visible.

---

## RPDC Chain Status Block

Mission Control chain JSON should include an `rpdc_chain` block at the top level.

### Template (FEATURE_DEGRADED state — current as of 2026-05-24)

```json
"rpdc_chain": {
  "status": "OPTION_B_LOCAL_MEMORY",
  "memory_rows": 18554,
  "date_range": {
    "first": "2026-03-17",
    "last": "2026-05-23"
  },
  "last_extended": "2026-05-24",
  "match_rate_last_card": 62.7,
  "formula_status": "FEATURE_DEGRADED",
  "improvement_score_constant": true,
  "improvement_score_value": 0.0872,
  "active_components": ["market_deception_score", "sqpe_v17"],
  "excluded_components": ["improvement_score"],
  "kill_switch_fired": true,
  "kill_switch_reason": "improvement_score zero-variance (all runners = 0.0872)",
  "supabase_backfill": "NOT_APPROVED",
  "option_a_table": "NOT_APPROVED",
  "nine_date_ingest": "AWAITING_OPERATOR_APPROVAL",
  "racecard_ratings_source": "MISSING",
  "learning_eligible": false,
  "learning_blocked_reason": "FEATURE_DEGRADED — degraded card excluded from learning",
  "degraded_card_count_this_week": null,
  "rpdc_shadow_lanes": {
    "STABLE_WARM": {"n": 40, "sr": 0.300, "frame": 0.625, "status": "VALUE_POSITIVE"},
    "CYCLE_RUN_2": {"n": 32, "sr": 0.312, "frame": 0.531, "status": "WATCHLIST"}
  }
}
```

### Template (PARTIAL_RESTORE state — after racecard fix applied)

```json
"rpdc_chain": {
  "status": "OPTION_B_LOCAL_MEMORY",
  "formula_status": "PARTIAL_RESTORE",
  "improvement_score_constant": false,
  "improvement_score_range": [0.004, 0.209],
  "active_components": ["market_deception_score", "sqpe_v17", "improvement_score"],
  "excluded_components": [],
  "kill_switch_fired": false,
  "racecard_ratings_source": "RP_MERGED_current_or",
  "learning_eligible": true,
  "rpdc_shadow_lanes": {
    "STABLE_WARM": {"n": 40, "sr": 0.300, "frame": 0.625, "status": "VALUE_POSITIVE"},
    "CYCLE_RUN_2": {"n": 32, "sr": 0.312, "frame": 0.531, "status": "WATCHLIST"}
  }
}
```

### Template (FULL_ENGINE state — all components active)

```json
"rpdc_chain": {
  "status": "OPTION_B_LOCAL_MEMORY",
  "formula_status": "FULL_ENGINE",
  "improvement_score_constant": false,
  "active_components": ["market_deception_score", "sqpe_v17", "improvement_score"],
  "kill_switch_fired": false,
  "learning_eligible": true
}
```

---

## Field Definitions

| Field | Type | Description | Current value |
|---|---|---|---|
| `status` | string | RPDC memory source type | OPTION_B_LOCAL_MEMORY |
| `memory_rows` | int | Total rows in local JSONL | 18,554 |
| `date_range.first` | date | Earliest RPDC record | 2026-03-17 |
| `date_range.last` | date | Most recent RPDC record | 2026-05-23 |
| `last_extended` | date | When JSONL was last rebuilt | 2026-05-24 |
| `match_rate_last_card` | float (%) | RPDC match rate on most recent scored card | 62.7 |
| `formula_status` | string | FEATURE_DEGRADED / PARTIAL_RESTORE / FULL_ENGINE | FEATURE_DEGRADED |
| `improvement_score_constant` | bool | True if all runners receive same improvement_score | true |
| `improvement_score_value` | float | Constant value when constant=true | 0.0872 |
| `active_components` | list | Components contributing to VP formula | [market_deception_score, sqpe_v17] |
| `excluded_components` | list | Components excluded by kill switch | [improvement_score] |
| `kill_switch_fired` | bool | True if any component excluded | true |
| `kill_switch_reason` | string | Human-readable exclusion reason | improvement_score zero-variance |
| `supabase_backfill` | string | Supabase migration status | NOT_APPROVED |
| `option_a_table` | string | rpdc_horse_memory Supabase table status | NOT_APPROVED |
| `nine_date_ingest` | string | Nine-date historical ingest status | AWAITING_OPERATOR_APPROVAL |
| `racecard_ratings_source` | string | Source for OFR/RPR/age fields | MISSING |
| `learning_eligible` | bool | Whether today's card qualifies for learning | false |
| `learning_blocked_reason` | string | Why learning is blocked | FEATURE_DEGRADED |
| `rpdc_shadow_lanes` | dict | Per-lane SR/Frame from tag value audit | see above |

---

## Operator-facing Status Messages

### FEATURE_DEGRADED (current)

```
⚠️ FORMULA STATUS: FEATURE_DEGRADED
   improvement_score: EXCLUDED (constant 0.0872 — zero-variance kill switch)
   Active: market_deception_score + sqpe_v17
   Learning: BLOCKED (degraded card)
   Racecard ratings source: MISSING (no OFR/RPR/age from RP F_0010 PDF)
   Fix available: 3-line patch in src/velo/racecard_loader.py (operator approval required)
```

### PARTIAL_RESTORE (after racecard fix)

```
✅ FORMULA STATUS: PARTIAL_RESTORE
   improvement_score: ACTIVE (range ~0.15–0.20)
   Active: market_deception_score + sqpe_v17 + improvement_score
   Learning: ELIGIBLE
   Racecard ratings source: RP_MERGED (current_or → ofr, rpr_master → rpr)
```

### FULL_ENGINE

```
✅ FORMULA STATUS: FULL_ENGINE
   All components: ACTIVE
   Learning: ELIGIBLE
```

---

## RPDC Memory Status Panel

Displayed alongside the chain block:

```
RPDC Memory Bridge (Option B)
──────────────────────────────
Source:        data/rpdc_backfill/rpdc_tags_historical.jsonl
Total rows:    18,554
Date range:    2026-03-17 → 2026-05-23 (44 dates)
Last rebuilt:  2026-05-24
Match rate:    62.7% (last card proxy)
Cash window:   9.2% of rows (release_score ≥ 3.0)

Shadow Lane Signals:
  STABLE_WARM   n=40  SR=30.0%  Frame=62.5%  → VALUE_POSITIVE
  CYCLE_RUN_2   n=32  SR=31.2%  Frame=53.1%  → WATCHLIST
  CYCLE_RUN_1   n=94  SR=22.3%  Frame=58.5%  → WATCHLIST

Improvement Feature Status:
  or_vs_field:  MISSING (no OFR from RP F_0010 PDF)
  rpr_vs_field: MISSING
  age_num:      MISSING
  Restore path: racecard_merged/current_or → awaiting operator approval
```

---

## Validation rules

Mission Control must NOT display:
- Improvement_score as ACTIVE when kill switch is firing
- FULL_FORMULA_ACTIVE if any component is excluded
- LEARNING_ELIGIBLE if formula is FEATURE_DEGRADED
- RPDC as scoring component (it is annotation only)

Mission Control MUST display:
- FEATURE_DEGRADED banner if kill switch fires
- Active component list (not just "full ensemble")
- Racecard ratings source status
- Shadow lane current SR/Frame (from `data/reports/rpdc_tag_value_latest.json`)

---

## Data sources for Mission Control population

| Field | Source |
|---|---|
| formula_status, active_components | Output of `run_prime_today.py` (verdict_flags) |
| improvement_score_constant, value | Compare min/max across scored runners |
| kill_switch_fired | `improvement_score` absent from verdict_flags |
| match_rate_last_card | `data/reports/rpdc_memory_card_coverage_{date}.json` |
| memory_rows, date_range | `scripts/ops/load_rpdc_memory.py` `_total_rows`, `_date_range` |
| rpdc_shadow_lanes | `data/reports/rpdc_tag_value_latest.json` |
| learning_eligible | verdict_flags `card_eligible_for_learning` |

---

## Update frequency

Mission Control is updated after each scoring run (`run_prime_today.py`) and after
each sigma run (`run_results_sigma.py`). The RPDC block should be rebuilt from:
1. The scored card's verdict_flags (formula_status, active_components)
2. The most recent tag value audit report (shadow lane stats)
3. The RPDC preflight check output (match_rate, memory_rows)

```bash
# After scoring and sigma:
source venv/bin/activate
PYTHONPATH=. python scripts/ops/update_mission_control.py
```

---

## Classification

```
STATUS:                  SPEC_DEFINED — not yet implemented in update_mission_control.py
SCORING_CHANGE:          NONE
FORMULA_CHANGE:          NONE
SUPABASE_WRITE:          NONE (Mission Control writes to local data/mission_control/)
DISPLAY_ONLY:            YES
OPERATOR_REQUIRED:       NO (display-only, no decisions embedded)
```

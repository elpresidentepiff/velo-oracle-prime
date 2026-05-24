# RPDC Shadow Lanes V1

**Prepared:** 2026-05-24  
**Classification:** RPDC_ADVISORY_ONLY / NO_LIVE_SCORING_CHANGE / SHADOW_EVIDENCE_ACCUMULATION  
**Hard constraint:** No live VP formula change. No weight changes. RPDC shadow lanes are observe-only until promoted through a separate operator gate.

---

## Purpose

Shadow lanes allow RPDC tag evidence to accumulate in parallel with the live scoring
pipeline without changing any VP formula, weight, or routing rule. Each lane defines
a selection filter based on RPDC context. Results are recorded, SR and frame metrics
computed, and promotion gates defined.

A shadow lane is NOT a bet recommendation. It is an evidence accumulation instrument.
No cash is risked. No Telegram picks are changed. No formula is touched.

Live VP formula (frozen):
```
VP = (0.45 × SQPE + 0.12 × improvement_score + 0.10 × MDS) / active_weight_sum
```

---

## Lane Definitions

### Lane 1 — RPDC_IMPROVER

**Hypothesis:** Horses with CYCLE_RUN_2 or STABLE_WARM tag + VP ≥ 0.30 outperform
the base VP≥0.30 population.

| Field | Value |
|---|---|
| Source fields | `rpdc_primary_tag` ∈ {CYCLE_RUN_2, STABLE_WARM} |
| VP filter | VP ≥ 0.30 |
| Tier filter | Tier A or Tier B |
| Minimum sample | 30 closed results |
| Promotion gate | SR ≥ 30% + Frame ≥ 65% at n ≥ 50 |
| Collapse threshold | SR < 18% at n ≥ 30 OR Frame < 50% at n ≥ 30 |
| Current evidence | STABLE_WARM SR=30.0% Frame=62.5% (n=40); CYCLE_RUN_2 SR=31.2% Frame=53.1% (n=32) |
| Status | WATCHLIST — promising but frame below 65% for CYCLE_RUN_2 |
| Why not live VP | n insufficient; RPDC match rate 15% on sigma; need 50+ closed results |

---

### Lane 2 — RPDC_REGRESSION_RISK

**Hypothesis:** Horses with MARK_NEAR or MARK_READY tag that are at or near winning OR
carry elevated suppression. These may be being laid by market for a reason.

| Field | Value |
|---|---|
| Source fields | `rpdc_primary_tag` ∈ {MARK_NEAR, MARK_READY} OR `rpdc_suppression_score` > 0.5 |
| VP filter | Any VP |
| Purpose | Warning overlay — flag runners to watch carefully, not suppress automatically |
| Minimum sample | 20 closed results |
| Promotion gate | N/A — this is a DIAGNOSTIC lane, not a selection lane |
| Collapse threshold | N/A |
| Current evidence | MARK_NEAR n=3 SR=66.7%; MARK_READY n=6 SR=33.3% — INSUFFICIENT_SAMPLE |
| Status | INSUFFICIENT_SAMPLE — monitor only |
| Why not live VP | n=9 total; cannot make inference from 9 results |

---

### Lane 3 — RPDC_COURSE_MEMORY

**Hypothesis:** Horses with COURSE_RETURN tag (returning to a course where they have
placed or won) have higher course-specific strike rate.

| Field | Value |
|---|---|
| Source fields | `course_return_flag` = True OR `rpdc_primary_tag` = COURSE_RETURN |
| VP filter | VP ≥ 0.25 |
| Minimum sample | 25 closed results |
| Promotion gate | SR ≥ 28% + Frame ≥ 60% at n ≥ 40 |
| Collapse threshold | SR < 15% at n ≥ 25 |
| Current evidence | COURSE_RETURN primary n=2 — INSUFFICIENT_SAMPLE; course_return_flag broader but not yet counted |
| Status | INSUFFICIENT_SAMPLE — data collection phase |
| Why not live VP | No meaningful sample yet |

---

### Lane 4 — RPDC_DISTANCE_MEMORY

**Hypothesis:** Horses with DISTANCE_RETURN tag (returning to a preferred distance
configuration) have lift over distance-agnostic selection.

| Field | Value |
|---|---|
| Source fields | `distance_revert_flag` = True OR `rpdc_primary_tag` = DISTANCE_RETURN |
| VP filter | VP ≥ 0.25 |
| Minimum sample | 25 closed results |
| Promotion gate | SR ≥ 28% + Frame ≥ 60% at n ≥ 40 |
| Collapse threshold | SR < 15% at n ≥ 25 |
| Current evidence | DISTANCE_RETURN primary n=1 — INSUFFICIENT_SAMPLE |
| Status | INSUFFICIENT_SAMPLE — data collection phase |
| Why not live VP | No meaningful sample yet |

---

### Lane 5 — RPDC_CASH_WINDOW

**Hypothesis:** Horses with `rpdc_cash_window_flag` = True (release_score ≥ 3.0)
represent the most concentrated RPDC signal. These are horses in their optimal
return-to-form window.

| Field | Value |
|---|---|
| Source fields | `rpdc_cash_window_flag` = True (release_score ≥ 3.0) |
| VP filter | VP ≥ 0.25 |
| Tier filter | Tier A preferred |
| Minimum sample | 20 closed results |
| Promotion gate | SR ≥ 35% + Frame ≥ 70% at n ≥ 30 |
| Collapse threshold | SR < 20% at n ≥ 20 |
| Current evidence | Cash window matched n ≈ 5 in sigma overlap — INSUFFICIENT_SAMPLE |
| Status | INSUFFICIENT_SAMPLE — data collection phase |
| Why not live VP | Cash window rate 9.2% of RPDC rows. With 15% sigma match rate, n accumulates slowly |

---

### Lane 6 — RPDC_NO_PRIOR_HISTORY

**Hypothesis:** Horses with NO entry in the RPDC JSONL are first-run or identity-gap
runners. The system has no prior knowledge of these horses. This is a DIAGNOSTIC lane
to quantify the RPDC blind spot.

| Field | Value |
|---|---|
| Source fields | Horse NOT found in RPDC index |
| VP filter | Any VP |
| Purpose | Baseline comparison — what is the SR of predictions where RPDC has no data? |
| Current evidence | No-RPDC-history SR=20.1% Frame=46.9% (n=1511 in sigma overlap) |
| Status | ACTIVE DIAGNOSTIC |
| Insight | No-RPDC picks perform below global baseline (SR=20.9%). RPDC presence = positive signal. |

---

### Lane 7 — RPDC_TRAP_WARNING

**Hypothesis:** Certain RPDC patterns may indicate horses being entered beyond their
optimal conditions. Monitor for below-baseline outcomes.

| Field | Value |
|---|---|
| Source fields | `class_delta` > 5 (stepped up sharply in class) AND `or_delta_to_win` < -5 (below last winning mark) |
| VP filter | Any VP |
| Purpose | Diagnostic — identify if RPDC negative signals correlate with below-baseline outcomes |
| Minimum sample | 30 closed results |
| Current evidence | Not yet measured — field tracking only from this date |
| Status | DATA_COLLECTION |
| Why not live VP | No evidence yet |

---

## Promotion Framework

### From shadow lane to WATCHLIST

Criteria (each lane may vary — see above):
- n ≥ 30 closed results (minimum)
- SR ≥ baseline + 10pp
- Frame ≥ baseline + 15pp
- Evidence spans ≥ 10 race days

### From WATCHLIST to SHADOW_CANDIDATE

- n ≥ 60 closed results
- SR ≥ 30% sustained over 3+ weeks
- No single day driving the result (check day-by-day consistency)
- Operator review required

### From SHADOW_CANDIDATE to LIVE_DISCUSSION

- n ≥ 100 closed results
- SR ≥ 30% consistent
- Frame ≥ 65% consistent
- Multi-week evidence
- Operator decision required — NOT automatic

### No automatic promotion at any gate

An operator must explicitly review and approve each promotion. The system does not
self-promote shadow lanes to live weights.

---

## What shadow lanes do NOT do

```
CHANGE_LIVE_VP:           NO
CHANGE_FORMULA_WEIGHTS:   NO
CHANGE_ROUTING_RULES:     NO
CHANGE_TELEGRAM_PICKS:    NO
CHANGE_MODEL_WEIGHTS:     NO
WRITE_TO_VELO_VERDICTS:   NO
TRIGGER_STAKING:          NO
```

Shadow lane data is stored in local files only. No Supabase writes required.

---

## Data collection mechanics

After each sigma run, run the tag value audit to update lane statistics:

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/audit_rpdc_tag_value.py
```

Results in: `data/reports/rpdc_tag_value_latest.json` and `.md`

---

## Current lane status summary (as of 2026-05-24)

| Lane | Status | n | SR | Frame | Next gate |
|---|---|---|---|---|---|
| RPDC_IMPROVER (STABLE_WARM) | WATCHLIST | 40 | 30.0% | 62.5% | Frame ≥ 65% at n≥50 |
| RPDC_IMPROVER (CYCLE_RUN_2) | WATCHLIST | 32 | 31.2% | 53.1% | Frame ≥ 65% at n≥50 |
| RPDC_REGRESSION_RISK | INSUFFICIENT_SAMPLE | 9 | — | — | n ≥ 20 |
| RPDC_COURSE_MEMORY | INSUFFICIENT_SAMPLE | 2 | — | — | n ≥ 25 |
| RPDC_DISTANCE_MEMORY | INSUFFICIENT_SAMPLE | 1 | — | — | n ≥ 25 |
| RPDC_CASH_WINDOW | INSUFFICIENT_SAMPLE | ~5 | — | — | n ≥ 20 |
| RPDC_NO_PRIOR_HISTORY | ACTIVE DIAGNOSTIC | 1511 | 20.1% | 46.9% | Permanent |
| RPDC_TRAP_WARNING | DATA_COLLECTION | 0 | — | — | n ≥ 30 |

---

## Classification

```
STATUS:                   RPDC_SHADOW_LANES_V1_DEFINED
LIVE_SCORING_IMPACT:      NONE
FORMULA_CHANGE:           NONE
MODEL_CHANGE:             NONE
OPERATOR_DECISION_NEEDED: YES — for any promotion gate
BEST_CURRENT_SIGNAL:      STABLE_WARM (SR=30.0%, Frame=62.5%, VALUE_POSITIVE)
PRIMARY_BLOCKER:          Low match rate (15%) on sigma — improves as RPDC coverage extends
```

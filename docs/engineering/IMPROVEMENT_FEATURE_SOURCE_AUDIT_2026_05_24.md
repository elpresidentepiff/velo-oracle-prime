# Improvement Model Feature Source Audit — 2026-05-24

**Prepared:** 2026-05-24  
**Trigger:** RPDC Option B confirmed as annotation-only. improvement_score still constant at 0.0872.  
**Classification:** IMPROVEMENT_FEATURE_SOURCE_GAP_CONFIRMED  

---

## Executive Summary

The improvement model (AUC=0.896, 12 features) is currently FEATURE_DEGRADED.
All 241 May24 runners received improvement_score = 0.0872 — the constant output
produced when all inputs take their neutral defaults. The zero-variance kill switch
fires and excludes improvement_score from the active ensemble.

**Root cause:** The RP F_0010 PDF racecard source does NOT provide OFR, RPR, or
horse age. After Racing API decommission (2026-05-14), these three fields are all
missing. Since `or_vs_field`, `rpr_vs_field`, and `age_num` are computed from
OFR/RPR/age, they collapse to 0.0 for every runner. The remaining 9 features come
from the v17 extractor (Racing API form history) which is also dead. All 12 inputs
reduce to the same neutral-default vector, producing a constant output.

**Sensitivity test (2026-05-24):**
- All features at DEFAULTS, OFR/RPR/age=0 → improvement_score = **0.0872** (constant)
- With real OFR/RPR/age variance → improvement_score range **0.0004–0.2094** (range=0.209)
- curr_or_minus_last_win_or from RPDC alone (other features constant) → range **0.012** (minor)

**Verdict: Restoration of or_vs_field / rpr_vs_field / age_num is the highest-priority fix.**

---

## Model Specification

| Attribute | Value |
|---|---|
| Model file | `models/specialist/improvement_model/improvement_model.pkl` |
| AUC | 0.8958 |
| Top-1 accuracy | 65.4% |
| Training rows | 1,448,990 |
| Training cutoff | 2024-01-01 |
| Feature count | 12 |
| Target | `target` (binary win/place signal) |

Missing features during inference → filled with **DEFAULTS** from `v17_feature_extractor.DEFAULTS`.
When OFR/RPR/age are also absent → all 12 inputs are identical for every runner → constant output.

---

## Feature Audit Table

| # | Feature | Default value | Source (original) | Current pipeline value | May24 null rate | May24 variance | Restoration status | Impact rank |
|---|---|---|---|---|---|---|---|---|
| 1 | `or_vs_field` | 0.0 | Racing API standard racecard (OFR field) | 0.0 (no OFR from RP PDF) | 100% | 0 | NEEDS_RACECARD_SOURCE | **HIGH** |
| 2 | `rpr_vs_field` | 0.0 | Racing API standard racecard (RPR field) | 0.0 (no RPR from RP PDF) | 100% | 0 | NEEDS_RACECARD_SOURCE | **HIGH** |
| 3 | `age_num` | 0.0 | Racing API standard racecard (age field) | 0.0 (no age from RP PDF) | 100% | 0 | NEEDS_RACECARD_SOURCE | **HIGH** |
| 4 | `curr_or_minus_last_win_or` | 0.0 | Racing API form history (v17 extractor) | 0.0 (DEFAULT — Racing API dead) | 100% | 0 | DERIVABLE_FROM_RPDC | LOW |
| 5 | `mark_compression_score` | 0.0 | Racing API form history (best OR ever) | 0.0 (DEFAULT) | 100% | 0 | NEEDS_NEW_SOURCE | MEDIUM |
| 6 | `curr_or_minus_best_or` | 0.0 | Racing API form history (best OR ever) | 0.0 (DEFAULT) | 100% | 0 | NEEDS_NEW_SOURCE | MEDIUM |
| 7 | `runs_since_win` | 5.0 | Racing API form history | 5.0 (DEFAULT — constant) | 0% | 0 | NEEDS_NEW_SOURCE | MEDIUM |
| 8 | `runs_since_place` | 2.0 | Racing API form history | 2.0 (DEFAULT — constant) | 0% | 0 | NEEDS_NEW_SOURCE | MEDIUM |
| 9 | `trainer_timing_score` | 0.12 | Racing API trainer stats | 0.12 (DEFAULT — constant) | 0% | 0 | DERIVABLE_FROM_RESULTS | LOW |
| 10 | `distance_fit_score` | 0.33 | Racing API form history | 0.33 (DEFAULT — constant) | 0% | 0 | PARTIALLY_DERIVABLE | LOW |
| 11 | `course_fit_score` | 0.33 | Racing API form history | 0.33 (DEFAULT — constant) | 0% | 0 | PARTIALLY_DERIVABLE | LOW |
| 12 | `release_window_score` | 0.0 | Racing API form + campaign timing | 0.0 (DEFAULT — constant) | 100% | 0 | NOT_RESTORABLE_FROM_RP | LOW |

**Note on null rate:** Features 7–11 show 0% null because they receive DEFAULTS from `v17_feature_extractor.DEFAULTS` before model inference. They are present but constant, not null. Features 1–4, 6, 12 are constant at their default value via the same mechanism.

---

## Restoration Status Definitions

| Status | Meaning |
|---|---|
| `NEEDS_RACECARD_SOURCE` | Value computed from OFR/RPR/age fields in a standard racecard. RP F_0010 PDF does not contain these. Source needed: standard racecard with numerical ratings (Racing API subscription, RP premium API, or alternative data vendor). |
| `DERIVABLE_FROM_RPDC` | Value can be read from `data/rpdc_backfill/rpdc_tags_historical.jsonl` directly or with minor derivation. Pipeline change needed to inject it into feats dict. |
| `NEEDS_NEW_SOURCE` | Value requires Racing API form history (best OR ever, runs count). Could be derived from results files with additional tracking (OR not currently stored per-run in results). |
| `DERIVABLE_FROM_RESULTS` | Value can be approximated from local results files (trainer win rate in 14 days). Not yet implemented. |
| `PARTIALLY_DERIVABLE` | RPDC JSONL has a related flag (course_return_flag, distance_revert_flag) but not the same score. Model received 0.33 default which is better than 0. |
| `NOT_RESTORABLE_FROM_RP` | Requires campaign-level timing vs OR trajectory. No local source has this. |

---

## Impact Analysis

### Sensitivity test results (2026-05-24)

Improvement model tested with increasing feature restoration:

| Path | Features restored | improvement_score range | Kill switch fires? |
|---|---|---|---|
| A — Current (DEFAULTS only) | 0 | 0.0872–0.0872 (constant) | YES |
| B — RPDC only | curr_or_minus_last_win_or | 0.0763–0.0886 (range=0.012) | YES |
| C — Racecard + RPDC | or_vs_field, rpr_vs_field, age_num, curr_or_minus_last_win_or | 0.0004–0.2094 (range=0.209) | NO |
| D — Full formula | all 12 features real | TBD — cannot test (no source for 9 RPDC features) | Expected NO |

**Path C (racecard + RPDC) is achievable once a standard racecard source provides OFR/RPR/age.**

### Feature importance (qualitative from sensitivity)

The model is most sensitive to:
1. `or_vs_field` — horses rated above-field average score significantly higher
2. `rpr_vs_field` — RPR above field is a strong positive signal
3. `age_num` — 3–5 year olds score differently from older horses

These three alone produce a range of 0.209 when varied. RPDC's `curr_or_minus_last_win_or`
alone produces a range of only 0.012 — it is a supporting signal, not the primary driver.

---

## Current Pipeline Path (FEATURE_DEGRADED state)

```
Runner from RP F_0010 PDF racecard
    ├── horse_name: YES
    ├── draw: YES (sometimes)
    ├── weight: YES (sometimes)
    ├── OFR (official_rating): MISSING — RP PDF does not contain ratings
    ├── RPR: MISSING
    └── age: MISSING

_build_live_features():
    or_raw = None → or_vs_field = 0.0  (neutral fallback for ALL runners)
    rpr_raw = None → rpr_vs_field = 0.0
    age = None → age_num = 0.0

v17_feature_extractor.DEFAULTS applied:
    runs_since_win = 5.0 (constant for ALL runners)
    runs_since_place = 2.0 (constant)
    curr_or_minus_last_win_or = 0.0 (constant)
    mark_compression_score = 0.0 (constant)
    course_fit_score = 0.33 (constant)
    distance_fit_score = 0.33 (constant)
    trainer_timing_score = 0.12 (constant)
    release_window_score = 0.0 (constant)

improvement_model.predict_proba([0.0, 0.0, 0.0, 0.0, 5.0, 2.0, 0.12, 0.33, 0.33, 0.0, 0.0, 0.0])
    = 0.0872 (constant — identical vector for all 241 runners)

Zero-variance kill switch: |max - min| < 1e-6 → FIRES
improvement_score EXCLUDED from ensemble.
Active components: ['market_deception_score', 'sqpe_v17']
```

---

## Restoration Requirements

### Immediate (unblocks most variance — HIGH priority)

**Source needed:** Standard racecard with OFR/RPR/age for today's card.

Options:
1. Racing API resubscription (most reliable — provides standard JSON used pre-May-14)
2. RP premium data API (if available — unclear if RP provides numerical ratings via API)
3. Manual racecard data ingestion (Racing Post website scraping — out of scope)

With OFR/RPR/age restored, improvement_score variance would be approximately 0.20 range,
kill switch would NOT fire, and improvement_score would re-enter the ensemble at weight=0.12.

**Code change required in run_prime_today.py / velo_prime_service.py:** None.
The pipeline already computes or_vs_field/rpr_vs_field/age_num correctly from the racecard.
No pipeline change needed — only a racecard data source with these fields.

### Near-term (adds further signal — MEDIUM priority)

**Feature:** `curr_or_minus_last_win_or`

Source: `data/rpdc_backfill/rpdc_tags_historical.jsonl` field `or_delta_to_win`

Pipeline change: Read RPDC memory at scoring time; overwrite DEFAULT (0.0) with actual value for matched horses. 62.7% match rate on May24 proxy.

**Code change:** Add `load_rpdc_memory()` call in `_build_live_features()` or `score_race_velo_prime()`.
Inject `or_delta_to_win` → `curr_or_minus_last_win_or` for matched runners.

Impact: minor (range 0.012 alone). Useful as supporting signal but not primary fix.

### Longer-term (completes formula — MEDIUM priority)

**Features:** `runs_since_win`, `runs_since_place`, `mark_compression_score`, `curr_or_minus_best_or`

Source: local results files — position and OR per run, tracked over time.
`backfill_rpdc_historical_local.py` partially computes these but does not store them.
The RPDC JSONL would need a schema extension to carry runs_since_win/place per run.

**Code change:** Extend RPDC backfill script to track and store position history per run.
Extend JSONL output with `runs_since_win`, `runs_since_place`, `current_or`, `best_or_ever`.
Inject at scoring time via RPDC memory adapter.

### Not restorable from current RP pipeline

**Features:** `release_window_score`, `trainer_timing_score` (at full resolution)

These require campaign-level timing analysis and trainer strike rate over rolling window.
`trainer_timing_score` can be approximated from results files (trainer wins in 14-day window)
but requires additional tracking beyond current pipeline.

`release_window_score` requires campaign OR trajectory — no local source currently captures this.

---

## May25 Gate

Until a standard racecard source with OFR/RPR/age is available:

```
FORMULA_STATUS:          FEATURE_DEGRADED
ACTIVE_COMPONENTS:       ['market_deception_score', 'sqpe_v17']
IMPROVEMENT_SCORE:       EXCLUDED (constant)
FULL_FORMULA_CLAIM:      PROHIBITED
LEARNING_BLOCKED:        YES (degraded card)
```

When a racecard source with OFR/RPR/age is restored:

```
FORMULA_STATUS:          PARTIAL_RESTORE (racecard fields)
ACTIVE_COMPONENTS:       ['sqpe_v17', 'improvement_score', 'market_deception_score']
IMPROVEMENT_WEIGHT:      0.12 (live weight per SQPE_IMPROVEMENT_MDS_V1 profile)
FULL_FORMULA_CLAIM:      PENDING RPDC injection for remaining 8 features
```

---

## Classification

```
FEATURE_SOURCE_GAP_CONFIRMED:       YES
PRIMARY_GAP:                        OFR/RPR/age from standard racecard
SECONDARY_GAP:                      Racing API form history (runs, marks, timing)
RPDC_BRIDGE_STATUS:                 AVAILABLE (Option B) — minor impact alone
RACECARD_RESTORATION_PRIORITY:      HIGH — solves most variance
IMPROVEMENT_SCORE_CONSTANT:         YES — 0.0872 for all runners
KILL_SWITCH_FIRING:                 YES
SUPABASE_CHANGE_NEEDED:             NO — racecard source only
SCORING_FORMULA_CHANGE_NEEDED:      NO — pipeline already handles OFR/RPR correctly
MODEL_CHANGE_NEEDED:                NO
PIPELINE_CODE_CHANGE_NEEDED:        MINOR (RPDC injection for curr_or_minus_last_win_or)
```

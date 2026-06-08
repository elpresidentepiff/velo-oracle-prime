# SQPE V18 Classification Packet

**Status:** UNCLASSIFIED_LOADABLE_MODEL — Council classification required  
**Classification:** `UNCLASSIFIED_LOADABLE_MODEL` / `NOT_WIRED` / `NO_PROMOTION` / `COUNCIL_CLASSIFICATION_REQUIRED` / `EVIDENCE_TRAIL_REQUIRED`  
**Date authored:** 2026-05-23  
**Authority:** El Presidente

---

## Purpose

This document provides the full evidence trail for SQPE V18 to enable the Council to classify it formally and close the governance gap identified in the V14 Architecture Truth Map (`VELO_V14_ARCHITECTURE_TRUTH_MAP.md`, Section 9).

The classification `UNCLASSIFIED_LOADABLE_MODEL` is a holding state only. It does NOT imply the model is under active consideration for promotion.

---

## Physical File Audit

| File | Path | Status |
|---|---|---|
| PKL (model) | `models/sqpe_v18/sqpe_v18.pkl` | PRESENT — loadable |
| Metadata | `models/sqpe_v18/metadata.json` | PRESENT — complete evidence trail |
| Feature importance | `models/sqpe_v18/feature_importance.csv` | PRESENT |
| Training script | `archive/dead_scripts/train_sqpe_v18.py` | PRESENT — ARCHIVED |

**Directory:** `models/sqpe_v18/` — 3 files total.  
**PKL size:** 6.9 MB (GradientBoostingClassifier + IsotonicCalibration pipeline).

---

## Training Evidence

| Field | Value |
|---|---|
| Version | v18.0 |
| Model type | GradientBoostingClassifier + IsotonicCalibration |
| Trained at | 2026-04-05T16:55:56.083847 |
| Source dataset | `data/raceform_v17_features.parquet` |
| n_features | 39 (v17 base 37 + 2 new) |
| Train rows | 1,374,559 |
| Test rows | 241,073 |

---

## Performance Results

| Metric | V18 | V17 Baseline | Delta | Verdict |
|---|---|---|---|---|
| AUC | 0.9372 | 0.9375 | **-0.0003** | NO LIFT |
| Log loss | 0.1834 | — | — | — |
| Top-1 accuracy | 0.7367 | 0.7379 | **-0.0012** | NO LIFT |
| MRR | 0.8486 | 0.8493 | **-0.0007** | NO LIFT |

**Verdict (verbatim from metadata.json):** `"NO LIFT"`

---

## New Features Assessed

| Feature | Importance | Assessment |
|---|---|---|
| `class_delta` | 0.0005 | Negligible — no measurable lift |
| `days_since_run` | 0.0005 | Negligible — no measurable lift |

Both new features rank below all 15 top features. Combined importance = 0.001.

---

## Top 15 Feature Importances (V18 model)

| Rank | Feature | Importance |
|---|---|---|
| 1 | rpr_vs_field | 0.4094 |
| 2 | rpr_num | 0.0974 |
| 3 | log_sp | 0.0674 |
| 4 | implied_prob | 0.0654 |
| 5 | sp_dec | 0.0578 |
| 6 | ts_num | 0.0471 |
| 7 | sp_rank | 0.0428 |
| 8 | or_num | 0.0410 |
| 9 | field_size | 0.0288 |
| 10 | or_vs_field | 0.0247 |
| 11 | wgt_lbs | 0.0246 |
| 12 | class_num | 0.0152 |
| 13 | is_fav | 0.0148 |
| 14 | draw_pct | 0.0081 |
| 15 | draw_num | 0.0078 |

---

## Git History

| Commit | Message |
|---|---|
| `032793f` | `lab(sqpe): v18 results — NO LIFT from days_since_run + class_delta` |

No other commits reference or modify `models/sqpe_v18/`.  
Training script committed to archive, not main src tree.

---

## Runtime Code Reference Audit

```
grep -r "sqpe_v18" --include="*.py" src/ scripts/ app/ workers/
→ ZERO RESULTS
```

SQPE V18 is referenced ONLY in governance documents:

| File | Reference type |
|---|---|
| `docs/engineering/VELO_V14_ARCHITECTURE_TRUTH_MAP.md` | Governance classification |
| `docs/engineering/policy_registry_manifest_v1.json` | Policy entry: SQPE_V18_CLASSIFICATION |
| `docs/engineering/VELO_V14_COUNCIL_REVIEW_PACKET.md` | Open item 1A |
| `CURRENT_RUNTIME_TRUTH.md` | Noted as unclassified loadable |
| `archive/dead_scripts/train_sqpe_v18.py` | Archived training script |

**It is NOT imported by any live scoring path. It is NOT wired to the prediction pipeline.**

---

## Comparison to Live Model (SQPE V17)

| Dimension | SQPE V17 (LIVE) | SQPE V18 (UNCLASSIFIED) |
|---|---|---|
| Trained at | 2026-03-16 | 2026-04-05 |
| Source | `data/raceform_clean.parquet` | `data/raceform_v17_features.parquet` |
| n_features | 37 | 39 |
| AUC | 0.9400 | 0.9372 |
| Top-1 | 0.7370 | 0.7367 |
| Verdict | LIVE (active) | NO LIFT — lab experiment |

V17 outperforms V18 on all reported metrics. V17 trained on a larger dataset (253,582 test rows vs 241,073).

---

## What Does NOT Exist

- No MLflow tracking entry
- No checksum file
- No test suite referencing sqpe_v18
- No evidence corpus results from V18 predictions
- No routing weight or policy referencing V18

---

## Hard Rules (Current)

```
DO NOT delete models/sqpe_v18/ without Council decision
DO NOT wire sqpe_v18.pkl to any runtime path
DO NOT use V18 in any promotion evidence
DO NOT treat V18 predictions as live
DO NOT evaluate V18 as an upgrade candidate without Council sign-off
```

---

## Recommended Council Action

Based on the full evidence trail, the Council should formally close V18 as a completed lab experiment with no promotion pathway:

```
RECOMMENDED_CLASSIFICATION: LAB_EXPERIMENT_COMPLETED_NO_LIFT
RECOMMENDED_STATUS: ARCHIVE_ELIGIBLE
RECOMMENDED_ACTION: Move to archive/models_evaluated/ after Council vote
EVIDENCE_VERDICT: COMPLETE — no further investigation needed
PROMOTION_PATH: NONE
```

The `"NO LIFT"` verdict is conclusive. The new features (`class_delta`, `days_since_run`) contribute 0.001 combined importance — below noise threshold. V17 is superior on all metrics. This is a closed question pending only formal Council classification.

---

```
SQPE_V18_CLASSIFICATION_PACKET_STATUS: COMPLETE
EVIDENCE_TRAIL: COMPLETE
CURRENT_CLASSIFICATION: UNCLASSIFIED_LOADABLE_MODEL / NOT_WIRED / NO_PROMOTION
COUNCIL_ACTION_REQUIRED: YES — formal close as LAB_EXPERIMENT_COMPLETED_NO_LIFT
ARCHIVE_ELIGIBLE: YES — after Council vote
```

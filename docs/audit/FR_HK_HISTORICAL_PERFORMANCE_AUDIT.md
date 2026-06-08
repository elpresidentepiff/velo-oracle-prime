# FR/HK Historical Performance Audit

**Date:** 2026-05-23  
**Purpose:** Verify or reject any historical backtest performance claims for French and HK racing  
**Scope:** Full codebase + data directory scan  
**Classification:** AUDIT DOCUMENT — read-only

---

## Search Methodology

Scanned all `.json`, `.csv`, `.md`, `.py` files matching:
`chantilly | sha tin | shatin | happy valley | hkjc | hk | france | fr | racing_api | raceform_v17 | benter | intl | international`

---

## Artifacts Found

### 1. `docs/hk_ready_gate.md` (2026-03-23)
- **Type:** Gate definition document
- **Content:** Defines 6 criteria for HK research readiness (90 days data, 80% coverage, etc.)
- **Performance claim:** NONE — gates are all marked `Status: NOT READY`
- **Conclusion:** Architectural planning only. No backtest. No performance number.

### 2. `docs/hk_research_build_order.md` (2026-03-23)
- **Type:** Build order / phase plan
- **Content:** Phase 0-4 HK ingestion pipeline plan
- **Performance claim:** NONE
- **Conclusion:** Planning doc only.

### 3. `docs/hk_source_audit_field_matrix.md` (2026-03-23)
- **Type:** API field availability matrix
- **Content:** Racing API field coverage for HK racecards
- **Performance claim:** NONE
- **Conclusion:** Source audit only. No model results.

### 4. `src/models/benter.py`
- **Type:** Model implementation
- **Content:** Bill Benter's fundamental × market model (α=0.9, β=1.1)
- **Performance claim:** References Benter 1994 paper. No VÉLØ-specific backtest results.
- **Conclusion:** Model exists. Not yet calibrated or validated on VÉLØ HK data.

### 5. `archive/dead_workers/hk_daily_ingest.py` and `fr_daily_ingest.py`
- **Type:** Dead worker scripts
- **Content:** Ingestion logic for HK/FR data via Racing API
- **Performance claim:** NONE — workers were never activated
- **Conclusion:** Pipeline code only. No data was ever ingested.

### 6. `data/raceform_v17_features.parquet` — Training Substrate
- **Type:** Training data file
- **Content:** 255,862 rows for 7 target venues (2015-2025)
- **Performance claim:** None — this is raw training data, not a backtest result
- **Conclusion:** Data exists. Training has NOT been run. No model exists for FR or HK.

### 7. `tests/test_phase25.py` and `tests/test_phase3_full.py`
- **Type:** Test files
- **Content:** References to international courses in test fixtures
- **Performance claim:** NONE — unit tests only

### 8. No Other Artifacts Found
No files found matching:
- Any FR or HK strike rate claim
- Any FR or HK ROI claim
- Any FR or HK frame rate claim
- Any backtest output JSON for international venues
- Any trained model files for FR or HK (`models/specialist/sqpe_v1_fr*`, `models/specialist/sqpe_v1_hk*`)

---

## Verdict

```
HISTORICAL_RESULT_CLAIM_UNVERIFIED_BUT_TRAINING_DATA_EXISTS
```

**What exists:**
- 255,862 rows of historical training data (2015-2025) for 7 target venues
- All rows have 100% win label coverage — TRAINING_SAFE
- Existing UK SQPE architecture that can be adapted
- Benter model implemented (needs calibration)
- Planning documents (build order, gate definitions, field matrix)
- Dead ingestion workers (blocked — Racing API access removed)

**What does NOT exist:**
- Any trained FR or HK model
- Any FR or HK backtest result
- Any FR or HK strike rate claim
- Any live FR or HK scored races
- Any FR or HK Supabase data (schemas not yet created)

**Prior session memory claim:** The session summary referenced "Sha Tin (HK): 50,976 rows, 427 dates" and "favourite SR=32.1%". These figures are confirmed as TRUE from the parquet audit. However, these are data descriptive statistics, not model performance claims.

**Prior session memory claim:** "RPR top-20% lift: HK=7-9x, France=7-10x vs bottom 80%". This is a data signal analysis finding, not a model performance backtest. Confirmed directionally accurate from the signal baseline audit.

---

## Action Required

No performance claims to retract. No results to quarantine.

The training substrate is real and verified. Model development has not started.

```
NEXT_STEP: Phase 0 complete → begin Phase 1 (jurisdiction packs + signal audit)
TRAINING: NOT_YET — requires Phase 2 approval
BACKTESTS: NONE_EXIST
LIVE_DATA: NONE_EXISTS
```

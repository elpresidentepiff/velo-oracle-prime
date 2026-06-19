# MOT-01 — Model Operational Truth + Inference Parity Audit
**Date:** 2026-06-18  
**Status:** COMPLETE  
**Classification:** MODEL_TRUTH_BREACH | SP_INFERENCE_MISMATCH_CONFIRMED | RPR_DOMINANCE_OVERDEPENDENCE_CONFIRMED

---

## 1. Feature Truth — Training vs Morning Inference

### SQPE v17 Trained Features (37 total)

| Feature Family | Features | Importance | Available at inference? | Status |
|---|---|---|---|---|
| **RPR / ratings** | rpr_vs_field, rpr_num, ts_num, or_num, or_vs_field | ~52% combined | ✓ | REAL — see caveat below |
| **Price / SP** | sp_dec, log_sp, implied_prob, sp_rank, is_fav | ~25% combined | ✗ | ARTIFICIAL (all default 10.0) |
| **Race context** | dist_f, going_code, is_aw, class_num, field_size, draw_num, draw_pct, age_num, wgt_lbs | ~10% | ✓ | REAL |
| **Market signals** | mark_compression_score, odds_resilience_score, odds_contraction_score | ~5% | ✗ | NULL at inference |
| **Specialist/intent** | decoy_support_flag, setup_run_flag, cash_run_flag, release_window_score, course_fit_score, going_fit_score, distance_fit_score, quiet_run_score, trainer_timing_score, jockey_switch_intent | ~8% | PARTIAL | Most 0% populated in snapshots |
| **History flags** | runs_since_win, runs_since_place, runs_since_mkt_support, curr_or_minus_last_win_or, curr_or_minus_best_or | ~5% | PARTIAL | Depends on RPDC run |

### SP INFERENCE MISMATCH — CONFIRMED

**Verdict: SP_TRAIN_INFERENCE_MISMATCH_CONFIRMED**

`_build_live_features()` (app/services/velo_prime_service.py:85) reads:
```python
odds = _safe(runner.get("best_odds_decimal"))
sp_dec = odds if odds > 1.0 else 10.0   # FALLBACK: 10.0
```

**Both RP injection AND LOCAL_JSON_FALLBACK return `best_odds_decimal = None`:**
- RP injection has `forecast_odds` (probability format, e.g., 0.333) and `rp_morning_price` — wrong key, never read
- LOCAL_JSON_FALLBACK has `odds` (decimal format, e.g., 1.1) — wrong key, never read
- Result: **all horses are scored as 9/1 (sp_dec=10.0) at morning inference, regardless of actual market position**

SP-related features at inference: `sp_dec=10.0, log_sp=2.303, implied_prob=0.1, sp_rank=field_size, is_fav=0.0` for every single runner.

### RPR DOMINANCE — THE FULL EXPLANATION

**Verdict: RPR_DEPENDENCE_CONFIRMED**

From SQPE v18 (same feature family as v17, shared metadata):
- `rpr_vs_field`: **40.9%** importance — single most important feature
- `rpr_num`: 9.7%
- Total RPR family: **~50%**

**RPR coverage comparison:**

| Source | RPR Coverage | Effect on SQPE |
|---|---|---|
| LOCAL_JSON_FALLBACK (Jun 17) | 52% | ~50% of horses have rpr_vs_field=0.0 (neutral) → SQPE under-fires |
| RP_MERGED_CLEAN (Jun 18) | 100% | Every horse has real RPR → SQPE sees full dominance signal |

**The Jun 18 over-firing is explained entirely by the intersection of:**
1. All horses artificially at sp_dec=10.0 (SP missing)
2. All horses now have RPR (100% coverage from RP)
3. When RPR dominance is extreme (Celestra +24 vs field avg, Heddon Street +30 vs field avg) and SP=10.0 (looks like hidden value), SQPE fires at 0.87-0.91

**The Jun 17 under-firing is explained by:**
1. Same artificial sp_dec=10.0 (LOCAL_JSON also missing best_odds_decimal)
2. Only 52% RPR coverage → half the field has rpr_vs_field=0.0 → dominance signal diluted
3. SQPE max = 0.23 (no extreme cases because field comparison is incomplete)

### Feature Family Decomposition

```
SQPE v17 Signal Composition (from v18 importances, shared feature set):
  RPR family:         ~50%   [rpr_vs_field=40.9%, rpr_num=9.7%]
  SP/price family:    ~24%   [log_sp=6.7%, implied_prob=6.5%, sp_dec=5.8%, sp_rank=4.3%, is_fav=1.5%]
  Race context:       ~10%   [field_size, wgt_lbs, class_num, dist_f, etc.]
  OR/class signals:   ~7%    [or_vs_field, or_num]
  Draw/age:           ~4%    [draw_pct, draw_num, age_num]
  Specialist/intent:  ~5%    [mark_compression_score, quiet_run_score, etc.]
```

**At morning inference, the effective signal composition is:**
```
  RPR family:         ~65%   [SP gone → RPR fills the void]
  Race context:       ~15%   [remaining real features]
  OR/class signals:   ~12%
  Specialist/intent:  ~8%
  SP family:          ~0%    [all artificial → zero discrimination]
```

---

## 2. NDS Dry-Run — Problem Race Analysis

### NDS Status
`src/intelligence/nds.py` — **FULLY BUILT, ZERO CALLERS** (confirmed via GitNexus graph)

NDS detects 7 narrative types: HYPE_FAVORITE, RECENCY_BIAS, FALSE_FORM, BREEDING_BIAS, CONNECTION_BIAS, DUE_TO_WIN, HOT_STREAK

### Problem Race Assessment (manual, NDS not yet wired)

| Horse | Jun 18 VP | SQPE | NDS Narrative (manual assessment) | Would suppress? |
|---|---|---|---|---|
| Celestra (Yarmouth 3:50) | 0.791 | 0.870 | **FALSE_FORM** — RPR 94 earned in better class; form "22-23" = place machine not win machine | YES |
| Heddon Street (Lingfield 8:10) | 0.916 | 0.845 | **RECENCY_BIAS** — one good debut win; second most recently; hype from press tip consensus | YES |
| Laravie (Yarmouth 1:30) | 0.827 | 0.585 | Possibly legitimate — 3-runner race, form "495111", RPR 78 vs 75/73 | MAYBE NOT — this may have been correct |
| Spirit Dreamer (Southwell 7:00) | 0.755 | 0.498 | Unclear without deeper form reading | INCONCLUSIVE |

### NDS Dry-Run Verdict
`NDS_SUPPRESSOR_DRY_RUN: CANDIDATE — pending wiring`

Manual assessment suggests NDS would correctly suppress at least 2 of the 4 extreme VP cases. Full wiring required to test algorithmically.

---

## 3. Chain Inventory

| Component | File | Status | Last Called From |
|---|---|---|---|
| pace_chain | app/intelligence/chains/pace_chain.py | BUILT_NOT_CALLED_BY_PRODUCTION | tests/test_phase3_full.py + API endpoint only |
| narrative_chain | app/intelligence/chains/narrative_chain.py | BUILT_NOT_CALLED_BY_PRODUCTION | tests + API endpoint only |
| market_chain | app/intelligence/chains/market_chain.py | BUILT_NOT_CALLED_BY_PRODUCTION | tests + API endpoint only |
| async_scheduler | app/optim/async_scheduler.py | TEST_ONLY | tests/test_phase3_full.py only |
| FastAPI intel endpoints | app/api/v1/intel.py | BUILT_CALLABLE | No automated caller; API routes exist |
| NDS | src/intelligence/nds.py | BUILT_ZERO_CALLERS | Never imported anywhere |
| Railway cron (run_prime_today.py) | scripts/ops/run_prime_today.py | LIVE | Calls score_race_velo_prime only — chains ignored |

**Chain audit verdict:** All three intelligence chains (pace, narrative, market) plus NDS are **DOCS_OVERCLAIM** if described as part of the live system. They exist. They work. They are not connected to daily scoring.

---

## 4. Documentation Corrections Required

### CLAUDE.md Overclaims to Fix

| Claim | Current State | Corrected Statement |
|---|---|---|
| "TIE v9 exists on disk" | Confirmed: 126-byte stub, cannot be loaded | TIE v9 pkl = stub/placeholder, NOT operational |
| Longshot v6 = METADATA_ONLY | Correct already | No change needed |
| Overlay v5 = METADATA_ONLY | Correct already | No change needed |
| sqpe_v14 = METADATA_ONLY | Correct already | No change needed |
| NDS / narrative chain | Not mentioned | Should state: BUILT_NOT_CALLED_BY_PRODUCTION |
| Pace / market chains | Not mentioned | Should state: BUILT_NOT_CALLED_BY_PRODUCTION |
| SQPE v17 description | "AUC=0.94" | True, but must add: "RPR-dominant (~50% feature importance), SP features are artificial at inference (all runners default to sp_dec=10.0 due to best_odds_decimal not populated by RP injection)" |

---

## 5. Classification Summary

```
SP_TRAIN_INFERENCE_MISMATCH_CONFIRMED
  → best_odds_decimal never populated by any racecard source
  → Service defaults ALL horses to sp_dec=10.0 at scoring time
  → Root fix: map forecast_odds/rp_morning_price to best_odds_decimal in injection parser

RPR_DEPENDENCE_CONFIRMED
  → rpr_vs_field = 40.9% of SQPE v17/v18 signal
  → With SP artificial, effective RPR weight at inference ≈ 65%
  → Root fix: RPR dominance cap when SP is missing

NDS_UNWIRED_CRITICAL
  → Fully coded narrative suppressor exists in src/intelligence/nds.py
  → Zero callers in entire codebase
  → Root fix: wire as report-only first, then suppressor gate

INTELLIGENCE_CHAINS_UNWIRED
  → pace_chain, narrative_chain, market_chain: TEST_ONLY
  → async_scheduler: TEST_ONLY
  → Root fix: wire to run_prime_today.py after SP fix is deployed

DOCS_OPERATIONAL_OVERCLAIM
  → TIE v9 stub misrepresented as model
  → Chains implied live when they are test/API-only
  → Root fix: correct CLAUDE.md and whitepaper claims

MODEL_TRUTH_BREACH (no live fix until full audit closure)
  → System produces inflated VP due to SP/RPR interaction
  → NDS exists but is not suppressing
  → Priority fix order: SP field mapping → RPR cap → NDS wire-in
```

---

## Fix Architecture (Phase Order)

```
Phase 1 (plumbing): Map forecast_odds → best_odds_decimal in injection parser
  → Immediate: eliminates artificial sp_dec=10.0 universal default
  → Unlocks: SP features become real → SQPE regains price calibration
  → Risk: LOW — no model change, only data pipeline

Phase 2 (RPR guard): Add rpr_vs_field dominance cap in run_prime_today.py
  → When rpr_vs_field > threshold AND sp data missing → confidence penalty
  → Prevents extreme SQPE scores without real price calibration

Phase 3 (NDS): Wire src/intelligence/nds.py as report-only layer
  → Run against all scored races; log NDS signals
  → Gate: if NDS fires FALSE_FORM or RECENCY_BIAS → flag for suppressor testing

Phase 4 (suppressor): After 30-day NDS dry-run evidence, wire as VP suppressor
  → High-RPR-dominance + NDS narrative flag → VP penalty

Phase 5 (chains): Wire pace/narrative/market chains into run_prime_today
  → Only after phases 1-3 are stable
```

**No VFU-13 until Phase 1 complete.**  
**No live suppressor until Phase 3 dry-run is evidenced.**

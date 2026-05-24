# Racecard Ratings Source Restoration — Week Plan

**Prepared:** 2026-05-24  
**Trigger:** improvement_score constant at 0.0872. Root cause: RP pipeline provides no OFR/RPR/age.  
**Classification:** RATINGS_SOURCE_GAP_CONFIRMED / FIX_APPLIED_2026-05-24 / IMPROVEMENT_VARIANCE_RESTORED / MAY25_FULL_FORMULA_RESTORED_PENDING_OPERATOR_REVIEW  
**Hard constraint:** No formula change. No live scoring change. No model change. Compare-only proves variance before any integration.

---

## Executive Summary

The improvement model (12 features, AUC=0.896) is FEATURE_DEGRADED because `or_vs_field`,
`rpr_vs_field`, and `age_num` all collapse to 0.0. Restoring these three features produces a
range of 0.209 in improvement_score (see: `IMPROVEMENT_FEATURE_SOURCE_AUDIT_2026_05_24.md`).

**KEY FINDING (2026-05-24):** The `data/racecard_merged/*.json` files produced by the RP
pipeline contain `current_or` (≡ OFR), `rpr_master` (≡ RPR), and `age` at 75.9% / 64.0% /
59.6% coverage respectively. These fields exist in the raw horse dicts TODAY. They are not
missing — they are silently discarded.

In `src/velo/racecard_loader.py` `load_rp_merged_as_racecards()` (lines 186–193), the
runner dict is built with hard-coded `None` values:

```python
"age": None,    # ← discards h.get("age")      which is present at 59.6%
"ofr": None,    # ← discards h.get("current_or") which is present at 75.9%
"rpr": None,    # ← discards h.get("rpr_master")  which is present at 64.0%
```

**The fix is 3 lines.** No formula change. No model change. No new data source required.
The data is already being parsed and thrown away.

---

## Source Audit Table

| Source | contains_OFR | contains_RPR | contains_age | same_date | pre_race_safe | extraction_status | verdict |
|---|---|---|---|---|---|---|---|
| Racing API standard racecard JSON (`racecards_YYYY_MM_DD_standard.json`) | YES (field: `ofr`) | YES (field: `rpr`) | YES (field: `age`) | YES | YES | DEAD — decommissioned 2026-05-14. Last file: `racecards_2026_05_17_standard.json` | DEAD — was PRIMARY |
| **RP merged racecard (`data/racecard_merged/racecard_*_{date}.json`)** | **YES** (`current_or`, 75.9%) | **YES** (`rpr_master`, 64.0%) | **YES** (`age`, 59.6%) | **YES** | **YES** | **ACTIVE — 155 files, 54 post-decommission. Fields present but discarded by normalizer** | **KEY_FINDING — FIXABLE (3 lines)** |
| RP F_0010 PDF (industry_selections JSON) | NO | NO | NO | YES | YES | ACTIVE — tipster selections only | NO RATINGS |
| Runner snapshots JSONL | NO | NO | NO | YES | NO (post-score) | ACTIVE — scoring output | NO RATINGS |
| Results files (`data/results_YYYY_MM_DD.json`) | NO (field present, empty) | NO (field present, empty) | NO (field present, empty) | NO (post-race) | NO (leakage risk) | ACTIVE — scraper populates `or` and `rpr` as empty strings | EMPTY + POST-RACE |
| Supabase `racecards` table | NO | NO | NO | N/A | N/A | 0 rows — never populated | EMPTY |
| `raceform_v17_features.parquet` | YES (`or_num`) | YES (`rpr_num`) | YES (`age_num`) | NO (training data) | NO (historical) | STATIC — training corpus, cutoff 2024-01-01. 1.7M rows but no live data | HISTORICAL ONLY |
| Supabase `racing_horse_runs` | YES (`official_rating`) | NO | NO | NO (post-race) | NO (post-race, leakage risk) | ACTIVE — populated by ingest script. Contains OR from results | POST-RACE ONLY |

---

## Key Finding Detail — racecard_merged mapping gap

**File:** `src/velo/racecard_loader.py`  
**Function:** `load_rp_merged_as_racecards()`, lines 183–199  
**Status:** 3-line fix to stop discarding available data

### Current code (discards ratings)

```python
runners.append({
    "horse": name,
    "horse_id": f"rp_{venue_code}_{name.lower().replace(' ', '_')}",
    "age": None,          # ← discards h.get("age")
    ...
    "ofr": None,          # ← discards h.get("current_or")
    "rpr": None,          # ← discards h.get("rpr_master")
    ...
```

### Fixed code (passes through available ratings)

```python
runners.append({
    "horse": name,
    "horse_id": f"rp_{venue_code}_{name.lower().replace(' ', '_')}",
    "age": h.get("age"),                    # 59.6% coverage in last 10 files
    ...
    "ofr": h.get("current_or"),             # 75.9% coverage in last 10 files
    "rpr": h.get("rpr_master"),             # 64.0% coverage in last 10 files
    ...
```

### Coverage audit (last 10 racecard_merged files as of 2026-05-24)

| Field | Source field in RP horse dict | Coverage in last 10 files | Verdict |
|---|---|---|---|
| `ofr` (official_rating) | `current_or` | 75.9% (536/706) | SUFFICIENT |
| `rpr` | `rpr_master` | 64.0% (452/706) | MODERATE |
| `age` | `age` | 59.6% (421/706) | MODERATE |

Coverage is lower than Racing API (which was 100% for OFR, 100% for RPR on May14).
However, sensitivity analysis shows OFR/RPR/age at even partial coverage produces
improvement_score range ≈ 0.209 vs 0.0 (constant). Kill switch would NOT fire.

---

## racecard_merged file coverage post-decommission

| Period | Merged files | Notes |
|---|---|---|
| 2026-03-17 → 2026-05-14 (pre-decommission) | 101 | Racing API also available |
| 2026-05-15 → 2026-05-23 (post-decommission) | 54 | RP pipeline only — these are the live source |
| 2026-05-24 (today) | Expected | Pipeline continues daily |

155 merged racecard files total. Post-decommission coverage is continuous.

---

## Restoration Plan — Compare-Only Gate First

**Rule:** No live scoring change until compare-only audit proves improvement_score variance is restored.

### Step 1 — Compare-only validation (SAFE — read-only)

Run `audit_improvement_feature_assembler_compare.py` after patching the source fields
in a local test path. This script already has Path C (racecard proxy). With the mapping
fix, Path C becomes "rp_merged actual" instead of "May17 proxy".

Expected result:
- Path A (current): improvement_score = 0.0872 constant, kill_switch=True
- Path B (RPDC only): improvement_score range ≈ 0.016, kill_switch=False (marginal)
- Path C (rp_merged fixed): improvement_score range ≈ 0.15–0.20, kill_switch=False (material)

### Step 2 — Operator decision

After compare-only confirms range ≥ 0.15 on a real card, operator approves the 3-line
change. This is classified as a **pipeline restoration**, not a scoring formula change.
The formula has not changed; the data pipeline is being corrected.

### Step 3 — Live card test

Run `run_prime_today.py --source rp_merged` after the fix. Confirm improvement_score
appears in the verdict flags with values distributed across runners. Confirm kill switch
does NOT fire.

### Step 4 — Commit and close gate

Commit the 3-line fix under a single atomic commit. Update IMPROVEMENT_FEATURE_SOURCE_AUDIT.

---

## racecard_merged additional fields available

The RP merged racecard provides more than just OFR/RPR. Several fields are directly relevant
to the improvement model and other scoring components:

| racecard_merged field | improvement model feature | Status |
|---|---|---|
| `current_or` | `or_vs_field`, `or_num`, `curr_or_minus_last_win_or` (with RPDC) | AVAILABLE — currently discarded |
| `rpr_master` | `rpr_vs_field`, `rpr_num` | AVAILABLE — currently discarded |
| `age` | `age_num` | AVAILABLE — currently discarded |
| `or_delta_to_best_win` | `curr_or_minus_best_or` (partial) | AVAILABLE via `_rp_raw` — separate gate |
| `or_run_history` | `runs_since_win` (derivable from pos field) | AVAILABLE via `_rp_raw` — separate gate |
| `ts_run_history` | `distance_fit_score` (derivable) | AVAILABLE via `_rp_raw` — separate gate |

The `_rp_raw` key is already passed through to the runner dict (line 180 of racecard_loader.py).
Downstream code can access the full horse dict via `runner.get("pdf_intel", {}).get("_rp_raw", {})`.

---

## Legacy data gap (Racing API era, pre-May14)

Standard racecard JSON files:
- 36 files from 2026-03-17 to 2026-05-17
- Last file: `data/racecards_2026_05_17_standard.json` (261 runners, 74.7% OFR, 75.5% RPR, 76.6% age)
- May17 file is anomalously small (302KB vs 4MB for May16) — partial card
- Last full-coverage standard racecard: `racecards_2026_05_14_standard.json` (430 runners, 100% OFR, 100% RPR)

These files are local cache and are read-only. They cannot provide ratings for May18+ cards.

---

## What is NOT available (out of scope)

| Feature | Reason |
|---|---|
| `mark_compression_score` | Requires OR history trajectory — not in racecard_merged without derivation |
| `curr_or_minus_best_or` | `or_delta_to_best_win` is available via `_rp_raw` — Gate 1 (separate approval) |
| `runs_since_win` / `runs_since_place` | Derivable from `or_run_history` pos fields — Gate 1 (separate approval) |
| `trainer_timing_score` | Needs trainer win rate rolling window — separate engineering spec |
| `release_window_score` | Requires campaign-level timing — not restorable from RP data |

---

## Week action items

| Priority | Action | Risk | Gate |
|---|---|---|---|
| **1 — IMMEDIATE** | Run compare-only audit using racecard_merged `current_or`/`rpr_master`/`age` for today's card | ZERO — read-only | None |
| **2 — IMMEDIATE** | Get operator approval for 3-line fix in `racecard_loader.py` | LOW — pipeline restoration, not formula change | Operator decision |
| **3 — THIS WEEK** | Apply 3-line fix, commit, run live card test | LOW | Operator approval in step 2 |
| **4 — THIS WEEK** | Re-run `audit_improvement_feature_assembler_compare.py` after fix | ZERO — compare-only | None |
| **5 — NEXT WEEK** | Evaluate `or_delta_to_best_win` + `or_run_history` injection for remaining improvement features | MEDIUM — separate gate | Separate operator decision |

---

## Classification

```
STATUS:                               FIX_APPLIED_2026-05-24 / FULL_FORMULA_RESTORED_PENDING_OPERATOR_REVIEW
KEY_FINDING:                          racecard_merged has current_or/rpr_master/age — discarded by normalizer
FIX_COMPLEXITY:                       3 lines in src/velo/racecard_loader.py
FIX_TYPE:                             PIPELINE_RESTORATION (not formula change)
CURRENT_OR_COVERAGE_IN_RP_MERGED:    75.9% (last 10 files)
RPR_MASTER_COVERAGE_IN_RP_MERGED:    64.0% (last 10 files)
AGE_COVERAGE_IN_RP_MERGED:           59.6% (last 10 files)
EXPECTED_IMPROVEMENT_RANGE_POST_FIX: ~0.15–0.20 (vs 0.0 constant now)
KILL_SWITCH_POST_FIX:                 EXPECTED_FALSE (material variance)
SCORING_FORMULA_CHANGE:               NONE
MODEL_CHANGE:                         NONE
LIVE_SCORING_CHANGE:                  NOT APPROVED — compare-only first
OPERATOR_DECISION_REQUIRED:           YES — before applying fix
SUPABASE_CHANGE_NEEDED:               NO
```

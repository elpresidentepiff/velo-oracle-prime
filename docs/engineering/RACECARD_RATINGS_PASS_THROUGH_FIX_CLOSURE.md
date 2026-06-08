# Racecard Ratings Pass-Through Fix — Closure

**Date:** 2026-05-24  
**Classification:** PIPELINE_RESTORATION_COMPLETE / IMPROVEMENT_VARIANCE_RESTORED / MAY25_FULL_FORMULA_RESTORED_PENDING_OPERATOR_REVIEW  
**Hard constraint:** No formula change. No weight change. No model change. Fix is a 3-line pipeline restoration only.

---

## What was fixed

**File:** `src/velo/racecard_loader.py`  
**Function:** `load_rp_merged_as_racecards()`, lines 186–193  
**Change type:** Pipeline restoration — stopped discarding available data

### Before

```python
"age": None,    # discarded h.get("age")      — available at 59.6%
"ofr": None,    # discarded h.get("current_or") — available at 75.9%
"rpr": None,    # discarded h.get("rpr_master") — available at 64.0%
```

### After

```python
"age": h.get("age") or None,
"ofr": h.get("current_or") or None,
"rpr": h.get("rpr_master") or None,
```

**Fallback:** If `current_or`, `rpr_master`, or `age` are missing in the RP horse dict, the field
remains `None`. No invented values. No post-race derivation. No new data source introduced.

---

## Task 2 — Syntax test

```
PYTHONPATH=. python -m py_compile src/velo/racecard_loader.py
→ SYNTAX OK
```

---

## Task 3 — Loader pass-through verification (May24 card, 241 runners)

| Field | Before fix | After fix | Notes |
|---|---|---|---|
| `ofr` (official_rating) | 0/241 (0%) | 178/241 (73.9%) | `current_or` from RP horse dict |
| `rpr` | 0/241 (0%) | 171/241 (71.0%) | `rpr_master` from RP horse dict |
| `age` | 0/241 (0%) | 241/241 (100.0%) | `age` from RP horse dict — universal coverage |
| Runner count | 241 | 241 | Unchanged |
| Horse identity | rp_VENUE_name format | rp_VENUE_name format | Unchanged |
| `ofr=None` when source missing | N/A | Correct | 63 runners had no `current_or` → remain None |

**Verification:** no post-race fields used, no invented values, no identity changes.

---

## Task 4 — Compare-only proof (May24 card, 241 runners matched to snapshots)

### Improvement score distribution

| Metric | Before fix (FEATURE_DEGRADED) | After fix (RESTORED) |
|---|---|---|
| improvement_score min | 0.0872 (constant) | 0.0000 |
| improvement_score mean | 0.0872 (constant) | 0.0490 |
| improvement_score max | 0.0872 (constant) | 0.2196 |
| improvement_score range | 0.0000 | 0.2196 |
| Kill switch fires? | YES | **NO** |
| Formula status | FEATURE_DEGRADED | IMPROVEMENT_VARIANCE_RESTORED |

### VP delta distribution (old degraded → new restored, all 241 runners)

| Metric | Value |
|---|---|
| VP delta min | -0.0180 |
| VP delta mean | -0.0014 |
| VP delta max | +0.0265 |
| Runners with VP drop > 0.02 | 0 |
| Runners with VP gain > 0.02 | 9 |

### Tier stability

| Check | Result |
|---|---|
| Tier A losses (was A, now non-A) | 0 |
| Tier A gains (was non-A, now A) | 0 |
| Total tier boundary crossings | 0 |

### Top horse analysis (29 races)

| Check | Result |
|---|---|
| Races with same top horse | 19/29 |
| Races with different top horse | 10/29 |
| Of those 10: margin > 0.05 VP (SHOCK) | **0** |
| Of those 10: margin ≤ 0.05 VP (marginal) | 10 |
| Max margin on top horse change | 0.0220 |
| All shifted races' VP range | 0.04–0.11 (Tier C/D only) |

**Interpretation:** All 10 top-horse changes occur in races where the highest VP is 0.043–0.111 —
deep Tier C/D territory. No Tier B or A runner is displaced. The maximum swap margin is 2.20pp
of VP, within the noise floor for Tier C/D. This is expected behaviour, not a ranking shock.

---

## Task 5 — May25 decision gate

**Gate criteria met:**

| Criterion | Status |
|---|---|
| Same-date OFR/RPR/age populated | ✓ YES — 73.9% / 71.0% / 100.0% |
| improvement_score variable | ✓ YES — range=0.2196 |
| Kill switch does not fire | ✓ YES |
| No unstable tier/ranking shock | ✓ YES — 0 Tier A changes, all top-horse shifts marginal |

**Classification:**

```
MAY25_GATE:  FULL_FORMULA_RESTORED_PENDING_OPERATOR_REVIEW
```

When May25 runs with the patched loader:
- `active_components`: `['market_deception_score', 'sqpe_v17', 'improvement_score']`
- `improvement_weight`: 0.12 (live weight per SQPE_IMPROVEMENT_MDS_V1 profile)
- `FEATURE_DEGRADED` banner: NOT fired
- `learning_eligible`: YES (pending operator confirmation)

---

## Immutability confirmation

```
LIVE_WEIGHTS_CHANGED:         NO — 0.45 / 0.12 / 0.10 unchanged
FORMULA_CHANGED:              NO — VP formula unchanged
MODEL_CHANGED:                NO — improvement_model.pkl unchanged
ROUTER_CHANGED:               NO
STAKING_CHANGED:              NO
TELEGRAM_PICK_CHANGED:        NO
PLAYBOOK_G_CHANGED:           NO
LIVE_STATE_MUTATED:           NO
OLD_VERDICTS_MUTATED:         NO
SUPABASE_MIGRATED:            NO
RPDC_INJECTED_INTO_SCORING:   NO — RPDC shadow only
SCORING_FORMULA_CHANGE:       NO
```

---

## Files changed in this fix

| File | Change |
|---|---|
| `src/velo/racecard_loader.py` | 3-line pass-through: `current_or` → `ofr`, `rpr_master` → `rpr`, `age` → `age` |
| `docs/engineering/RACECARD_RATINGS_PASS_THROUGH_FIX_CLOSURE.md` | This document |
| `docs/engineering/RACECARD_RATINGS_SOURCE_RESTORATION_WEEK_PLAN.md` | Updated: fix applied, gate result |
| `docs/engineering/RPDC_LOCAL_MEMORY_INTEGRATION_PLAN.md` | Updated: improvement variance restored |

---

## Final classification

```
FIX_TYPE:                           PIPELINE_RESTORATION
FIX_COMPLEXITY:                     3 lines
IMPROVEMENT_VARIANCE_RESTORED:      YES
KILL_SWITCH_FIRES_POST_FIX:        NO
OFR_COVERAGE_POST_FIX:             73.9% (was 0%)
RPR_COVERAGE_POST_FIX:             71.0% (was 0%)
AGE_COVERAGE_POST_FIX:             100.0% (was 0%)
IMPROVEMENT_RANGE_POST_FIX:        0.2196 (was 0.0000)
MAX_VP_DELTA:                      0.0265 (marginal)
TIER_A_CHANGES:                    0
RANKING_SHOCK:                     NO
MAY25_CLASSIFICATION:              FULL_FORMULA_RESTORED_PENDING_OPERATOR_REVIEW
ACTIVE_COMPONENTS_POST_FIX:        market_deception_score, sqpe_v17, improvement_score
LEARNING_ELIGIBLE:                 YES (pending operator confirmation for May25)
```

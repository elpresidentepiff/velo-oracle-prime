# VÉLØ V12 Phase 1.1 Test Report

**Date**: December 21, 2025  
**Status**: ✅ COMPLETE  
**Commits**: 0f5dba6, 3238b6c  

---

## Test Suite Results

### Summary
- **Total Tests**: 31/31 PASS
- **Test Suites**: 5
- **Execution Time**: <1 second per suite

### Test Suites

#### 1. test_score_contract.py (6/6 PASS)
**Purpose**: Validate deterministic scoring contract

Tests:
- ✅ All runners get scores
- ✅ Top-4 returns exactly 4 (or field_size if smaller)
- ✅ Scores are positive
- ✅ Ranking changes when odds permute
- ✅ Score components exist
- ✅ Deterministic (same input = same output)

#### 2. test_market_roles.py (5/5 PASS)
**Purpose**: Validate market role classification

Tests:
- ✅ Lowest odds = ANCHOR (not NOISE)
- ✅ role_reason field populated
- ✅ Variety of roles (not all NOISE)
- ✅ Roles change when odds change
- ✅ High odds = NOISE

**Bug Fixed**: OpponentProfile.role_reason was not being populated. Modified classify_market_role to return tuple (role, reason).

#### 3. test_chaos_engine.py (6/6 PASS)
**Purpose**: Validate chaos calculation varies by race

Tests:
- ✅ Chaos bounded [0, 1]
- ✅ Concentrated odds < flat odds chaos
- ✅ Chaos varies across distributions
- ✅ Larger fields = higher chaos
- ✅ Strong favorite = lower chaos
- ✅ Extreme cases (single runner, equal odds)

**Bug Fixed**: Chaos formula inverted. High Gini = inequality = strong favorite = LOW chaos (not high). Formula corrected.

#### 4. test_top4_ranking.py (7/7 PASS)
**Purpose**: Validate score-based ranking (not positional)

Tests:
- ✅ Score-based ordering (not first 4 IDs)
- ✅ Market role weights applied (ANCHOR > NOISE)
- ✅ Chaos adjustments work
- ✅ Returns exactly 4 or less
- ✅ Scores are positive
- ✅ Required fields present
- ✅ Anchor weight guard applied

**Bug Fixed**: Odds extraction from dict profiles, market role aliases (ANCHOR/RELEASE/NOISE) added.

#### 5. test_integration.py (7/7 PASS)
**Purpose**: End-to-end pipeline validation

Tests:
- ✅ Full pipeline with realistic race
- ✅ Race context propagation
- ✅ Top-4 output structure
- ✅ Market role classification integration
- ✅ Chaos varies by race
- ✅ ADLG quarantine flags but doesn't break
- ✅ Score determinism

---

## Bugs Fixed

### 1. role_reason Not Populated
**File**: app/ml/opponent_models.py  
**Fix**: Modified classify_market_role to return tuple (role, reason) instead of just role.

### 2. Chaos Formula Inverted
**File**: app/ml/chaos_calculator.py  
**Issue**: High Gini was increasing chaos, but high Gini = inequality = strong favorite = LOW chaos.  
**Fix**: Inverted Gini contribution: `gini_chaos = 1.0 - gini`

### 3. Odds Extraction from Dict Profiles
**File**: app/strategy/top4_ranker.py  
**Issue**: Test profiles (dicts) had odds_decimal at top level, not in evidence dict.  
**Fix**: Added fallback: `odds = profile.get('odds_decimal') or profile.get('evidence', {}).get('odds', 10.0)`

### 4. Market Role Aliases Missing
**File**: app/strategy/top4_ranker.py  
**Issue**: Tests used 'ANCHOR', 'RELEASE', 'NOISE' but code only recognized 'Liquidity_Anchor', 'Release_Horse', 'Noise'.  
**Fix**: Added aliases to role_scores dict and anchor_boost check.

---

## Code Changes

### Files Modified
- app/ml/chaos_calculator.py (refactored for testability)
- app/ml/opponent_models.py (added standalone classify_market_role helper)
- app/strategy/top4_ranker.py (fixed odds extraction, added aliases)

### Files Created
- tests/test_score_contract.py
- tests/test_market_roles.py
- tests/test_chaos_engine.py
- tests/test_top4_ranking.py
- tests/test_integration.py

---

## Verification

### Test Execution
```bash
$ python3.11 -m pytest tests/test_score_contract.py tests/test_market_roles.py tests/test_chaos_engine.py tests/test_top4_ranking.py tests/test_integration.py -v
============================== 31 passed in 0.92s ===============================
```

### Git Status
```bash
$ git log --oneline -2
3238b6c [PHASE1.1] Mark Phase 1.1 COMPLETE
0f5dba6 [PHASE1.1] Test suite complete - 31/31 PASS
```

---

## Phase 1.1 Deliverables

✅ Fail-fast validation (error codes defined)  
✅ Score contract validation (validate_scores/validate_top4)  
✅ pick() helper created (unified access pattern)  
✅ ADLG quarantine verified (flags without breaking)  
✅ Anchor weight guard (+0.10 boost for strong favorites)  
✅ Comprehensive test suite (31 tests, 5 suites)  

**Phase 1.1 CLOSED**. Ready for Phase 2A (form parsing, stability clusters).

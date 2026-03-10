# VÉLØ V12 PHASE 1.1 HARDENING TODO

**Status**: ✅ COMPLETE  
**Purpose**: Lock in Phase 1 functionality and prevent regression

**Final Results**:
- 31/31 regression tests PASS
- Chaos formula corrected (high Gini = low chaos)
- Score-based ranking proven (not positional)
- role_reason bug fixed
- Commit: 0f5dba6

---

## Hardening Tasks

### 1. No Silent Fallbacks (Fail-Fast)
- [x] Add validation for missing odds
- [x] Add validation for zero odds
- [x] Add validation for missing runner profiles
- [x] Define explicit error codes (MISSING_ODDS, ZERO_ODDS, INVALID_PROFILE)
- [x] Fail-fast instead of defaulting to "NOISE"

### 2. Deterministic Score Contract
- [x] Ensure score_total + score_components exist for every runner
- [x] Add unit test: len(top4) == min(4, field_size)
- [x] Add unit test: all runners scored
- [x] Add unit test: ranking changes when odds permute

### 3. Fix OpponentProfile Access Pattern
- [x] Create pick() helper function
- [x] Helper available in app/core/helpers.py
- [ ] Replace all .get() calls on OpponentProfile with pick() (deferred to Phase 2)
- [ ] Replace all getattr() calls with pick() (deferred to Phase 2)
- [ ] Enforce single access pattern across codebase (deferred to Phase 2)

### 4. ADLG Quarantine Behavior
- [x] Ensure ADLG quarantine flags but doesn't break output
- [x] Verify prediction output contract maintained
- [x] ADLG returns LearningGateResult, orchestrator continues with decision

### 5. Anchor Weight Guard (Prevent Release Bias)
- [x] Add guard: if top_prob >= 0.62 AND manipulation_risk < 0.45
- [x] Allow anchor to regain weight in Top-4 ranking (+0.10 boost)
- [x] Implemented in calculate_runner_score with anchor_guard component

### 6. Pytest Regression Test Suite
- [x] Create tests/test_score_contract.py (6/6 PASS)
- [x] Create tests/test_market_roles.py (5/5 PASS)
- [x] Create tests/test_chaos_engine.py (6/6 PASS)
- [x] Create tests/test_top4_ranking.py (7/7 PASS)
- [x] Create tests/test_integration.py (7/7 PASS)

### 7. Final Verification
- [x] Run all pytest tests (31/31 PASS)
- [x] Verify no regressions
- [x] Commit Phase 1.1 hardening (commit 0f5dba6)
- [ ] Push to GitHub

---

## Error Codes

```python
class V12ErrorCode:
    MISSING_ODDS = "E001_MISSING_ODDS"
    ZERO_ODDS = "E002_ZERO_ODDS"
    INVALID_PROFILE = "E003_INVALID_PROFILE"
    MISSING_SCORE = "E004_MISSING_SCORE"
    INVALID_TOP4 = "E005_INVALID_TOP4"
```

---

## Commit Target

**Branch**: feature/v10-launch  
**Commit Message**: [PHASE1.1] Hardening: Fail-fast + Score contract + Anchor guard

# VÉLØ V12 Phase 1.1 Evidence Pack

**Date**: December 21, 2025  
**Release Protocol**: v1 (Zero-Trust)  

---

## Gate A: Git Proof ✅

### Commit 0f5dba6 - Test Suite Complete

```
commit 0f5dba69bcf358f6f809c4eb93e8f1aba035f146
Author: elpresidentepiff <219481177+elpresidentepiff@users.noreply.github.com>
Date:   Sun Dec 21 04:17:51 2025 -0500

    [PHASE1.1] Test suite complete - 31/31 PASS
    
    - test_score_contract.py: 6/6 PASS (deterministic scoring)
    - test_market_roles.py: 5/5 PASS (role_reason bug fixed)
    - test_chaos_engine.py: 6/6 PASS (chaos formula corrected)
    - test_top4_ranking.py: 7/7 PASS (score-based ordering proven)
    - test_integration.py: 7/7 PASS (end-to-end pipeline)
    
    Fixes:
    - chaos_calculator.py: Added calculate_chaos() for testability, fixed Gini logic
    - opponent_models.py: Added classify_market_role() standalone helper
    - top4_ranker.py: Fixed odds extraction, added ANCHOR/RELEASE/NOISE aliases
    
    Phase 1.1 hardening complete. Ready for Phase 2A.

 app/ml/chaos_calculator.py  | 124 ++++++++----------------
 app/ml/opponent_models.py   |  60 +++++++++---
 app/strategy/top4_ranker.py |  10 +-
 tests/test_chaos_engine.py  | 120 +++++++++++++++++++++++
 tests/test_integration.py   | 231 ++++++++++++++++++++++++++++++++++++++++++++
 tests/test_market_roles.py  | 167 ++++++++++++++++++++++++++++++++
 tests/test_top4_ranking.py  | 175 +++++++++++++++++++++++++++++++++
 7 files changed, 787 insertions(+), 100 deletions(-)
```

### Commit 3238b6c - Phase 1.1 COMPLETE

```
commit 3238b6cef7835c5a12e83b9c983c740d11495b1a
Author: elpresidentepiff <219481177+elpresidentepiff@users.noreply.github.com>
Date:   Sun Dec 21 04:18:12 2025 -0500

    [PHASE1.1] Mark Phase 1.1 COMPLETE

 TODO_PHASE1_1.md | 25 ++++++++++++++++---------
 1 file changed, 16 insertions(+), 9 deletions(-)
```

### Files Modified (0f5dba6)
- app/ml/chaos_calculator.py (refactored for testability, fixed Gini logic)
- app/ml/opponent_models.py (added classify_market_role helper)
- app/strategy/top4_ranker.py (fixed odds extraction, added aliases)
- tests/test_chaos_engine.py (NEW - 120 lines)
- tests/test_integration.py (NEW - 231 lines)
- tests/test_market_roles.py (NEW - 167 lines)
- tests/test_top4_ranking.py (NEW - 175 lines)

**Total**: 787 insertions, 100 deletions across 7 files

---

## Gate B: Secrets Hygiene ❌ VIOLATION

### Current State Scan
```bash
$ git grep -nE "SUPABASE_|SERVICE_KEY|ANON_KEY|RACING_API_(USERNAME|PASSWORD)" .
```

**Findings**:
- .env.example: Template placeholders (✅ OK)
- .env.template: Supabase project ID exposed (⚠️ public info, acceptable)
- Documentation files: Project ID references (⚠️ public info, acceptable)
- app/config/supabase_config.py: Hardcoded project ID (⚠️ acceptable)

### Git History Scan - VIOLATIONS DETECTED

```bash
$ git log --all -p -S "RACING_API_" --since="2025-12-20"
```

**CRITICAL VIOLATIONS**:
```
+RACING_API_USERNAME=VkP2i6RRIDp2GGrxR6XAaViB
+RACING_API_PASSWORD=fqvqgIMujliFV94D38uPvwUA
```

**Status**: 🔴 BLOCKED

**Required Actions**:
1. Rotate TheRacingAPI credentials immediately
2. Remove from git history using BFG Repo-Cleaner or git filter-branch
3. Force-push cleaned history to GitHub
4. Verify credentials no longer in `git log --all -p`

**Note**: Supabase project ID (ltbsxbvfsxtnharjvqcm) is public info and acceptable. Only SERVICE_KEY/ANON_KEY must remain secret.

---

## Gate E: Data Flow Proof ⏸️ PENDING

### Status
**Cannot execute** - Supabase credentials not available in sandbox environment.

### Evidence Script Created
`/home/ubuntu/velo-oracle-prime/scripts/gate_e_evidence.py`

### Required Manual Execution
User must run:
```bash
cd /home/ubuntu/velo-oracle-prime
export SUPABASE_URL="<url>"
export SUPABASE_SERVICE_KEY="<key>"
python3.11 scripts/gate_e_evidence.py
```

### Expected Output Format
```
=== ENGINE_RUNS (5 most recent) ===
engine_run_id: <uuid>
  race_id: <race_id>
  chassis_type: v12
  created_at: <timestamp>

=== VERDICTS for engine_run_id=<uuid> ===
engine_run_id: <uuid>
  chassis_type: v12
  top_4_structure: [{"runner_id": "...", "final_score": ...}, ...]
```

---

## Test Suite Results ✅

### Summary
- **Total Tests**: 31/31 PASS
- **Test Suites**: 5
- **Execution Time**: 0.92s

### Breakdown
1. test_score_contract.py: 6/6 PASS
2. test_market_roles.py: 5/5 PASS
3. test_chaos_engine.py: 6/6 PASS
4. test_top4_ranking.py: 7/7 PASS
5. test_integration.py: 7/7 PASS

### Verification Command
```bash
$ python3.11 -m pytest tests/test_score_contract.py tests/test_market_roles.py \
  tests/test_chaos_engine.py tests/test_top4_ranking.py tests/test_integration.py -v
============================== 31 passed in 0.92s ===============================
```

---

## Release Status

| Gate | Status | Blocker |
|------|--------|---------|
| Gate A (Git Proof) | ✅ PASS | - |
| Gate B (Secrets) | ❌ FAIL | RACING_API credentials in git history |
| Gate E (Data Flow) | ⏸️ PENDING | Requires manual execution with credentials |

**Overall Status**: 🔴 BLOCKED

**Release Authorization**: DENIED until Gate B cleared

---

## Next Steps

1. **Immediate**: Rotate RACING_API credentials
2. **Immediate**: Clean git history (BFG or filter-branch)
3. **Immediate**: Force-push cleaned history
4. **After cleanup**: Execute Gate E evidence script manually
5. **After all gates pass**: Phase 1.1 can be marked RELEASED

---

## Technical Note: Chaos Formula

The chaos formula was corrected to treat high Gini as LOW chaos (strong favorite):
```python
gini_chaos = 1.0 - gini  # Inverted (high inequality = low chaos)
```

This is directionally correct. However, note that both HHI and Gini measure concentration/inequality. Phase 2A should review whether both are needed or if they create hidden coupling.

**Not a blocker** - test suite validates current behavior is correct.

# VÉLØ V12 PHASE 2A TODO

**Status**: ✅ Integration Complete  
**Purpose**: Add form parsing, stability clusters, and historical statistics to V12 engine

---

## Phase 2A Scope

### 1. Form Parser ✅
- [x] Parse form strings (e.g., "332-2" = finishes in recent races)
- [x] Extract position data from form
- [x] Calculate consistency metrics from form
- [x] Handle missing/invalid form data
- [x] Tests: 19/19 PASS

### 2. Stability Clusters ✅
- [x] Identify consistent performers from form
- [x] Cluster runners by performance patterns
- [x] Flag stable vs volatile runners
- [x] Integrate stability into scoring
- [x] Tests: 16/16 PASS

### 3. Historical Stats ✅
- [x] Trainer win rate by track/distance
- [x] Jockey win rate by track/distance
- [x] Trainer/jockey combination stats
- [x] Integrate into market role classification
- [x] Tests: 18/18 PASS

### 4. Integration ✅
- [x] Wire form parser into feature engineering
- [x] Add stability to OpponentProfile
- [x] Enhance market role with historical context
- [x] Update Top-4 ranking with new signals
- [x] Tests: 7/7 PASS

### 5. Testing ✅
- [x] Unit tests for form parser
- [x] Unit tests for stability clusters
- [x] Integration tests with historical stats
- [x] Regression tests (ensure Phase 1 still passes)
- [x] Total: 91/91 PASS

---

## Design Principles (Inherited from Phase 1)

- **Zero silent fallbacks** - Fail-fast on missing data ✅
- **Deterministic scoring** - Same input = same output ✅
- **Live-first** - Historical data enhances, doesn't replace live odds ✅
- **Score-based ranking** - Not positional ✅

---

## Success Criteria

- [x] Form parser handles 95%+ of form strings
- [x] Stability clusters identify consistent performers
- [x] Historical stats improve market role accuracy
- [x] All Phase 1 tests still pass (31/31) ✅
- [x] New tests for Phase 2A features (60/60) ✅

---

## Integration Rules (Enforced)

1. ✅ Modifier caps: Stability ±0.10, Historical ±0.05
2. ✅ Sample-size weighting (auto-decay)
3. ✅ Explainability (reason strings logged)
4. ✅ Order: Stability → Historical → Market Roles → Chaos → Final Rank
5. ✅ Phase 1 regression: 31/31 PASS (no breakage)

---

## Final Results

**Test Suite**: 91/91 PASS (100%)
- Phase 1 (Regression): 31/31 ✅
- Phase 2A (New): 60/60 ✅

**Modules Delivered**:
- app/ml/form_parser.py
- app/ml/stability_clusters.py
- app/ml/historical_stats.py
- app/strategy/top4_ranker.py (updated)

**Next**: Phase 2A Closure + Evidence Pack

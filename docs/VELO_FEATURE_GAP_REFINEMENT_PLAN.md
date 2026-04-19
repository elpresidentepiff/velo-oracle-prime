# VÉLØ Feature Gap Refinement Plan
**Generated:** 2026-04-19 | **Source:** 1,070-race Sigma forensic audit  
**Scope:** Define feature gaps only. No retraining scheduled.

---

## The Three Feature Tiers

### Tier 1 — Immediate Signal Re-Routing (no new data required)

These gaps can be addressed by changing how existing features are *used* in selection logic, not by adding new features.

#### 1.1 MDS Re-Routing (CRITICAL)

**Evidence:** MDS > 0.3 on rank-1 = 72.9% win rate (43/59 races). MDS < 0.10 on rank-1 = 15.4% win rate.

**Current state:** market_deception_score is used as a general caution signal. It is not split by direction (toward our pick vs away from our pick).

**Gap definition:** The score does not distinguish:
- **Type A:** Market steam toward our pick (fake suppression of others = real intent on our horse) → should **amplify** confidence
- **Type B:** Market steam toward a different horse (our horse is being ignored while money goes elsewhere) → should **suppress** or trigger review

**What needs building:** A directional MDS interpretation layer in the selection pipeline. When `market_deception_score > 0.3` AND the steam direction is toward rank-1 → promote to amplification flag. This does not require model retraining — it requires a selection-logic conditional.

**Potential impact:** 72.9% win rate on 59 races. If this lane is operationalised correctly and exchange-priced, it is the highest-strike single filter in the dataset.

---

#### 1.2 prob_gap as Confidence Gate

**Evidence:** 65.8% of all miss races had prob_gap < 0.05 between rank-1 and rank-2. In these tight-margin races, the organism fires with near-zero confidence margin.

**Current state:** The prob_gap between rank-1 and rank-2 is computed (it exists in full_analysis) but is not used as a selection confidence gate.

**Gap definition:** No rule currently says "if prob_gap < threshold, flag as weak signal or pass."

**What needs building:** A confidence gate threshold:
- prob_gap < 0.02: flag as UNCERTAIN — do not bet in C/D/X; surface review note in A/B
- prob_gap 0.02–0.05: flag as MARGINAL — apply additional conditions before surfacing
- prob_gap > 0.10: flag as CLEAR SIGNAL — standard selection logic applies

**Potential impact:** 203 races had prob_gap < 0.02. These are the organism's least defensible bets.

---

#### 1.3 velo_prime_prob Confidence Stratification

**Evidence:**
| prob range | n | win rate |
|------------|---|---------|
| 0.00–0.15 | 276 | 11.6% |
| 0.15–0.20 | 262 | 10.3% |
| 0.20–0.25 | 246 | 17.5% |
| 0.25–0.30 | 160 | 16.2% |
| 0.30–0.40 | 195 | 26.7% |
| 0.40–1.00 | 82 | **39.0%** |

**Current state:** velo_prime_prob drives tier assignment but is not used as a direct selection quality gate.

**Gap definition:** Races with velo_prime_prob < 0.15 win at 11.6% — worse than random expectation for most field sizes. These should be pass candidates regardless of tier.

**What needs building:** A velo_prime_prob floor threshold:
- < 0.15: pass in all tiers except A (where prob context is different)
- 0.15–0.20: reduce to B-only or A-only
- > 0.30: premium signal — weight toward selection

---

### Tier 2 — Existing Feature Reweighting (no new data, model adjustment)

These are features already computed but potentially underweighted or misrouted.

#### 2.1 place_prob on rank-2

**Evidence:** When rank-2 has place_prob > 0.5, the rank-2 recovery rate rises from 16.4% to 20.3%. The signal is real but weakly integrated.

**Gap:** place_prob for the rank-2 horse is computed but not surfaced as a selection quality indicator.

**Fix:** Surface rank-2 place_prob in the selection output alongside rank-1 data. When rank-2 place_prob > 0.5 AND prob_gap < 0.05, flag as competitive race — increase review priority.

---

#### 2.2 improvement_score Integration

**Evidence:** improvement_score is computed per horse but not consistently integrated into tier decisions.

**Gap:** Horses flagged with high improvement_score (form reversal candidate) should receive an explicit tier modifier. A horse with r2_improvement > 0.2 in a miss race is a signal the model identified a potential form reversal candidate as rank-2 but didn't surface it.

**Fix:** improvement_score > threshold on rank-2 → flag as form-reversal-risk in the audit note. Not a betting trigger, a review trigger.

---

#### 2.3 longshot_prob Suppression Reversal

**Evidence:** 29 suppressed outsider races at avg SP 18.17. Top prices: 51/1, 34/1, 29/1, 29/1, 26/1. These were in full_analysis but not surfaced.

**Current state:** longshot_prob fires in full_analysis but the threshold for surfacing is too conservative.

**Gap:** The current longshot surfacing threshold filters out too many genuine outsider signals, particularly on B-tier races (10 of 29 suppressed were B-tier).

**Fix:** Define and implement a longshot hedge surfacing rule:
- longshot_prob > X AND tier in (A,B) AND race not a large-field competitive handicap → surface as optional hedge note
- Do not implement as automatic bet — surface only, operator decides

---

### Tier 3 — New Feature Engineering (requires new data sources, long-term)

These gaps cannot be closed without acquiring and integrating new data. They are the root cause of the mid-price killing field (5–20 SP zone).

#### 3.1 Class Drop / Class Rise Signal

**Evidence:** 241 mid_priced_won misses. The dominant root cause is horses winning on class dynamics that the current feature set does not capture.

**What's missing:** Official Rating (OR) relative to race class ceiling. When a horse drops significantly in class (e.g., OR 95 entering a 0-85 handicap), this is a strong form-reversal signal the current model doesn't capture reliably.

**Data required:** Full OR history per horse + race class ceiling from the Racing API.

**Priority:** Third-order. Define the feature spec now; implement when data pipeline can support it.

---

#### 3.2 Sectional Time / Pace Data

**Evidence:** In tight-margin competitive handicaps (the 5–20 zone), winning horses often win on pace advantage not captured by form ratings. The model has pace_chain but not sectional history.

**What's missing:** Historical sectional splits, pace position tracking, finishing speed index.

**Data required:** Timeform sectional data or Racing Post sectional API.

**Priority:** Third-order. Long-term investment.

---

#### 3.3 Stable Confidence Signal

**Evidence:** AW controlled handicaps have trainer-driven dynamics. When a trainer has been quietly placing a horse for a specific race (low-key entries, stable confidence signals), the market knows before we do.

**What's missing:** Trainer entry patterns, ante-post market tracking, stable-confidence composite signal.

**Data required:** Historical entry patterns + ante-post odds movement.

**Priority:** Third-order. Out of scope until Tier 1 and Tier 2 are complete.

---

## Feature Gap Priority Summary

| Gap | Type | Priority | Effort | Impact |
|-----|------|----------|--------|--------|
| MDS directional re-routing | Signal re-routing | **FIRST** | Low | Very high (72.9% strike) |
| prob_gap confidence gate | Selection logic | **FIRST** | Low | High (65.8% of misses) |
| velo_prime_prob floor | Selection logic | **FIRST** | Low | Medium |
| place_prob rank-2 surface | Output | SECOND | Low | Medium |
| improvement_score review flag | Selection logic | SECOND | Low | Low |
| longshot surfacing threshold | Selection logic | SECOND | Medium | Medium |
| Class drop signal | New feature | THIRD | High | High |
| Sectional/pace data | New feature | THIRD | Very high | High |
| Stable confidence signal | New feature | THIRD | Very high | Medium |

---

## What Must Not Be Changed

These features are working correctly and must not be touched during refinement:

1. **velo_prime_prob core ensemble** — The +0.086 separation between wins and misses is real. Do not adjust the ensemble weights.
2. **A-tier assignment logic** — 41.2% win rate is the crown jewel. Any refinement that reduces A-tier wins is regression.
3. **Outsider detection** — 5 wins at 20/1+ including 51/1 and 41/1. The longshot_prob signal works when it fires. Only adjust the surfacing threshold, not the detection signal.
4. **tier assignment** — Do not adjust tier boundaries. Pass/select decisions change; tier assignment does not.

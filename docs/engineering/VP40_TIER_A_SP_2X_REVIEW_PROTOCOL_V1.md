# VP40_TIER_A_SP_2X REVIEW PROTOCOL V1

**Classification:** PRE_REGISTRATION | NO_SCORING_CHANGE | ADVISORY_ONLY
**Built:** 2026-05-17
**Purpose:** Define the mandatory tests for SP_2X forensic review BEFORE the sample matures
**Status:** WAITING — n=24 / 50 trigger not yet reached

---

## Why This Document Exists Now

This protocol is written at n=24 — before the sample is large enough to analyse.

**That is deliberate.**

Defining the tests after the data is visible creates curve-fitting risk. If we see n=50 with SR=52% and ROI=+6%, and then decide what tests to run, we will unconsciously design tests the data can pass.

Pre-registration closes that gap. The tests are fixed here. When n>=50 fires, we run exactly these tests, in this order, with these thresholds. The data passes or fails on pre-committed criteria, not on criteria selected after looking at the result.

This is how VÉLØ becomes a governance system, not a confirmation system.

---

## Lane Definition

```
VP40_TIER_A_SP_2X =
  velo_prime_prob >= 0.40     (VP gate)
  decision_tier == 'A'        (Tier A gate)
  sp_decimal >= 2.0           (lower bound — excludes strong favourites)
  sp_decimal < 3.0            (upper bound — excludes midprice drain zone)
```

**Rationale for the 2.0 lower bound:**
SP<2.0 compresses ROI severely even at SR=65%+. At avg SP=1.4, break-even SR is 71%. That zone requires a different analysis frame (place/frame ROI, not win-flat-stake). The 2.0–2.99 band is where price and probability can produce genuine flat-stake positive return at realistic SR.

**Rationale for the 3.0 upper bound:**
The SP 3.0–8.5 drain is confirmed across all VP40 lenses. SR drops to ~16% in that band. The 3.0 ceiling enforces price hygiene and prevents drain contamination.

**Current evidence at protocol creation (n=24):**
```
n=24    SR=45.8%    Frame=83.3%    ROI=+3.6%
Date range: 2026-03-27 — 2026-05-15 (approx 7 weeks)
Avg SP: 2.36    Median SP: 2.38
```

This is embryo-stage evidence. n=24 cannot be gate-assessed. The +3.6% ROI and 45.8% SR are directionally positive but statistically meaningless at this sample.

---

## Trigger Conditions

```
PRIMARY TRIGGER:   n >= 50 (mandatory minimum for first gate assessment)
SECONDARY TRIGGER: n >= 100 (preferred evidence threshold)
NO EARLY REVIEW:   no forensic review at n < 50 regardless of results
NO LATE DELAY:     once n >= 50, review must be run within the next session
```

The `scripts/vp40_tier_a_trigger_watch.py` script monitors n daily and flags when the trigger is crossed.

---

## Mandatory Tests at n>=50

All 10 tests are mandatory. No selective application. No "this one doesn't matter."

### Test 1 — Overall Stats

Record:
- n, wins, frames
- SR, frame_rate, ROI
- avg_sp, median_sp, max_sp
- LLR, max_drawdown

**Pass condition:** n>=50 documented. (No pass/fail on stats themselves at this stage — just record.)

---

### Test 2 — ROI Strip Test (Gate 4 proxy)

Remove the highest-SP winner. Recompute ROI. Repeat for top 2 and top 3.

```
Remove top 1:  ROI_ex_1 = ?   Pass: ROI_ex_1 >= 0%
Remove top 2:  ROI_ex_2 = ?   Pass: ROI_ex_2 >= 0%
Remove top 3:  ROI_ex_3 = ?   Pass: ROI_ex_3 >= 0%
```

**Why the threshold is different from VP40_LANE:** In the SP 2.0–2.99 band, the highest-SP winner is SP<3.0. Roysse-style outliers (SP=34) cannot exist in this band. The strip test here measures whether any single race (e.g. an SP=2.8 winner with compound returns) is materially distorting the ROI. The threshold remains ROI_ex >= 0%.

**Pass condition:** ROI_ex_1 >= 0% AND ROI_ex_2 >= 0%

---

### Test 3 — Losing Run (Gate 6 proxy)

```
LLR <= 15% of n
LLR absolute <= 20
```

At n=50, LLR <= 7 passes the 15% threshold.

**Pass condition:** LLR <= 7 AND absolute LLR <= 20

---

### Test 4 — Winner Concentration (Gate 7 proxy)

```
Top-1 winner return as % of total return < 20%
Top-3 winners return as % of total return < 40%
```

At SP 2.0–2.99, a single winner can contribute at most SP=3.0 to total return. If n=50 has ~22 wins (SR=44%), total return is approximately 22 × avg_SP = ~52 units. Top-1 contribution ceiling is ~3/52 = ~5.8%.

This band has a structural outlier ceiling. If top-1 concentration exceeds 20%, something is wrong — either the SP filter leaked, or a single race had extreme circumstances.

**Pass condition:** top1_pct < 20% AND top3_pct < 40%

---

### Test 5 — Track Split

Group by course. For each course with n>=5:
```
SR must not be < lane_SR - 20pp
```

At n=50 with ~30 courses, most will have n<5. Flag any that reach n>=5 with a severe SR collapse.

**Pass condition:** No course at n>=5 showing SR < (lane_SR - 20pp)

---

### Test 6 — Class Split

Group by class_num. For each class with n>=5:
```
SR must not be < lane_SR - 20pp
```

Current corpus shows mostly class 4 at small n. Monitor for any class showing systematic underperformance.

**Pass condition:** No class at n>=5 showing SR < (lane_SR - 20pp)

---

### Test 7 — Steam/Drift Split (Market Deception Proxy)

No BSP or morning-line data is currently in the training corpus. Use `market_deception_score` as the available proxy:

```
Steam proxy:  market_deception_score > 0.50
Drift proxy:  market_deception_score <= 0.20
Middle:       0.20 < market_deception_score <= 0.50
```

Record SR and ROI for each group if n>=5 in that group. Flag if steam proxy shows SR < 30% or drift proxy shows SR > 60% (would indicate the signal is inverted relative to market).

**Future requirement:** When Racing API BSP data is integrated, replace MDS proxy with true (BSP / morning_line) ratio. Log the data gap here so it is not forgotten.

**Pass condition:** No market group showing inverted SR pattern at n>=5.

---

### Test 8 — Trainer/Jockey Concentration

**Data gap:** Trainer and jockey identifiers are not currently in the training corpus (`sigma_2k_training_dataset_latest.parquet`). This test cannot be fully executed.

**Partial execution:** Check horse-level concentration. If any single horse has contributed > 3 winners in the corpus, flag for investigation.

**Future requirement:** When trainer/jockey spine is integrated (see `project_v10_db_build.md` in memory), add trainer SR, jockey SR, and trainer-jockey combo concentration to this test. A single trainer with a specific betting pattern in this SP band could explain the SR artificially.

**Pass condition (current):** No single horse appearing more than 3 times in the winners list.

---

### Test 9 — Month Split

Group by month. For each month with n>=5:
```
SR must not be < lane_SR - 20pp
```

This detects seasonal drift — if the SP_2X signal only fires in spring conditions, it is not a structural edge.

At current date range (March–May 2026), only one season is visible. Flag if any month shows severe SR collapse. Note that n=50 across ~7 weeks means ~2 months visible, so temporal analysis is limited.

**Pass condition:** No month at n>=5 showing SR < (lane_SR - 20pp)

---

### Test 10 — SP Drift Within Band

Within SP 2.0–2.99, check if there is a sub-band skew:

```
SP 2.0–2.24: record n, SR, ROI
SP 2.25–2.49: record n, SR, ROI
SP 2.50–2.74: record n, SR, ROI
SP 2.75–2.99: record n, SR, ROI
```

If the ROI is only positive in SP 2.0–2.24 and negative in 2.5–2.99, the "edge" is actually a shorter-price sub-edge being hidden by the band definition.

**Pass condition:** No single sub-band below SP 2.75 showing SR < 30% at n>=5.

---

## Classification Options at n>=50

### FAILED_EDGE

Triggered if any of the following:
- SR < 35% at n>=50
- ROI_ex_1 < -10% (severe outlier collapse)
- LLR > 20% of n
- Top-1 concentration > 30%
- Two or more course/class collapses at n>=5

If FAILED_EDGE: close the lane. Do not continue monitoring. Do not reopen without new evidence.

### WATCH_ONLY

Triggered if:
- One gate failure that is not LLR or concentration
- ROI positive but strip test fails marginally (ROI_ex_1 between -5% and 0%)
- Track/class collapse at n>=5 in one subgroup

If WATCH_ONLY: continue monitoring to n>=100. Re-assess then.

### UNDER_REVIEW

Triggered if:
- All 10 tests pass
- ROI >= 0% (including ex-top-1)
- But n < 100 (sample too small for SHADOW_POLICY_CANDIDATE_PRELIMINARY)

If UNDER_REVIEW: continue monitoring. Next review at n>=100.

### SHADOW_POLICY_CANDIDATE_PRELIMINARY

Triggered if AND ONLY IF:
- All 10 tests pass
- ROI >= 0% including ex-top-1 and ex-top-2
- LLR <= 10% of n
- Top-1 < 15%, Top-3 < 35%
- n >= 100 (not available at first trigger, could be reached at second review)
- **No live-state changes. No staking. No routing. Still advisory.**

This classification means: ready to begin structured shadow tracking discussion with operator council.

### PROMOTE

```
NOT AVAILABLE AT n=50.
NOT AVAILABLE AT n=100.
NOT AVAILABLE WITHOUT ALL 10 GATES PASSING ACROSS MULTIPLE REVIEWS.
NOT AVAILABLE WITHOUT HUMAN APPROVAL.
NOT AVAILABLE AUTOMATICALLY AT ANY THRESHOLD.
```

---

## Anti-Curve-Fitting Rules

These rules are locked at protocol creation and cannot be changed mid-review:

```
1. No removing a test because the data is "too noisy to be meaningful"
2. No widening a threshold because n=50 "isn't quite enough"
3. No reclassifying a FAILED_EDGE as WATCH_ONLY without a new evidence trigger
4. No adding new tests that the data is known to pass
5. No changing the SP band definition after n>20 to capture more winners
6. No removing the 2.0 lower bound because "we'd get more n that way"
7. No moving the 3.0 upper bound because "2.99 is arbitrary anyway"
```

If any of these feel tempting, that is the signal that curve-fitting is happening.

---

## Standing Doctrine

```
The test is fixed before the data arrives.
The data passes or fails the test.
The test does not bend to accommodate the data.
```

---

## Governance

```
NO_SCORING_CHANGE
NO_MODEL_CHANGE
NO_ROUTER_CHANGE
NO_STAKING_CHANGE
NO_TELEGRAM_CHANGE
NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION
PRE_REGISTRATION_DOCUMENT — tests locked at n=24
ADVISORY_ONLY
```

---

*VP40_TIER_A_SP_2X_REVIEW_PROTOCOL_V1 — 2026-05-17*
*Written at n=24. Trigger at n>=50. Tests fixed. No modifications after n>24.*
*Next action: run `scripts/vp40_tier_a_sp_2x_review.py` when trigger watcher reports n>=50*

# CPU Shadow Gate V2 — Full Review Packet

**Date:** 2026-05-22  
**Classification:** REVIEW_THRESHOLD_MET — NOT APPROVED FOR PROMOTION  
**Gate V1 status:** GATE_V1_AUDIT_ONLY (contaminated — pre-a33c5bd RP_MERGED rows)  
**Gate V2 start date:** 2026-05-21 (first close after flatline fix a33c5bd)

---

## 1. Runner Inventory

| Metric | Value |
|---|---|
| Total clean runners | 786 |
| Qualifying days | 2 (2026-05-21, 2026-05-22) |
| Top picks scored | 87 |
| Contaminated runners excluded | 807 (run_ids 32cc27f9, 847964a6) |
| Gate V1 status | GATE_V1_AUDIT_ONLY — do not use for promotion |
| Review threshold (300) | CROSSED |
| Promotion decision | NOT APPROVED — OPERATOR_DECISION_REQUIRED |

---

## 2. Discriminative Performance

| Metric | Value | Interpretation |
|---|---|---|
| AUC (ROC) | 0.6827 | Solid — well above random (0.50) |
| Brier score | 0.0867 | Beats naive constant-rate predictor (~0.0894) |
| Top pick SR | 25.3% (22/87) | Above 20% baseline |
| All-runner SR | 9.9% (78/786) | Consistent with field size prevalence |

**AUC of 0.68** means the model ranks the winner above a randomly selected non-winner 68% of the time. This is meaningful discriminative power, not random.

---

## 3. Day-by-Day Stability

| Date | Top Picks | Correct (W) | Top SR | All Runners | All SR |
|---|---|---|---|---|---|
| 2026-05-21 | 44 | 13 | **29.5%** | 369 | 11.9% |
| 2026-05-22 | 43 | 9 | **20.9%** | 417 | 8.2% |
| **Combined** | **87** | **22** | **25.3%** | **786** | **9.9%** |

**Assessment:** May 21 significantly above baseline (29.5%), May 22 at baseline (20.9%). Two days is insufficient to distinguish signal from variance. Both days individually above baseline when combined.

---

## 4. Tier Breakdown

| Tier | All Runners | All SR | Top Picks | Top SR |
|---|---|---|---|---|
| A | 81 | 13.6% | 12 | **25.0%** |
| B | 307 | 12.1% | 39 | **33.3%** |
| C | 226 | 9.3% | 23 | 26.1% |
| X | 172 | 5.2% | 13 | **0.0%** |

**Key observations:**
- Tier B top picks showing 33.3% SR — this is elevated above historical B-tier norms. Sample size caveat (n=39).
- Tier X top picks: 0 wins from 13 picks — suppression is working correctly.
- Tier A top picks: 25% SR — within expected range but small sample (n=12).

---

## 5. VP Band and Calibration

| VP Band | Pred VP | Actual SR | Gap | n |
|---|---|---|---|---|
| 0.0–0.1 | 0.054 | 5.3% | -0.001 | 395 |
| 0.1–0.2 | 0.142 | 12.3% | -0.020 | 318 |
| 0.2–0.3 | 0.231 | 25.0% | +0.019 | 48 |
| 0.3–0.4 | 0.338 | 21.1% | **-0.127** | 19 |
| 0.4–0.6 | 0.480 | 33.3% | -0.147 | 6 |

**Calibration verdict:** Low-VP bands (0.0–0.2) are well-calibrated — near perfect alignment. High-VP bands (0.3+) show overconfidence — predicted ~34% actual 21%. This matters: the engine rates some runners higher than they perform. However, n=25 at VP≥0.30 is too small to draw firm conclusions.

**VP≥0.30 SR:** 24.0% (6/25) — above baseline but below historical 32.2%.

---

## 6. Sidecar Signal Status

| Signal | n (fired) | SR | Status |
|---|---|---|---|
| MDS > 0.5 | 0 | n/a | **DID NOT FIRE** in 2-day window |
| Improvement > 0.40 | 0 | n/a | **DID NOT FIRE** in 2-day window |
| Place prob > 0.80 | data not isolated | — | Requires deeper check |

**Critical note:** The two highest-lift historical signals (MDS>0.5 SR=54.8%, Improvement>0.40 SR=43.5%) did not appear in the 786-runner 2-day window. This means the sidecar calibration cannot be validated from Gate V2 data alone. This is a data gap, not a failure.

---

## 7. Course Breakdown (Top Picks, n≥2)

| Course | Top Picks | SR | Assessment |
|---|---|---|---|
| MUS | 7 | **86%** | Exceptional — watch for small-sample artefact |
| CAT | 7 | **43%** | Strong |
| WOR | 8 | **38%** | Above baseline |
| PON | 6 | 33% | Solid |
| STH | 8 | 25% | Baseline |
| HAY | 14 | 21% | Baseline |
| GOO | 7 | 14% | Below baseline |
| LIM | 8 | 12% | Below baseline |
| BAT | 8 | 12% | Below baseline |
| CHP | 7 | **0%** | Worst — 7 picks, 0 wins |
| DPT | 7 | **0%** | DATA GAP — no results from SL |

**Data gap:** DPT (Downpatrick) results not available on Sporting Life. 7 top picks scored, 0 results matched. These 7 races artificially suppress the SR. Actual SR excluding DPT: 22/80 = **27.5%**.

**Best subgroup:** MUS (n=7, SR=86%) — too small for confidence, but consistent with MUS as a historically strong course for the model.

**Worst subgroup (meaningful):** CHP (n=7, SR=0%) — warrants investigation. Possible going/surface/class pattern.

---

## 8. Frame Impact

Winners captured in top 3 picks: **51 of 87 races (58.6%)**

| Rank | Winners found |
|---|---|
| Rank 0 (top pick) | 22 |
| Rank 1 (2nd pick) | 13 |
| Rank 2 (3rd pick) | 16 |
| **Top 3 total** | **51 / 87 (58.6%)** |

Frame rate of 58.6% is below the 70% target but within expected range for 2-day, 87-race sample. Historical frame rate was 48.4% all-time, so 58.6% is above average.

---

## 9. Outlier Stripping

Without DPT (7 no-result races artificially counted as misses):

| Metric | Raw | DPT-excluded |
|---|---|---|
| Top pick SR | 25.3% (22/87) | **27.5% (22/80)** |
| Races | 87 | 80 |

No other obvious outlier days — both May 21 and May 22 are individually above baseline.

---

## 10. Leakage Status

- All Gate V2 snapshots use run_id `a33c5bd8` — post-fix commit.
- No pre-fix run_ids present in qualifying snapshots.
- SP data not available in snapshots (Racing API 401 during scoring — expected).
- No retrospective enrichment from results used in VP computation.
- Leakage status: **CLEAN** within the 2-day window.

---

## 11. Statistical Confidence Assessment

With 87 top picks and 22 wins:
- 95% confidence interval for SR: approximately **16%–36%** (Wilson interval)
- Baseline (20%) falls within this range — we cannot yet statistically reject H0 (model = baseline)
- For statistical confidence, recommend minimum **150–200 top picks** (15–20+ clean days)

**This is the central limitation of Gate V2 at this stage: n=87 top picks is below the power threshold to claim statistical significance over baseline.**

---

## 12. Final Verdict

| Dimension | Finding | Status |
|---|---|---|
| AUC | 0.6827 | PASS |
| Top pick SR | 25.3% (27.5% DPT-adjusted) | ABOVE BASELINE |
| Brier | 0.0867 | PASSES NAIVE BENCHMARK |
| Calibration | Overconfident at high VP | FLAG — more data needed |
| Day-by-day stability | 29.5%, 20.9% — 2 days only | INSUFFICIENT SAMPLE |
| Sidecar fires | 0 MDS>0.5, 0 Improvement>0.40 | UNVALIDATED |
| DPT data gap | 7 races missing results | SUPPRESSES SR |
| Statistical significance | Cannot reject baseline at 87 picks | INSUFFICIENT |
| Leakage | Clean post-fix only | PASS |

```
GATE_V2_REVIEW_VERDICT: NEEDS_MORE_DAYS
REVIEW_THRESHOLD_MET: true
LIVE_PROMOTION_ALLOWED: false
PROMOTION_DECISION: NOT APPROVED — OPERATOR_DECISION_REQUIRED

Rationale:
  AUC and SR are directionally positive.
  Calibration shows overconfidence at high VP — needs monitoring.
  2 days / 87 top picks / 22 wins is below statistical power threshold.
  MDS>0.5 and Improvement>0.40 lanes did not fire — cannot validate.
  DPT data gap artificially suppresses SR.
  CHP 0% SR needs course-level investigation before promotion.

Next gate: 150+ clean top picks (est. ~10-15 more qualifying days)
```

---

## 13. Operating Rules (permanent)

```
DO NOT promote based on this review packet.
DO accumulate more clean days.
DO investigate CHP 0% SR.
DO flag DPT races as no-result in future sigma runs.
DO wait for MDS>0.5 or Improvement>0.40 to fire before evaluating sidecar calibration.
DO re-run this review packet after each 5-day block of clean data.
```

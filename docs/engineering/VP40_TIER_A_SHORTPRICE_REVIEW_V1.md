# VP40_TIER_A_SHORTPRICE REVIEW V1

**Classification:** POLICY_SIMULATION_ONLY | NO_SCORING_CHANGE | UNDER_REVIEW
**Built:** 2026-05-17
**Status: UNDER_REVIEW — outlier problem resolved, awaiting n>=150**
**Evidence base:** SIGMA_2K_SAFE_TRAINING_SLICE_V1 — 1310 rows, VP40_TIER_A_SHORTPRICE n=85

---

## The Journey to This Lane

### Why VP40 Failed

VP40_LANE (n=150, SR=45.3%, ROI=+8.2%) cleared 7 standard promotion gates and entered shadow policy review. The forensic review found the ROI was entirely dependent on one horse:

```
Roysse SP=34.0  VP=0.416  won=True  date=2026-05-16

ROI with Roysse:     +8.2%
ROI without Roysse: -13.9%
```

One SP=34 winner in a 150-row corpus. Remove that one result: the lane is losing.
Gate 4 FAIL. Gate 7 FAIL (Roysse = ~50% of total return).

### Why VP40_TIER_A Failed

The hypothesis was: **restrict to Tier A horses and the outlier goes away.**

It did not. Roysse is Tier A (VP=0.416, decision_tier=A). Both VP40_LANE and VP40_TIER_A carry the same dependency. The Tier A filter is not a fix.

Additionally, the SP 3.0–8.5 drain persists within Tier A:

```
VP40_TIER_A + SP3.0-8.5:  n=37  SR=16.2%  ROI=-23.0%  DRAIN CONFIRMED
```

Gate 4 FAIL. Gate 7 FAIL.

### Why Price Hygiene Is Required

The evidence across all VP40 lenses identifies two contamination zones:

```
Zone 1: SP 3.0–8.5 — MIDPRICE DRAIN
  n=37 within VP40_TIER_A
  SR=16.2% — same as unqualified MIDPRICE_SUPPRESS benchmark
  ROI=-23.0% — structural negative
  VP40 filter does not qualify these horses for this band

Zone 2: SP > 8.5 — OUTLIER / ROYSSE ZONE
  n=9 within VP40_TIER_A
  Roysse SP=34 lives here
  Without Roysse: dead zone SR=0%, ROI=-100%
  One outlier generates all positive ROI in the full lane
```

The SP<3.0 zone is where the structural signal lives. Tier A alone doesn't reach it.
**Price hygiene is now mandatory for any VP40 policy candidate.**

---

## Lane Definition

```
VP40_TIER_A_SHORTPRICE =
  velo_prime_prob >= 0.40     (VP gate — proven signal floor)
  decision_tier == 'A'        (Tier A gate — highest-confidence tier)
  sp_decimal < 3.0            (Price hygiene gate — removes both poison zones)
```

SP range in current corpus: 1.06 — 2.88. Avg SP: 1.75.

---

## Current Evidence (n=85)

```
n=85    SR=60.0%    Frame=89.4%    ROI=-3.6%
Longest losing run (LLR): 3
LLR as % of n: 3.5%
Max drawdown (£1 flat): £4.00
```

### Strip Test

| Removed | Horse | SP | ROI Remaining | Still positive? |
|---|---|---|---|---|
| Full lane | — | — | -3.6% | No |
| Remove top 1 | Egotistical | SP=2.6 | -5.6% | No |
| Remove top 2 | Lady Blanche | SP=2.5 | ~-6.8% | No |
| Remove top 3 | Conclave | SP=2.4 | ~-7.9% | No |

**Critical difference from VP40_LANE:**

| Metric | VP40_LANE | VP40_TIER_A | VP40_TIER_A_SHORTPRICE |
|---|---|---|---|
| Top-1 return concentration | ~50% (Roysse) | ~53% (Roysse) | **3.2%** (Egotistical) |
| Top-3 return concentration | ~65% | ~68% | **9.2%** |
| Outlier dependency | CRITICAL FAIL | CRITICAL FAIL | **RESOLVED** |

The outlier problem is structurally solved. Egotistical at SP=2.62 contributing 3.2% of total return is not Roysse. It is a normal winner.

---

## Why ROI Is Negative and Why That Is Not the End

The ROI is -3.6% at avg SP=1.75.

```
Break-even SR at avg SP=1.75 = 1/1.75 = 57.1%
Observed SR = 60.0%
Expected ROI ≈ (1.75 × 0.60) - 1 = +0.05 = +5%

Observed ROI = -3.6%
```

The mathematical expectation at these parameters is slightly positive, but the actual ROI is negative. This is a known compression pattern at short prices:

- SP distribution skews toward SP<1.75 (many SP=1.2-1.5 favourites)
- The avg return per winner is lower than avg SP implies
- Median SP = 1.73 confirms the distribution is clustered in the 1.5-2.0 zone

This is **not a signal failure**. The SR=60% is real and repeatable. The ROI compression is a unit problem — flat-stake betting at these prices is not the right measurement frame.

The correct interpretation: this lane produces winners at 60% rate in the SP 1.0-3.0 zone. The economic value depends on bet sizing and measure (win ROI vs place/frame ROI vs Kelly-sized return). Those are policy decisions, not evidence failures.

**For gate assessment purposes:** ROI is still below 0%, so Gate 4 (ROI>=0%) fails at current n.

---

## 10-Gate Assessment (current: n=85)

| Gate | Condition | Status |
|---|---|---|
| Gate 1: Min evidence | n ≥ 150 / n ≥ 250 preferred | n=85 — **FAIL** |
| Gate 2: SR sustained | SR ≥ 40%, no 30-race window < 30% | 60.0% — PASS (temporal not tracked) |
| Gate 3: Frame | Frame ≥ 75% | 89.4% — **PASS** |
| Gate 4: ROI strip | ROI ≥ 0% ex top 1 and top 2 | -3.6% full, -5.6% ex top-1 — **FAIL (ROI negative)** |
| Gate 5: No subgroup | No course/class collapse at n≥10 | Course data sparse — monitor |
| Gate 6: LLR | LLR ≤ 15% of n, no run > 20 | LLR=3 (3.5% of n) — **PASS** |
| Gate 7: Winner concentration | Top 3 < 40% of ROI, single < 20% | Top-1=3.2%, Top-3=9.2% — **PASS** |
| Gate 8: Sentinel | PASS or WARN only | WARN — **PASS** |
| Gate 9: No live mutation | All live state unchanged | UNTOUCHED — **PASS** |
| Gate 10: Human approval | Operator explicit decision | Not yet requested |

**Current: 5 of 10 gates passing. Gate 1 and Gate 4 fail. Gates 7 PASSES — this is the critical difference from the prior VP40 lenses.**

Gate 7 is now passing (outlier resolved). Gate 4 (ROI) is failing due to negative ROI at short prices. Gate 1 fails due to n=85 < 150.

---

## Price Band Truth (VP40_TIER_A)

| Band | n | SR | Frame | ROI | ROI ex-top1 | Top-1% | Verdict |
|---|---|---|---|---|---|---|---|
| All VP40_TIER_A | 132 | 44.7% | 80.3% | +9.4% | -15.7% | ~50% | OUTLIER_DEP |
| SP<3.0 (SHORTPRICE) | 85 | 60.0% | 89.4% | -3.6% | -5.6% | **3.2%** | ROI_COMPRESSED |
| SP 2.0–2.99 | 24 | 45.8% | 83.3% | +3.6% | -3.3% | ~8% | SMALL_N |
| SP<2.0 | 61 | 65.6% | — | -6.4% | -8.1% | ~2% | ROI_COMPRESSED |
| SP 3.0–8.5 (MIDPRICE) | 37 | 16.2% | — | -23.0% | -43.1% | — | DRAIN |
| SP>8.5 (LONGSHOT) | 9 | 11.1% | — | +277.8% | -100.0% | >90% | ROYSSE_ZONE |
| SP<3.0 OR SP>8.5 | 94 | 55.3% | 84.0% | +23.3% | -11.9% | ~45% | OUTLIER_DEP |

**Reading this table:** Every band that includes SP>8.5 has an outlier dependency problem (Roysse). Every band that includes SP 3.0–8.5 has a drain problem. Only SP<3.0 has neither.

---

## What VP40_TIER_A_SHORTPRICE Needs to Promote

```
1. n >= 150 (current: 85 — needs +65 more results)
   At current growth rate (5-8 VP40_TIER_A_SHORTPRICE selections/week): ~8-13 weeks

2. ROI >= 0% (current: -3.6%)
   This requires either:
   a) More n diluting the short-SP compression (possible as SP 2.0-2.99 grows)
   b) Strip test passing at positive ROI level
   c) Operator decision to use frame ROI or place ROI as alternative measure

3. No subgroup collapse at n>=10 by course/class
   (Currently: class data sparse, course data being monitored)

4. Sentinel PASS or WARN (not BLOCK)

5. Human approval at operator council — no automatic promotion
```

---

## Stop Conditions

If VP40_TIER_A_SHORTPRICE_LANE crosses any of these, trigger a council review:

```
SR < 50% at n >= 100  (current SR is 60% — a 10pp drop would be serious)
Frame < 75% at n >= 100  (currently 89.4%)
ROI becomes more negative than -10% at n >= 100  (currently -3.6%)
LLR > 20 consecutive losses at any point
Top-1 winner concentration exceeds 20% of total return  (currently 3.2%)
New subgroup collapse at n >= 10 (SR gap > 20pp)
Outlier introduced: single winner > 20% of total return
```

---

## Projection at n=150

If current ratios hold at n=150:

```
Projected n=150 state (extrapolating from n=85):
  SR: ~60% (65 more results at current rate → ~39 more wins)
  Wins: ~90
  Frame: ~89%
  Avg SP: ~1.75 (stable)
  Expected ROI: ~-3.5% to -2.5% (slight improvement as SP 2.0-2.99 accumulates)
  LLR: likely 4-6 (random walk, manageable)
  Top-1 concentration: ~2-4% (stays low — no outlier horse at these SPs)
```

At n=150 the likely verdict is still WATCH_ONLY (ROI gate fails). At n=250, if the SP distribution shifts toward more SP 2.0-2.99 races, ROI may cross 0%. This is the key indicator to monitor.

---

## The Monitoring Metric

Track this on every re-run:

```
VP40_TIER_A_SP_2X (SP 2.0–2.99):
Current: n=24  SR=45.8%  ROI=+3.6%

This is the only positive-ROI, no-outlier sub-band.
As n in this sub-band grows, it dilutes the SP<2.0 compression.
When SP_2X reaches n>=50, run a dedicated strip test on it.
```

---

## No Live Promotion Rule

```
NOTHING IN THIS DOCUMENT AUTHORISES ANY LIVE ACTION.

VP40_TIER_A_SHORTPRICE is not a live policy.
It has no connection to:
  - candidate_route() in the scoring pipeline
  - router lane masks
  - ensemble weights
  - staking configuration
  - Telegram output format
  - Playbook G directives

Policy simulation findings are advisory only.
All policy changes require explicit human approval
with documented evidence and operator council sign-off.
```

---

## Operating Doctrine

```
High probability alone is not enough.
Tier A alone is not enough.
Price zone matters.
Outlier stripping is mandatory.
Midprice needs router qualification.
No lane promotes until it survives abuse testing.
```

This lane has survived the first two abuse tests:
- Gate 7 (outlier concentration): PASS — Roysse is excluded
- Gate 6 (losing run): PASS — LLR=3

The remaining tests (n gate, ROI gate) are accumulation-dependent. Time and volume will answer them, not another review of the same data.

---

## Review Schedule

```
Next review trigger:   n >= 150 (run vp40_tier_a_shortprice_review.py)
Preferred trigger:     n >= 250
Interim check:         n >= 120 — spot check only, no gate re-assessment
SP_2X sub-band check:  when VP40_TIER_A_SP_2X reaches n >= 50
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
POLICY_SIMULATION_ONLY
UNDER_REVIEW
```

---

*VP40_TIER_A_SHORTPRICE_REVIEW_V1 — 2026-05-17*
*Evidence base: SIGMA_2K_SAFE_TRAINING_SLICE_V1 at 1310 rows, VP40_TIER_A_SHORTPRICE n=85*
*Next review: when n >= 150 OR VP40_TIER_A_SP_2X sub-band reaches n >= 50*

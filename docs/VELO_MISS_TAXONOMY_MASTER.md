# VÉLØ Miss Taxonomy Master
**Generated:** 2026-04-19 | **Base:** 556 misses across 1,070 scored races

---

## Master Table

| Miss Class | Count | % Total | Rank-2 Win | Top-3 Win | Recovery% | Severity | Recoverability |
|------------|-------|---------|-----------|-----------|-----------|----------|----------------|
| mid_priced_won | 241 | 43.3% | 43 (18%) | 71 (29%) | 29.5% | HIGH | PARTIAL |
| market_decoy_followed | 94 | 16.9% | 18 (19%) | 36 (38%) | 38.3% | HIGH | CONDITIONAL |
| outsider_won | 90 | 16.2% | 4 (4%) | 11 (12%) | 12.2% | MEDIUM | LOW |
| short_fav_won | 66 | 11.9% | 21 (32%) | 34 (52%) | 51.5% | LOW | HIGH |
| non_runner_or_untracked | 32 | 5.8% | 3 (9%) | 6 (19%) | 18.8% | LOW | NONE (data) |
| outsider_hedge_omitted | 29 | 5.2% | 2 (7%) | 5 (17%) | 17.2% | MEDIUM | PARTIAL |
| high_confidence_miss | 2 | 0.4% | 0 | 0 | 0% | CRITICAL | UNKNOWN |
| signal_underweighted | 2 | 0.4% | 0 | 2 | 100% | HIGH | HIGH |

---

## Class-by-Class Autopsy

### 1. mid_priced_won — 241 misses (43.3%)
**What happened:** A horse priced 3–20/1 won and we were not on it. This is the single biggest miss class.

**By tier:**
- C: 96 (39.8%)
- B: 63 (26.1%)
- X: 35 (14.5%)
- D: 24 (10.0%)
- A: 12 (5.0%)

**Rank-2 recovery: 29.5% top-3.** Meaning: in roughly 1 in 3 mid-priced-winner races, our top-3 contained the actual winner. We were "close" but not "right."

**Root cause:** The model is built around clear signals (dominant favourites, proven form, market consensus). Mid-priced horses in competitive handicaps win on factors the current feature set does not fully weight: class drop, return from break, stable signals, sectional advantages. These are the features most missing from the current ensemble.

**Recoverability:** PARTIAL. Rank-2 catches 18%, top-3 catches 29%. A 2-horse system recovers ~18% of these misses but does not solve the structural pricing gap in the 5–20 band.

---

### 2. market_decoy_followed — 94 misses (16.9%)
**What happened:** The model followed a market move (shortening horse, steaming favourite) that was manipulated or misleading. The "decoy" horse lost; a different horse (typically 3–8/1) won.

**Track concentration:**
- 70 with no track logged (data quality gap)
- Lingfield AW: 12, Wolverhampton AW: 11, Newcastle AW: 10
- AW decoy rate: 21.7% of all AW misses

**Avg SP of winner in decoy races: 4.8.** These are not outsider beats — a 4–5/1 horse was the real winner that the market knew about before we did.

**Rank-2 recovery: 38.3% top-3.** This is the most recoverable miss class after short_fav_won. When a decoy fires, the winner often IS in our top-3.

**Root cause:** The model's market_deception_score is present but not sufficiently weighted in tier assignment. AW controlled handicaps have structurally different market dynamics — market moves are more often trainer-driven than form-driven.

**Recoverability:** CONDITIONAL. Suppressable via AW decoy filter. Partially recoverable via rank-2 (19%). The long-term fix is market_deception_score threshold gating on AW surfaces.

---

### 3. outsider_won — 90 misses (16.2%)
**What happened:** A horse at 20/1+ won and it was not in our meaningful contention.

**Rank-2 recovery: 12.2% top-3.** Very low. When a 20/1+ horse wins, it is almost never in our top-3.

**Root cause:** Not a model failure — this is genuine variance. The model cannot be calibrated to predict 20/1+ winners reliably without also producing massive false positives. The 5 correct outsider wins (51/1, 41/1, 34/1, 23/1, 21/1) represent the model's outsider detection working at its ceiling.

**Recoverability:** LOW. These are not recoverable via ranking or second picks. Accept them as variance cost.

---

### 4. short_fav_won — 66 misses (11.9%)
**What happened:** A short-priced favourite (typically <3/1) won but was not our pick. We picked a different horse at similar odds.

**Rank-2 recovery: 51.5% top-3.** Highest recoverability class. In half of these races, the winning favourite was already in our top-3.

**Root cause:** Two scenarios:
1. We picked the right race type but wrong horse at similar prices (rank-2 recovery works)
2. We were fooled by a form reversal where the favourite won on class/breeding alone

**Recoverability:** HIGH. 51.5% top-3 coverage means a 2-horse system with both horses at short prices would recover roughly half of these misses. This is the strongest case for the 2-horse system.

---

### 5. non_runner_or_untracked — 32 misses (5.8%)
**What happened:** Our pick was a non-runner, or the result was not tracked in the API. Not a model failure.

**Recoverability:** NONE (data quality issue, not a prediction issue).

---

### 6. outsider_hedge_omitted — 29 misses (5.2%)
**What happened:** There was an outsider signal present in the full_analysis but it was not surfaced. Average SP of winner: 18.0 (range 11–51/1).

**These are the big-price opportunities the model already sees but suppresses.**

**Recoverability:** PARTIAL. These are exactly the races a 2-horse/hedge system is designed for. 7 of the 29 recovered winners were at 10/1+. The ROI case here is significant.

---

## Recoverability Ranking

| Class | Recovery Method | Priority |
|-------|----------------|----------|
| short_fav_won | Rank-2 pick | HIGH — implement first |
| market_decoy_followed | AW decoy filter | HIGH — implement second |
| outsider_hedge_omitted | Longshot hedge surfacing | MEDIUM — prove ROI first |
| mid_priced_won | Better feature engineering | FUTURE — not this cycle |
| outsider_won | Accept variance | NONE |
| non_runner_or_untracked | Data pipeline fix | ADMIN |

---

## What Cannot Be Determined Yet

1. **mutation_contaminated** — no mutation flag in current sigma_audits schema. Cannot quantify.
2. **stale_field / divergence** — no field state tracking persisted. Cannot audit.
3. **winner_seen_but_underweighted** — partial only. Would need full feature-level audit per race.
4. **confidence_overreach** — A-tier has 26 misses (22% of A races). Can we predict A-tier failures? Not yet — sample too small.

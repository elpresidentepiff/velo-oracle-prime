# VÉLØ Candidate Lane Design V1
**Generated:** 2026-04-29 00:17 UTC
**Evidence source:** data/evidence_vault/velo_unified_evidence_audit_v1.json

**This document is DESIGN ONLY. No code was changed. No staking was activated.**

---

## Summary

| Item | Value |
|---|---|
| Shadow candidates | VP30_TIER_A, MARKET_DECEPTION_HIGH, IMPROVEMENT_SCORE_HIGH |
| Watchlist | PLACE_PROB_HIGH |
| Suppress candidates | B_TIER_LOW_VP_SUPPRESS |
| Forensics only | MID_PRICE_WINNER_FORENSICS |
| Highest priority | VP30_TIER_A |
| Highest upside | MARKET_DECEPTION_HIGH (SR=54.8%, n=31) |
| Most proven | VP30_TIER_A (SR=40.1%, n=162, 49-day evidence) |

---

## 🔵 VP30_TIER_A — VP ≥ 0.30 + Tier A

**Status:** SHADOW_CANDIDATE | **Priority:** 1

**Condition:** `velo_prime_prob >= 0.30 AND decision_tier == 'A'`

**Signal sources:** velo_prime_prob, decision_tier

### Evidence

| Metric | Value | vs Global |
|---|---|---|
| n | 162 | baseline n=1249 |
| Strike rate | 40.1% | global 20.6% |
| Frame rate | 77.2% | global 48.4% |
| SR lift | 19.5% | — |
| Avg VP | 0.425 | — |
| Avg winner SP | 2.26 | — |

**Note:** Most miss SPs in 3.25-9.0 range — mid-price zone still the weakness

**Confidence level:** HIGH

**Confidence note:** n=162 across 49 days. Monotonic VP relationship confirms the signal is structural.

### Risks

- Tier A self-selection: these are the system's highest-confidence races — selection bias possible
- Average winner SP=2.26 means wins come from short-priced horses — market may price this in
- 37 misses include 15+ races where short favourites won — short-fav override needed
- Miss SP avg=7.12: mid-price winner problem persists even in this lane

### Promotion Gates

- **shadow_candidate_entry:** n=162 (already passed — evidence exists)
- **first_review:** n=200 qualifying results
- **paper_execution_gate:** n=300, SR≥35%, Frame≥70%, no freeze triggered
- **live_discussion_gate:** n=500, multi-month track record, SR≥30%, Frame≥70%
- **live_activation:** NEVER without explicit operator decision + legal review

### Freeze Conditions

- SR drops below 20.0% at n≥30 (global baseline — no lift = no point)
- Frame drops below 55.0% at n≥30
- 6+ consecutive losses at any sample size
- ROI turns negative and stays negative for 20+ races at n≥50

---

## 🔵 MARKET_DECEPTION_HIGH — Market Deception Score > 0.50

**Status:** SHADOW_CANDIDATE | **Priority:** 2

**Condition:** `market_deception_score > 0.50`

**Signal sources:** market_deception_score

### Evidence

| Metric | Value | vs Global |
|---|---|---|
| n | 31 | baseline n=1249 |
| Strike rate | 54.8% | global 20.6% |
| Frame rate | 96.8% | global 48.4% |
| SR lift | 34.2% | — |

**Note:** Frame=96.8% means almost every pick finishes in the top 3. SR=54.8% means over half win outright. This is the highest-lift sidecar in the system. n=31 is promising but not yet sufficient for full confidence. CAUTION: In A/B routing, high MDS was historically treated as DECOY risk. The evidence here directly contradicts that assumption. Polarity flip confirmed: high MDS in velo_verdicts = model-backed signal, not decoy.

**Confidence level:** PROMISING_HIGH_UPSIDE

**Confidence note:** n=31 clears the INSUFFICIENT threshold but remains small. SR=54.8% is extraordinary. Must track for regression — if SR drops to 30-35% range it may still be valuable but the current numbers could be a small-sample peak.

### Risks

- n=31: small sample — single regression patch could drop SR significantly
- Polarity confusion: MDS was previously used as a decoy blocker. If any code path still treats MDS>0.5 as a negative signal, this lane will self-contradict
- MDS>0.5 fires on ~2% of predictions — very low volume, slow ledger accumulation
- Frame=96.8% at n=31 is likely to regress toward 80-85% at n=100 — still excellent but not 97%
- No SP filter applied: winning at any price. If most wins are short-priced (SP<2), ROI may be limited despite high SR

### Promotion Gates

- **shadow_candidate_entry:** IMMEDIATE — evidence sufficient to start shadow tracking
- **first_review:** n=50 qualifying results
- **paper_execution_gate:** n=80, SR≥40%, Frame≥80%, positive ROI, no freeze
- **live_discussion_gate:** n=100, multi-month track record, SR≥35%
- **live_activation:** NEVER without explicit operator decision + legal review

### Freeze Conditions

- SR drops below 25.0% at n≥20 (still above global but serious regression from 54.8%)
- Frame drops below 65.0% at n≥20 (regression from 96.8%)
- 5+ consecutive losses at any sample size
- ROI negative for 15+ consecutive races at n≥30

---

## 🔵 IMPROVEMENT_SCORE_HIGH — Improvement Score > 0.40

**Status:** SHADOW_CANDIDATE | **Priority:** 3

**Condition:** `improvement_score > 0.40`

**Signal sources:** improvement_score

### Evidence

| Metric | Value | vs Global |
|---|---|---|
| n | 62 | baseline n=1249 |
| Strike rate | 43.5% | global 20.6% |
| Frame rate | 82.3% | global 48.4% |
| SR lift | 22.9% | — |

**Note:** The improvement specialist model identifies horses about to step forward in performance. SR=43.5% at n=62 is the second-highest SR in the system. Frame=82.3% means picks are competitive in 5 of 6 races. This is a consistently strong signal with a meaningful sample.

**Confidence level:** HIGH

**Confidence note:** n=62 is a meaningful sample. SR=43.5% at this size is convincing. The improvement model is one of 7 specialist models — it fires selectively.

### Risks

- Improvement score fires on horses showing forward form — these may already be short-priced, limiting ROI
- The improvement model was trained on historical data — may not generalise to unusual going/class combinations
- n=62: at the lower end of confidence — need 100+ for full PROVEN status
- Interaction with MDS: a horse showing improvement in a deceptive market may fire both signals — avoid double-counting

### Promotion Gates

- **shadow_candidate_entry:** IMMEDIATE — evidence sufficient
- **first_review:** n=80 qualifying results
- **paper_execution_gate:** n=120, SR≥35%, Frame≥75%, positive ROI
- **live_discussion_gate:** n=150, SR≥30%, Frame≥72%
- **live_activation:** NEVER without explicit operator decision + legal review

### Freeze Conditions

- SR drops below 22.0% at n≥30
- Frame drops below 60.0% at n≥30
- 6+ consecutive losses
- ROI negative for 20+ consecutive races at n≥50

---

## 🟡 PLACE_PROB_HIGH — Place Probability > 0.80

**Status:** WATCHLIST | **Priority:** 4

**Condition:** `place_prob > 0.80`

**Signal sources:** place_prob

### Evidence

| Metric | Value | vs Global |
|---|---|---|
| n | 392 | baseline n=1249 |
| Strike rate | 31.6% | global 20.6% |
| Frame rate | 66.8% | global 48.4% |
| SR lift | 11.0% | — |

**Note:** SR=31.6% at n=392 is the largest sample of any sidecar signal. Frame=66.8% is slightly below the 70% target but with 392 races it is statistically significant. This signal fires frequently — 392 from 1391 total = 28% of all predictions. Lift of +11% SR over global baseline is consistent and meaningful at this scale.

**Confidence level:** WATCHLIST_GOOD

**Confidence note:** Large sample (n=392) but frame rate misses the 70% target. The signal provides meaningful lift without exceptional performance. WATCHLIST not SHADOW_CANDIDATE because it does not differentiate winners sharply enough on its own.

### Risks

- Frame=66.8% is just below the 70% target — may be a ceiling effect for the place_prob specialist
- High coverage (28% of all predictions) means it is not selective — needs combination with VP or tier filter
- The place_prob model is optimised for placement, not wins — SR=31.6% may be the ceiling for this signal alone
- Combining with VP≥0.30 may create a stronger combined lane — test separately

### Promotion Gates

- **watchlist_entry:** IMMEDIATE — already at n=392
- **shadow_candidate_gate:** n=500, combined with VP≥0.30 filter, SR≥28%, Frame≥68%
- **paper_execution_gate:** n=700, SR≥25%, Frame≥68%, positive ROI over 6+ months
- **live_discussion_gate:** n=1000
- **live_activation:** NEVER without explicit operator decision + legal review

### Freeze Conditions

- SR drops below 20.0% (global baseline) at n≥100
- Frame drops below 55.0% at n≥100
- 10+ consecutive losses

---

## 🔴 B_TIER_LOW_VP_SUPPRESS — Tier B VP < 0.30 — Suppress Candidate

**Status:** SUPPRESS_CANDIDATE | **Priority:** 5

**Condition:** `decision_tier == 'B' AND velo_prime_prob < 0.30`

**Signal sources:** decision_tier, velo_prime_prob

### Evidence

| Metric | Value | vs Global |
|---|---|---|
| n | 272 | baseline n=1249 |
| Strike rate | 16.9% | global 20.6% |
| Frame rate | 44.1% | global 48.4% |
| SR lift | -3.7% | — |
| Avg VP | 0.245 | — |
| Avg winner SP | 4.93 | — |

**Note:** SR=16.9% is below global baseline. These predictions have negative lift (-3.7%). Suppressing them gains only +1.0% SR and +1.2% frame but loses 21.8% coverage. The gain is modest. The direction is confirmed: these are drag. Suppression is an operator decision, not automatic.

**Confidence level:** CONFIRMED_DRAG

**Confidence note:** n=272 is conclusive. SR=16.9% across 49 days is consistently below baseline. This is not a signal — it is a noise band.

### Risks

- Coverage loss: removing 272 races loses 21.8% of daily prediction volume
- Some Tier B VP<0.30 races may be E/W candidates — suppressing them removes potential placed returns
- The gain (+1% SR) is statistically real but operationally modest
- If the VP calibration improves, some currently VP<0.30 B-tier races may become VP≥0.30 — suppression rule should be reviewed after any model update

### Suppression Protocol

- **what_to_suppress:** All Tier B predictions where velo_prime_prob < 0.30
- **where:** Any future candidate lane design — do not include these in lane pass criteria
- **not_where:** Do not change the production sigma output — all predictions still reported to Telegram
- **activation_requires:** Explicit operator decision — do not auto-suppress
- **review_trigger:** After any model update that changes VP calibration

---

## 🔬 MID_PRICE_WINNER_FORENSICS — Mid-Priced Winner Forensics Lane (SP 3.0–8.5)

**Status:** FORENSICS_ONLY | **Priority:** 6

**Condition:** `outcome == 'MISS' AND actual_winner_sp between 3.0 and 8.5`

**Signal sources:** actual_winner_sp, miss_reason, outcome

### Evidence

| Metric | Value | vs Global |
|---|---|---|
| n | — | baseline n=1249 |
| Strike rate | —% | global 20.6% |
| Frame rate | —% | global 48.4% |
| SR lift | —% | — |

**Note:** This is not a promotion lane. It is a research diagnostic. VÉLØ is missing 279 mid-priced winners across 49 days. These are races where the model competed but ranked the wrong horse first. The winner was visible to the market (SP 3–8.5 = legitimate contender). Research question: what distinguishes the SP 3–8.5 winner from VÉLØ's pick?

**Confidence level:** FORENSICS

**Confidence note:** This is a diagnostic lane only. There is no promotion path.

### Research Questions

- What features do SP 3–8.5 winners carry that VÉLØ's picks do not?
- Is there a specific tier/archetype combination where mid-price misses cluster?
- Are mid-price misses correlated with specific courses or going conditions?
- Does the place_prob or improvement signal fire on the actual winner in these cases?
- Is the VÉLØ pick framing in these races (finishing 2nd/3rd) or missing entirely?
- What is the VP score of the actual SP 3–8.5 winner in races where VÉLØ missed?

---

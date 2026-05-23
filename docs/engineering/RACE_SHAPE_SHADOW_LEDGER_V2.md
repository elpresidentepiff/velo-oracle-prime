# Race Shape Shadow Ledger V2 — Design Note

**Date:** 2026-05-23  
**Status:** DESIGN_PENDING — awaiting corpus accumulation  
**Classification:** Research protocol only. No scoring integration, no model changes.

---

## V1 Finding Summary

Shadow ledger V1 (May 22, n=36):

| Metric | Value |
|---|---|
| Total races | 36 |
| Shape-warned | 31/36 (86%) |
| SR when warned | 22.6% |
| SR when silent | 40.0% |
| Discriminative power | 17pp |
| Winner visible (misses) | 92.6% (25/27) |
| Winner ranked 2nd/3rd | 48.1% (13/27) |

**V1 verdict:** Discriminative (17pp lift) but too broad to be actionable. 86% warn rate means the signal is nearly always firing. A suppression gate that fires on 86% of races adds noise, not precision.

---

## Why V1 Warns Too Broadly

FAV_VULNERABLE dominates the classification (23/36 = 64%). The threshold `top_vp < 0.20` fires on any race where the engine's top pick has VP below 20% — which covers most races, since VP ≥ 0.20 is the baseline signal gate.

| Shape Status | n | % of total |
|---|---|---|
| FAV_VULNERABLE | 23 | 64% |
| MIDPRICE_TRAP | 5 | 14% |
| CLEAR_TOP | 3 | 8% |
| COMPRESSED | 2 | 6% |
| CHAOTIC | 1 | 3% |
| UNKNOWN | 2 | 6% |

---

## V2 Precision Hypothesis

**Hypothesis:** High-miss-risk races are not simply "VP is low" — they have a specific structure: the favourite is vulnerable AND the market is ultra-compressed (no clear second-best), funnelling money into a winner the engine under-rates.

V2 seeks high-precision subsets with SR ≤ 22% and warn rate ≤ 30% (vs V1's 86%).

---

## V2 Precision Candidates (from V1 audit, n=36)

Identified by `scripts/audit_race_shape_precision.py`:

| Subset | n | SR | Verdict | Notes |
|---|---|---|---|---|
| FAV_VULN_ULTRA_COMPRESSED (vp_spread_top3 < 0.01) | 16 | 18.8% | ACTIONABLE_RISK_FLAG (provisional) | 44% of all races — still broad |
| MIDPRICE_TRAP (midprice_density ≥ 0.45) | 5 | 20.0% | ACTIONABLE_RISK_FLAG (provisional) | n=5 too small to confirm |
| FAV_VULNERABLE (all) | 23 | 26.1% | BROAD_WARNING_ONLY | Confirms V1 |
| SHAPE_WARNED (all V1 statuses) | 31 | 22.6% | BROAD_WARNING_ONLY | V1 result |

**Strongest V2 candidate:** `FAV_VULN_ULTRA_COMPRESSED` — races where `top_vp < 0.20 AND vp_spread_top3 < 0.01`. These are markets with no credible favourite AND near-zero VP separation in the top 3. SR=18.8% at n=16.

**Note:** All verdicts are provisional at n=36. Confirmation requires n ≥ 300.

---

## V2 Shadow Ledger — Design Spec

### New Features to Track (per race)

| Feature | Description | Purpose |
|---|---|---|
| `fav_vuln_ultra_compressed` | top_vp < 0.20 AND vp_spread_top3 < 0.01 | Strongest V2 candidate |
| `midprice_trap_strict` | midprice_density ≥ 0.45 AND vp_spread_top3 ≥ 0.08 | MIDPRICE_TRAP with clear VP separation |
| `winner_sp_quartile` | SP band of winner: 1 (≤3.0), 2 (3.0–5.5), 3 (5.5–8.5), 4 (>8.5) | Midprice zone detail |
| `vp_spread_rank_gap` | VP gap between rank-1 and rank-2 horse | Sharpness of top pick |

### V2 Warn Criteria (draft — needs 300+ corpus to confirm)

```
V2_PRECISION_WARN = (
    fav_vuln_ultra_compressed  # top_vp < 0.20 AND vp_spread_top3 < 0.01
    OR midprice_trap_strict    # midprice_density >= 0.45 AND clear VP separation
)
```

Target: SR ≤ 22% with warn rate ≤ 35%.

---

## Promotion Gates

| Gate | Threshold | Current Status |
|---|---|---|
| Corpus minimum | 300+ races | 36/300 (12%) |
| FAV_VULN_ULTRA_COMPRESSED confirm | n ≥ 50, SR ≤ 22% | n=16 provisional |
| MIDPRICE_TRAP confirm | n ≥ 20, SR ≤ 22% | n=5 provisional |
| V2 warn rate target | ≤ 35% | Not tested (needs corpus) |
| Operator approval | Required before any scoring integration | Not sought |

---

## Research Protocol

1. Run `scripts/build_race_shape_shadow_ledger.py --date YYYY-MM-DD` daily
2. Run `scripts/audit_race_shape_precision.py` weekly or after each new 50-race batch
3. Track FAV_VULN_ULTRA_COMPRESSED and MIDPRICE_TRAP SR as corpus grows
4. Do NOT adjust VP scores or suppression gates based on V1 evidence alone
5. First review gate: corpus reaches 150 races (≈50 more race days)
6. V2 implementation gate: corpus reaches 300+ races with stable precision subsets

---

## What V2 Does NOT Do

```
No VP score changes
No suppression of top-pick presentation
No routing changes
No Telegram format changes
No staking changes
No model promotion
```

V2 is shadow tracking only. It adds precision columns to the ledger and identifies when a race-shape pattern is associated with above-average miss risk. The operator decides whether to act on that information.

---

## Winner Visibility Insight

92.6% of miss winners were visible in pre-race snapshots. 48.1% ranked 2nd or 3rd in VP. This confirms the miss structure is **ranking failure, not coverage failure** — the engine sees the winner but doesn't rate it highly enough. This is a VP calibration signal, not a race shape signal.

Implication: V2 race shape analysis should focus on identifying when the engine's ranking is unreliable, not on filtering races out.

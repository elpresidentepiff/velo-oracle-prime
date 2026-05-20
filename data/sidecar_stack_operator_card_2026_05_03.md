# SIDECAR STACK OPERATOR CARD — 2026-05-03

```
STATUS:             OPERATOR_VISIBILITY_ONLY
SCORING_CHANGES:    NO
MODEL_CHANGES:      NO
SQPE_CHANGES:       NO
ROUTER_CHANGES:     NO
STAKING:            NO
LIVE_EXECUTION:     NO
TELEGRAM_ALERTS:    NO
PURPOSE:            Sidecar stack operator intelligence panel
```

---

## THRESHOLDS

| Threshold | Value | Source |
|---|---:|---|
| VP30 (velo_prime_prob >=) | 0.30 | place_signal_classifier.py |
| MDS_HIGH (market_deception_score >) | 0.50 | place_signal_classifier.py |
| IMPROVE_HIGH (improvement_score >) | 0.40 | place_signal_classifier.py |

---

## STACK SUMMARY

| Stack | Definition | Count |
|---|---|---:|
| ELITE_STACK | Tier A + VP≥0.30 + MDS>0.50 | 1 |
| STRONG_STACK_PLUS | VP≥0.30 + MDS>0.50 + IMP>0.40 | 0 |
| STRONG_STACK | VP≥0.30 + MDS>0.50 (no IMP) | 1 |
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 1 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 20 |
| SUPPRESS | Tier B + VP<0.30 | 2 |

**Total races scanned:** 36  
**VP30 selections:** 22

---

## A. ELITE STACK — Tier A + VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 2:05 | Hamilton | Aspire Cleaning & Facilities Ltd No | **Westport** | A | 0.833 | 0.771 | 0.290 | 0.949 | OK | TIER_A VP30 MDS_HIGH |

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 2:05 | Hamilton | Aspire Cleaning & Facilities Ltd No | **Westport** | A | 0.833 | 0.771 | 0.290 | 0.949 | OK | TIER_A VP30 MDS_HIGH |

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 4:20 | Salisbury | Fitzdares Extra Places Every Day EB | **Ranga Tang** | B | 0.350 | 0.360 | 0.451 | 0.992 | OK | VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (20)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 3:15 | Hamilton | Darley Stallions EBF Novice Stakes  | **Conclave** | A | 0.682 | 0.404 | 0.147 | 0.968 | OK | TIER_A VP30 |
| 1:30 | Salisbury | Find Us At fitzdares.com Amateur Jo | **Moonhall Lass** | B | 0.606 | 0.128 | 0.039 | 0.509 | OK | VP30 |
| 4:10 | Newmarket | Tattersalls £40,000 EBF Fillies' No | **Call Me Tomorrow** | B | 0.498 | 0.173 | 0.116 | 0.661 | OK | VP30 |
| 4:50 | Cork | Irish Stallion Farms EBF Median Auc | **Yousaynothingatall** | B | 0.455 | 0.249 | 0.386 | 0.885 | OK | VP30 |
| 2:00 | Salisbury | Fitzdares Fillies' Conditions Stake | **Ziggy Starshine** | A | 0.444 | 0.175 | 0.084 | 0.666 | OK | TIER_A VP30 |
| 5:35 | Hamilton | Racing TV Handicap | **Alpine Sierra** | B | 0.377 | 0.092 | 0.088 | 0.991 | OK | VP30 |
| 3:10 | Salisbury | Download The Fitzdares App Novice S | **Poetry Of Time** | B | 0.376 | 0.192 | 0.119 | 0.643 | OK | VP30 |
| 3:48 | Salisbury | Call Fitzdares For Top Prices Filli | **Siam Ruby** | B | 0.373 | 0.065 | 0.015 | 0.848 | OK | VP30 |
| 2:40 | Hamilton | Heineken Buttonhook Handicap (GBBPl | **Humble Spark** | B | 0.372 | 0.053 | 0.082 | 0.972 | OK | VP30 |
| 4:15 | Cork | Racing Again Sunday, May 10th Appre | **Grey Intentions** | A | 0.357 | 0.047 | 0.156 | 0.450 | OK | TIER_A VP30 |
| 2:10 | Sligo | Tote.ie Median Auction Maiden | **County Carlow** | B | 0.354 | 0.266 | 0.203 | 0.487 | OK | VP30 |
| 5:27 | Cork | Irish Stallion Farms EBF (C & G) Ma | **Atomic City** | C | 0.349 | 0.273 | 0.251 | 0.432 | OK | VP30 |
| 1:20 | Cork | Irish EBF Auction Series Maiden (IR | **Matriarchal** | C | 0.349 | 0.237 | 0.396 | 0.613 | OK | VP30 |
| 4:32 | Sligo | Web The Tool Company Handicap | **Creative Dancer** | X | 0.348 | 0.013 | 0.079 | 0.332 | OK | VP30 |
| 3:58 | Sligo | Irish Stallion Farms EBF Fillies Ha | **God Knows** | B | 0.335 | 0.017 | 0.081 | 0.584 | OK | VP30 |
| 2:35 | Salisbury | Track Radio Launches Tomorrow Handi | **Over Spiced** | B | 0.328 | 0.025 | 0.026 | 0.865 | OK | VP30 |
| 5:20 | Newmarket | HKJC World Pool Handicap (GBBPlus R | **Study Of Words** | C | 0.326 | 0.079 | 0.015 | 0.815 | OK | VP30 |
| 3:53 | Hamilton | Aspire Cleaning & Facilities Throug | **Starliner** | B | 0.326 | 0.064 | 0.182 | 0.989 | OK | VP30 |
| 1:45 | Newmarket | Oliver Brown Pretty Polly Stakes (L | **Sacred Ground** | C | 0.306 | 0.083 | 0.066 | 0.850 | OK | VP30 |
| 3:05 | Cork | Goffs Irish EBF Polonia Stakes (Lis | **Havana Anna** | B | 0.301 | 0.050 | 0.337 | 0.918 | OK | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (2)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 1:35 | Sligo | Download The Tote App Fillies Maide | **Baiana** | B | 0.295 | 0.067 | 0.119 | 0.740 | OK |  |
| 5:07 | Sligo | Apex Controls Ltd. Handicap | **Pliny** | B | 0.247 | 0.065 | 0.203 | 0.628 | OK |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-05-03T11:36:14.519484+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
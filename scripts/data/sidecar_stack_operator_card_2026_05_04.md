# SIDECAR STACK OPERATOR CARD — 2026-05-04

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
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 3 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 42 |
| SUPPRESS | Tier B + VP<0.30 | 9 |

**Total races scanned:** 95  
**VP30 selections:** 46

---

## A. ELITE STACK — Tier A + VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| — | — | — | **?** | A | 0.839 | 0.771 | 0.290 | 0.949 | TIER_A VP30 MDS_HIGH |

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| — | — | — | **?** | A | 0.839 | 0.771 | 0.290 | 0.949 | TIER_A VP30 MDS_HIGH |

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (3)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 1:15 | Curragh | Irish EBF Median Sires Series Maide | **?** | B | 0.462 | 0.206 | 0.608 | 0.890 | VP30 IMP_HIGH |
| — | — | — | **?** | B | 0.355 | 0.380 | 0.451 | 0.992 | VP30 IMP_HIGH |
| 1:35 | Down Royal | Ballygowan Maiden Hurdle | **?** | B | 0.302 | 0.241 | 0.456 | 0.953 | VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (42)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| — | — | — | **?** | A | 0.675 | 0.404 | 0.147 | 0.968 | TIER_A VP30 |
| — | — | — | **?** | B | 0.639 | 0.138 | 0.039 | 0.561 | VP30 |
| 2:30 | Beverley | EBF Restricted Maiden Stakes (Band  | **?** | B | 0.518 | 0.236 | 0.383 | 0.830 | VP30 |
| 5:48 | Fakenham | Break Mares' Handicap Hurdle | **?** | A | 0.500 | 0.017 | 0.077 | 0.742 | TIER_A VP30 |
| — | — | — | **?** | B | 0.492 | 0.186 | 0.116 | 0.681 | VP30 |
| 2:18 | Fakenham | Each The Nook Novices' Handicap Hur | **?** | A | 0.491 | 0.064 | 0.184 | 0.960 | TIER_A VP30 |
| 4:30 | Down Royal | C&C White Maiden Hunters Chase | **?** | A | 0.482 | 0.138 | 0.112 | 0.433 | TIER_A VP30 |
| 3:05 | Beverley | Mayday Fillies' Novice Stakes (GBB  | **?** | A | 0.471 | 0.186 | 0.114 | 0.784 | TIER_A VP30 |
| 3:28 | Fakenham | Heritage House Mares' Maiden Hurdle | **?** | B | 0.462 | 0.097 | 0.043 | 0.471 | VP30 |
| — | — | — | **?** | B | 0.459 | 0.249 | 0.386 | 0.885 | VP30 |
| 2:45 | Down Royal | Pepsi Max Hurdle | **?** | A | 0.418 | 0.272 | 0.271 | 0.972 | TIER_A VP30 |
| 4:25 | Warwick | M&T Solicitors In Warwick Handicap  | **?** | B | 0.415 | 0.092 | 0.108 | 0.726 | VP30 |
| — | — | — | **?** | A | 0.414 | 0.149 | 0.084 | 0.647 | TIER_A VP30 |
| 2:40 | Warwick | Moore & Tibbits Family Fun Day Mare | **?** | B | 0.412 | 0.341 | 0.382 | 0.957 | VP30 |
| — | — | — | **?** | C | 0.400 | 0.350 | 0.251 | 0.434 | VP30 |
| — | — | — | **?** | B | 0.390 | 0.102 | 0.088 | 0.990 | VP30 |
| 1:50 | Curragh | AES Recycling First Flier Stakes (L | **?** | B | 0.386 | 0.129 | 0.082 | 0.518 | VP30 |
| — | — | — | **?** | B | 0.378 | 0.072 | 0.082 | 0.983 | VP30 |
| — | — | — | **?** | B | 0.374 | 0.065 | 0.015 | 0.848 | VP30 |
| 2:35 | Kempton (AW) | McCaffertys Bars Maiden Stakes (GBB | **?** | B | 0.371 | 0.185 | 0.385 | 0.735 | VP30 |
| — | — | — | **?** | B | 0.357 | 0.015 | 0.081 | 0.570 | VP30 |
| — | — | — | **?** | C | 0.353 | 0.294 | 0.345 | 0.731 | VP30 |
| 1:53 | Windsor | Cuthy's Race Sponsored By TTC Handi | **?** | B | 0.347 | 0.011 | 0.082 | 0.628 | VP30 |
| 4:20 | Kempton (AW) | Brooke Handicap (London Mile Series | **?** | B | 0.347 | 0.036 | 0.115 | 0.944 | VP30 |
| — | — | — | **?** | B | 0.341 | 0.252 | 0.203 | 0.465 | VP30 |
| 1:57 | Beverley | EBF Restricted Maiden Stakes (Band  | **?** | B | 0.340 | 0.174 | 0.328 | 0.607 | VP30 |
| — | — | — | **?** | A | 0.339 | 0.031 | 0.156 | 0.486 | TIER_A VP30 |
| 4:10 | Curragh | Clem Murphy Memorial Irish EBF Moor | **?** | B | 0.335 | 0.404 | 0.136 | 0.998 | VP30 |
| — | — | — | **?** | C | 0.332 | 0.091 | 0.015 | 0.825 | VP30 |
| 2:53 | Fakenham | Norfolk Wildlife Trust Centenary Ma | **?** | C | 0.332 | 0.020 | 0.030 | 0.739 | VP30 |
| — | — | — | **?** | B | 0.325 | 0.058 | 0.182 | 0.989 | VP30 |
| — | — | — | **?** | B | 0.325 | 0.098 | 0.220 | 0.607 | VP30 |
| 5:35 | Warwick | Racing To School Celebrating 25 Yea | **?** | B | 0.325 | 0.073 | 0.077 | 0.708 | VP30 |
| 3:50 | Warwick | Hazelton Mountford Insurance Broker | **?** | C | 0.318 | 0.081 | 0.075 | 0.867 | VP30 |
| — | — | — | **?** | B | 0.316 | 0.026 | 0.026 | 0.835 | VP30 |
| 2:58 | Windsor | Cameron Smart Memorial Novice Stake | **?** | B | 0.315 | 0.166 | 0.235 | 0.520 | VP30 |
| 3:35 | Curragh | Coolmore Auguste Rodin Irish EBF At | **?** | B | 0.311 | 0.029 | 0.100 | 0.666 | VP30 |
| — | — | — | **?** | B | 0.309 | 0.088 | 0.119 | 0.758 | VP30 |
| 4:00 | Bath | Carers Centre Charity Handicap (Bat | **?** | C | 0.309 | 0.081 | 0.030 | 0.375 | VP30 |
| — | — | — | **?** | C | 0.306 | 0.086 | 0.066 | 0.851 | VP30 |
| 2:23 | Windsor | Betwright Windsor Flat Season Opene | **?** | C | 0.305 | 0.101 | 0.087 | 0.291 | VP30 |
| 2:25 | Curragh | Coolmore Stud Henry Longfellow Iris | **?** | C | 0.300 | 0.037 | 0.054 | 0.696 | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (9)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 3:15 | Warwick | Moore & Tibbits Solicitors Handicap | **?** | B | 0.299 | 0.017 | 0.081 | 0.531 |  |
| 3:25 | Bath | Pins And Putts Handicap | **?** | B | 0.294 | 0.031 | 0.083 | 0.922 |  |
| — | — | — | **?** | B | 0.292 | 0.050 | 0.337 | 0.918 |  |
| 2:00 | Kempton (AW) | Shooting Star EBF Novice Stakes (GB | **?** | B | 0.282 | 0.112 | 0.208 | 0.346 |  |
| — | — | — | **?** | B | 0.261 | 0.069 | 0.203 | 0.665 |  |
| 3:55 | Down Royal | Club Mixers Handicap Chase | **?** | B | 0.255 | 0.038 | 0.070 | 0.628 |  |
| 3:10 | Kempton (AW) | McCaffertys Bars Maiden Stakes (GBB | **?** | B | 0.247 | 0.162 | 0.338 | 0.920 |  |
| 5:53 | Windsor | Daily Prize Wheel At Betwright.com  | **?** | B | 0.235 | 0.017 | 0.079 | 0.899 |  |
| 5:10 | Bath | Droneart Show May 8th Handicap | **?** | B | 0.224 | 0.069 | 0.022 | 0.323 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-05-04T07:25:47.123127+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
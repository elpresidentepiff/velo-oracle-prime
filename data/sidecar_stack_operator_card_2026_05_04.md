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
| ELITE_STACK | Tier A + VP≥0.30 + MDS>0.50 | 0 |
| STRONG_STACK_PLUS | VP≥0.30 + MDS>0.50 + IMP>0.40 | 0 |
| STRONG_STACK | VP≥0.30 + MDS>0.50 (no IMP) | 0 |
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 2 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 23 |
| SUPPRESS | Tier B + VP<0.30 | 7 |

**Total races scanned:** 59  
**VP30 selections:** 25

---

## A. ELITE STACK — Tier A + VP30 + MDS (0)

*No signals for this stack today.*

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (0)

*No signals for this stack today.*

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (2)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 1:15 | Curragh | Irish EBF Median Sires Series Maide | **Ischgl** | B | 0.462 | 0.206 | 0.608 | 0.890 | OK | VP30 IMP_HIGH |
| 1:35 | Down Royal | Ballygowan Maiden Hurdle | **Theflyingking** | B | 0.302 | 0.241 | 0.456 | 0.953 | OK | VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (23)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 2:30 | Beverley | EBF Restricted Maiden Stakes (Band  | **Lady Dublin** | B | 0.518 | 0.236 | 0.383 | 0.830 | OK | VP30 |
| 5:48 | Fakenham | Break Mares' Handicap Hurdle | **Masonbrook Meadow** | A | 0.500 | 0.017 | 0.077 | 0.742 | OK | TIER_A VP30 |
| 2:18 | Fakenham | Each The Nook Novices' Handicap Hur | **Path Of Stars** | A | 0.491 | 0.064 | 0.184 | 0.960 | OK | TIER_A VP30 |
| 4:30 | Down Royal | C&C White Maiden Hunters Chase | **Focus Point** | A | 0.482 | 0.138 | 0.112 | 0.433 | OK | TIER_A VP30 |
| 3:05 | Beverley | Mayday Fillies' Novice Stakes (GBB  | **Donna Rumma** | A | 0.471 | 0.186 | 0.114 | 0.784 | OK | TIER_A VP30 |
| 3:28 | Fakenham | Heritage House Mares' Maiden Hurdle | **Mighty Fleur** | B | 0.462 | 0.097 | 0.043 | 0.471 | OK | VP30 |
| 2:45 | Down Royal | Pepsi Max Hurdle | **Timeless Treaty** | A | 0.418 | 0.272 | 0.271 | 0.972 | OK | TIER_A VP30 |
| 4:25 | Warwick | M&T Solicitors In Warwick Handicap  | **Full Force Gale** | B | 0.415 | 0.092 | 0.108 | 0.726 | OK | VP30 |
| 2:40 | Warwick | Moore & Tibbits Family Fun Day Mare | **Great Dance** | B | 0.412 | 0.341 | 0.382 | 0.957 | OK | VP30 |
| 1:50 | Curragh | AES Recycling First Flier Stakes (L | **Star Prospect** | B | 0.386 | 0.129 | 0.082 | 0.518 | OK | VP30 |
| 2:35 | Kempton (AW) | McCaffertys Bars Maiden Stakes (GBB | **Noble Vow** | B | 0.371 | 0.185 | 0.385 | 0.735 | OK | VP30 |
| 1:53 | Windsor | Cuthy's Race Sponsored By TTC Handi | **Forever Glamorous** | B | 0.347 | 0.011 | 0.082 | 0.628 | OK | VP30 |
| 4:20 | Kempton (AW) | Brooke Handicap (London Mile Series | **Valentine Boy** | B | 0.347 | 0.036 | 0.115 | 0.944 | OK | VP30 |
| 1:57 | Beverley | EBF Restricted Maiden Stakes (Band  | **Furturra** | B | 0.340 | 0.174 | 0.328 | 0.607 | OK | VP30 |
| 4:10 | Curragh | Clem Murphy Memorial Irish EBF Moor | **Minnie Hauk** | B | 0.335 | 0.404 | 0.136 | 0.998 | OK | VP30 |
| 2:53 | Fakenham | Norfolk Wildlife Trust Centenary Ma | **Annie Nail** | C | 0.332 | 0.020 | 0.030 | 0.739 | OK | VP30 |
| 5:35 | Warwick | Racing To School Celebrating 25 Yea | **Luna Run** | B | 0.325 | 0.073 | 0.077 | 0.708 | OK | VP30 |
| 3:50 | Warwick | Hazelton Mountford Insurance Broker | **Cinderello** | C | 0.318 | 0.081 | 0.075 | 0.867 | OK | VP30 |
| 2:58 | Windsor | Cameron Smart Memorial Novice Stake | **Decade Of Time** | B | 0.315 | 0.166 | 0.235 | 0.520 | OK | VP30 |
| 3:35 | Curragh | Coolmore Auguste Rodin Irish EBF At | **Black Caviar Gold** | B | 0.311 | 0.029 | 0.100 | 0.666 | OK | VP30 |
| 4:00 | Bath | Carers Centre Charity Handicap (Bat | **Takincareofbizness** | C | 0.309 | 0.081 | 0.030 | 0.375 | OK | VP30 |
| 2:23 | Windsor | Betwright Windsor Flat Season Opene | **Beauty Box** | C | 0.305 | 0.101 | 0.087 | 0.291 | OK | VP30 |
| 2:25 | Curragh | Coolmore Stud Henry Longfellow Iris | **Neolithic** | C | 0.300 | 0.037 | 0.054 | 0.696 | OK | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (7)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 3:15 | Warwick | Moore & Tibbits Solicitors Handicap | **Neigh Botha** | B | 0.299 | 0.017 | 0.081 | 0.531 | OK |  |
| 3:25 | Bath | Pins And Putts Handicap | **Diomed Spirit** | B | 0.294 | 0.031 | 0.083 | 0.922 | OK |  |
| 2:00 | Kempton (AW) | Shooting Star EBF Novice Stakes (GB | **From Me To You** | B | 0.282 | 0.112 | 0.208 | 0.346 | OK |  |
| 3:55 | Down Royal | Club Mixers Handicap Chase | **Hardy Diamond** | B | 0.255 | 0.038 | 0.070 | 0.628 | OK |  |
| 3:10 | Kempton (AW) | McCaffertys Bars Maiden Stakes (GBB | **Gris De Chine** | B | 0.247 | 0.162 | 0.338 | 0.920 | OK |  |
| 5:53 | Windsor | Daily Prize Wheel At Betwright.com  | **Moonlit Cloud** | B | 0.235 | 0.017 | 0.079 | 0.899 | OK |  |
| 5:10 | Bath | Droneart Show May 8th Handicap | **Mali Star** | B | 0.224 | 0.069 | 0.022 | 0.323 | OK |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-05-04T07:29:03.157623+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
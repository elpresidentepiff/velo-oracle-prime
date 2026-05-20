# SIDECAR STACK OPERATOR CARD — 2026-05-05

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
| STRONG_STACK | VP≥0.30 + MDS>0.50 (no IMP) | 1 |
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 3 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 33 |
| SUPPRESS | Tier B + VP<0.30 | 7 |

**Total races scanned:** 91  
**VP30 selections:** 37

---

## A. ELITE STACK — Tier A + VP30 + MDS (0)

*No signals for this stack today.*

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 3:18 | Ffos Las | Mickey Bowen 51 Winners Novices' Hu | **Fairye Forth** |  | 0.723 | 0.731 | 0.352 | 0.999 | OK | VP30 MDS_HIGH |

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (3)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| — | — | — | **Ischgl** | B | 0.462 | 0.206 | 0.608 | 0.890 | MISSING:course,off_time | VP30 IMP_HIGH |
| 5:07 | Gowran Park | Societies Welcome At Gowran Park Ma | **The Publican's Son** |  | 0.369 | 0.402 | 0.718 | 0.986 | OK | VP30 IMP_HIGH |
| — | — | — | **Theflyingking** | B | 0.302 | 0.241 | 0.456 | 0.953 | MISSING:course,off_time | VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (33)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 7:47 | Hereford | Green Dragon Hotel Novices' Handica | **Triple Haych** |  | 0.573 | 0.033 | 0.106 | 0.719 | OK | VP30 |
| — | — | — | **Lady Dublin** | B | 0.518 | 0.236 | 0.383 | 0.830 | MISSING:course,off_time | VP30 |
| — | — | — | **Masonbrook Meadow** | A | 0.500 | 0.017 | 0.077 | 0.742 | MISSING:course,off_time | TIER_A VP30 |
| — | — | — | **Path Of Stars** | A | 0.491 | 0.064 | 0.184 | 0.960 | MISSING:course,off_time | TIER_A VP30 |
| — | — | — | **Focus Point** | A | 0.482 | 0.138 | 0.112 | 0.433 | MISSING:course,off_time | TIER_A VP30 |
| — | — | — | **Donna Rumma** | A | 0.471 | 0.186 | 0.114 | 0.784 | MISSING:course,off_time | TIER_A VP30 |
| — | — | — | **Mighty Fleur** | B | 0.462 | 0.097 | 0.043 | 0.471 | MISSING:course,off_time | VP30 |
| 6:38 | Gowran Park | Irish Stallion Farms EBF Victor McC | **Faiyum** |  | 0.429 | 0.253 | 0.214 | 0.992 | OK | VP30 |
| — | — | — | **Timeless Treaty** | A | 0.418 | 0.272 | 0.271 | 0.972 | MISSING:course,off_time | TIER_A VP30 |
| — | — | — | **Full Force Gale** | B | 0.415 | 0.092 | 0.108 | 0.726 | MISSING:course,off_time | VP30 |
| — | — | — | **Great Dance** | B | 0.412 | 0.341 | 0.382 | 0.957 | MISSING:course,off_time | VP30 |
| 7:00 | Wolverhampton (AW) | Get Raceday Ready Fillies' Restrict | **Bintaziza** |  | 0.405 | 0.483 | 0.386 | 0.995 | OK | VP30 |
| — | — | — | **Star Prospect** | B | 0.386 | 0.129 | 0.082 | 0.518 | MISSING:course,off_time | VP30 |
| 5:42 | Hereford | CopyBet Supporting UK Racing Handic | **Edgewell** |  | 0.381 | 0.026 | 0.087 | 0.826 | OK | VP30 |
| 2:48 | Ffos Las | Weatherbys nhstallions.co.uk Handic | **Prince Rhinegold** |  | 0.375 | 0.021 | 0.123 | 0.652 | OK | VP30 |
| — | — | — | **Noble Vow** | B | 0.371 | 0.185 | 0.385 | 0.735 | MISSING:course,off_time | VP30 |
| 7:08 | Gowran Park | Irish Stallion Farms EBF Fillies Ma | **Almeiyda** |  | 0.370 | 0.186 | 0.360 | 0.679 | OK | VP30 |
| 7:30 | Wolverhampton (AW) | Free Digital Racecard At raceday-re | **Tinsel** |  | 0.361 | 0.106 | 0.023 | 0.989 | OK | VP30 |
| — | — | — | **Forever Glamorous** | B | 0.347 | 0.011 | 0.082 | 0.628 | MISSING:course,off_time | VP30 |
| — | — | — | **Valentine Boy** | B | 0.347 | 0.036 | 0.115 | 0.944 | MISSING:course,off_time | VP30 |
| — | — | — | **Furturra** | B | 0.340 | 0.174 | 0.328 | 0.607 | MISSING:course,off_time | VP30 |
| — | — | — | **Minnie Hauk** | B | 0.335 | 0.404 | 0.136 | 0.998 | MISSING:course,off_time | VP30 |
| — | — | — | **Annie Nail** | C | 0.332 | 0.020 | 0.030 | 0.739 | MISSING:course,off_time | VP30 |
| — | — | — | **Luna Run** | B | 0.325 | 0.073 | 0.077 | 0.708 | MISSING:course,off_time | VP30 |
| — | — | — | **Cinderello** | C | 0.318 | 0.081 | 0.075 | 0.867 | MISSING:course,off_time | VP30 |
| — | — | — | **Decade Of Time** | B | 0.315 | 0.166 | 0.235 | 0.520 | MISSING:course,off_time | VP30 |
| — | — | — | **Black Caviar Gold** | B | 0.311 | 0.029 | 0.100 | 0.666 | MISSING:course,off_time | VP30 |
| 7:17 | Hereford | Wye Valley Metals Handicap Hurdle | **Cluain Chormaic** |  | 0.309 | 0.099 | 0.065 | 0.377 | OK | VP30 |
| — | — | — | **Takincareofbizness** | C | 0.309 | 0.081 | 0.030 | 0.375 | MISSING:course,off_time | VP30 |
| — | — | — | **Beauty Box** | C | 0.305 | 0.101 | 0.087 | 0.291 | MISSING:course,off_time | VP30 |
| 6:47 | Hereford | CopyBet Overnight Best Odds Guarant | **The Long Walk** |  | 0.304 | 0.038 | 0.038 | 0.601 | OK | VP30 |
| 2:00 | Ayr | Weddings At Western House Hotel Mai | **Stoneacre Joe** |  | 0.301 | 0.194 | 0.338 | 0.744 | OK | VP30 |
| — | — | — | **Neolithic** | C | 0.300 | 0.037 | 0.054 | 0.696 | MISSING:course,off_time | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (7)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| — | — | — | **Neigh Botha** | B | 0.299 | 0.017 | 0.081 | 0.531 | MISSING:course,off_time |  |
| — | — | — | **Diomed Spirit** | B | 0.294 | 0.031 | 0.083 | 0.922 | MISSING:course,off_time |  |
| — | — | — | **From Me To You** | B | 0.282 | 0.112 | 0.208 | 0.346 | MISSING:course,off_time |  |
| — | — | — | **Hardy Diamond** | B | 0.255 | 0.038 | 0.070 | 0.628 | MISSING:course,off_time |  |
| — | — | — | **Gris De Chine** | B | 0.247 | 0.162 | 0.338 | 0.920 | MISSING:course,off_time |  |
| — | — | — | **Moonlit Cloud** | B | 0.235 | 0.017 | 0.079 | 0.899 | MISSING:course,off_time |  |
| — | — | — | **Mali Star** | B | 0.224 | 0.069 | 0.022 | 0.323 | MISSING:course,off_time |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-05-05T03:52:49.208887+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
# SIDECAR STACK OPERATOR CARD — 2026-05-12

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
| ELITE_STACK | Tier A + VP≥0.30 + MDS>0.50 | 3 |
| STRONG_STACK_PLUS | VP≥0.30 + MDS>0.50 + IMP>0.40 | 1 |
| STRONG_STACK | VP≥0.30 + MDS>0.50 (no IMP) | 3 |
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 3 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 9 |
| SUPPRESS | Tier B + VP<0.30 | 17 |

**Total races scanned:** 39  
**VP30 selections:** 16

---

## A. ELITE STACK — Tier A + VP30 + MDS (3)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 2:38 | Hereford | Worcester Racecourse Ladies Day 6th | **?** | A | 0.837 | 0.552 | 0.024 | 0.980 | TIER_A VP30 MDS_HIGH |
| 3:38 | Hereford | Ludford Car Parts Group Mares' Novi | **?** | A | 0.595 | 0.555 | 0.149 | 0.965 | TIER_A VP30 MDS_HIGH |
| 6:58 | Sligo | Enda McGoldrick, Plant & Agri Hire  | **?** | A | 0.486 | 0.521 | 0.295 | 0.990 | TIER_A VP30 MDS_HIGH |

## B. STRONG STACK PLUS — VP30 + MDS + IMP (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 5:50 | Lingfield (AW) | Sky Sports Racing Virgin 512 Novice | **?** | B | 0.311 | 0.567 | 0.659 | 0.984 | VP30 MDS_HIGH IMP_HIGH |

## C. STRONG STACK — VP30 + MDS (3)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 2:38 | Hereford | Worcester Racecourse Ladies Day 6th | **?** | A | 0.837 | 0.552 | 0.024 | 0.980 | TIER_A VP30 MDS_HIGH |
| 3:38 | Hereford | Ludford Car Parts Group Mares' Novi | **?** | A | 0.595 | 0.555 | 0.149 | 0.965 | TIER_A VP30 MDS_HIGH |
| 6:58 | Sligo | Enda McGoldrick, Plant & Agri Hire  | **?** | A | 0.486 | 0.521 | 0.295 | 0.990 | TIER_A VP30 MDS_HIGH |

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (3)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 3:00 | Beverley | Ire-Incentive, It Pays To Buy Irish | **?** | A | 0.575 | 0.365 | 0.416 | 0.910 | TIER_A VP30 IMP_HIGH |
| 2:30 | Beverley | Clearanswer Call Centres Maiden Fil | **?** | B | 0.503 | 0.412 | 0.541 | 0.953 | VP30 IMP_HIGH |
| 6:20 | Lingfield (AW) | Download The At The Races App Filli | **?** | A | 0.393 | 0.173 | 0.443 | 0.987 | TIER_A VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (9)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 5:20 | Hereford | Hereford Season Finale Open Nationa | **?** | A | 0.650 | 0.492 | 0.184 | 0.973 | TIER_A VP30 |
| 3:30 | Beverley | Bowel Cancer Screening Programme Sa | **?** | A | 0.432 | 0.188 | 0.066 | 0.967 | TIER_A VP30 |
| 3:20 | Bath | Best Cleaning Group Maiden Stakes ( | **?** | A | 0.421 | 0.301 | 0.207 | 0.986 | TIER_A VP30 |
| 3:08 | Hereford | CopyBet Overnight Best Odds Guarant | **?** | B | 0.389 | 0.167 | 0.001 | 0.822 | VP30 |
| 3:50 | Bath | Pockets At Bath Handicap | **?** | A | 0.388 | 0.024 | 0.077 | 1.000 | TIER_A VP30 |
| 5:40 | Killarney | Irish Stallion Farms EBF Fillies Ra | **?** | A | 0.382 | 0.057 | 0.077 | 0.863 | TIER_A VP30 |
| 2:20 | Bath | RJ King & Sons EBF Restricted Novic | **?** | B | 0.363 | 0.215 | 0.150 | 0.799 | VP30 |
| 4:10 | Hereford | CopyBet Says Thank You To Hereford  | **?** | B | 0.328 | 0.033 | 0.039 | 0.868 | VP30 |
| 7:10 | Killarney | Brehon Hotel Handicap | **?** | B | 0.314 | 0.043 | 0.194 | 0.649 | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (17)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 8:10 | Killarney | Killarney Racegoers Club Race | **?** | B | 0.289 | 0.165 | 0.041 | 0.538 |  |
| 5:05 | Killarney | Irish Stallion Farms EBF (C & G) Ma | **?** | B | 0.288 | 0.447 | 0.410 | 0.925 | IMP_HIGH |
| 6:10 | Killarney | FEXCO Maiden | **?** | B | 0.287 | 0.154 | 0.191 | 0.935 |  |
| 5:10 | Beverley | Racing Welfare Supporting Mental He | **?** | B | 0.284 | 0.071 | 0.062 | 0.785 |  |
| 5:15 | Lingfield (AW) | Free Tips Daily On attheraces.com A | **?** | B | 0.278 | 0.029 | 0.065 | 0.558 |  |
| 4:45 | Hereford | First Past The Post At CopyBet Hand | **?** | B | 0.260 | 0.051 | 0.115 | 0.365 |  |
| 4:23 | Bath | Clyde And Co Handicap | **?** | B | 0.228 | 0.032 | 0.010 | 0.780 |  |
| 7:58 | Sligo | Solar Generation Handicap Hurdle | **?** | B | 0.221 | 0.080 | 0.136 | 0.640 |  |
| 5:58 | Sligo | DecoClip Construction Company Mares | **?** | B | 0.213 | 0.118 | 0.220 | 0.528 |  |
| 5:27 | Sligo | Adare Manor Opportunity Maiden Hurd | **?** | B | 0.210 | 0.150 | 0.234 | 0.761 |  |
| 7:28 | Sligo | Johnston Farm Equipment Handicap Hu | **?** | B | 0.206 | 0.054 | 0.150 | 0.489 |  |
| 7:50 | Lingfield (AW) | Free Bets On attheraces.com Fillies | **?** | B | 0.201 | 0.017 | 0.087 | 0.378 |  |
| 6:50 | Lingfield (AW) | Sky Sports Racing Sky 415 Handicap | **?** | B | 0.193 | 0.034 | 0.032 | 0.511 |  |
| 2:50 | Bath | Bath Mind Charity "Confined" Handic | **?** | B | 0.179 | 0.007 | 0.018 | 0.707 |  |
| 5:00 | Bath | Download The Fairplay App Now Handi | **?** | B | 0.173 | 0.008 | 0.035 | 0.586 |  |
| 7:20 | Lingfield (AW) | Follow @attheraces On X Handicap | **?** | B | 0.169 | 0.015 | 0.079 | 0.704 |  |
| 6:40 | Killarney | Velo Coffee Roasters Handicap | **?** | B | 0.139 | 0.010 | 0.087 | 0.185 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-05-12T21:22:46.415786+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
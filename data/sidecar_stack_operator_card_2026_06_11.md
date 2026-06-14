# SIDECAR STACK OPERATOR CARD — 2026-06-11

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
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 3 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 25 |
| SUPPRESS | Tier B + VP<0.30 | 6 |

**Total races scanned:** 46  
**VP30 selections:** 28

---

## A. ELITE STACK — Tier A + VP30 + MDS (0)

*No signals for this stack today.*

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (0)

*No signals for this stack today.*

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (3)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:35 | Nottingham | EBF Restricted Novice Stakes (For H | **Moriarty Moon** | A | 0.479 | 0.220 | 0.511 | 0.918 | TIER_A VP30 IMP_HIGH |
| 14:45 | Yarmouth | Paul Corrigan Memorial Novice Stake | **Nevasca Cinza** | C | 0.394 | 0.353 | 0.547 | 0.988 | VP30 IMP_HIGH |
| 18:00 | Leopardstown | Irish Stallion Farms EBF Fillies Ma | **Cromac Quay** | A | 0.577 | 0.351 | 0.734 | 0.954 | TIER_A VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (25)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 2:55 | NBY | 1m (Class 5) Last 9 outings(pos,rat | **Suggy** | A | 0.405 | 0.035 | 0.038 | 0.652 | TIER_A VP30 |
| 4:40 | NBY | 1m 1f (Class 4) Last 9 outings(pos, | **Shady Dame** | B | 0.325 | 0.065 | 0.087 | 0.226 | VP30 |
| 14:10 | Yarmouth | QuinnBet Second To The Favourite "H | **Heretic** | A | 0.664 | 0.436 | 0.014 | 0.999 | TIER_A VP30 |
| 15:08 | Nottingham | Â£9 Racedays At Nottingham Racecour | **Fractional** | A | 0.645 | 0.380 | 0.182 | 0.999 | TIER_A VP30 |
| 15:20 | Yarmouth | Winning Experience With Moulton Rac | **Neyva's Angel** | A | 0.364 | 0.080 | 0.017 | 0.901 | TIER_A VP30 |
| 15:53 | Yarmouth | QuinnBet Best Odds Guaranteed Handi | **Prefer The Sister** | C | 0.322 | 0.017 | 0.014 | 0.417 | VP30 |
| 16:17 | Nottingham | Watch On Racing TV Handicap | **Caraway** | A | 0.574 | 0.061 | 0.043 | 0.726 | TIER_A VP30 |
| 16:28 | Yarmouth | QuinnBet Handicap (GBBPlus Race) | **Yokohama** | A | 0.390 | 0.050 | 0.014 | 0.761 | TIER_A VP30 |
| 16:40 | Newbury | HMC Horse Boxes EBF Fillies' Novice | **Shady Dame** | A | 0.414 | 0.117 | 0.251 | 0.683 | TIER_A VP30 |
| 16:52 | Nottingham | Events At Nottingham Racecourse Han | **Toptime** | B | 0.310 | 0.055 | 0.024 | 0.774 | VP30 |
| 17:03 | Yarmouth | Download The QuinnBet App Classifie | **Wrist Art** | A | 0.481 | 0.152 | 0.151 | 0.869 | TIER_A VP30 |
| 17:08 | Worcester | CopyBet And Worcester Here All Year | **Beorma** | A | 0.623 | 0.065 | 0.055 | 0.641 | TIER_A VP30 |
| 17:15 | Newbury | White Horse International Handicap  | **Mythical Bay** | B | 0.321 | 0.043 | 0.030 | 0.467 | VP30 |
| 17:22 | Nottingham | Dine In Sherwoods Restaurant Classi | **South Shore Island** | A | 0.465 | 0.052 | 0.093 | 0.525 | TIER_A VP30 |
| 17:35 | Yarmouth | quinnbet.com Handicap | **Darkest Red** | A | 0.633 | 0.050 | 0.043 | 0.646 | TIER_A VP30 |
| 17:40 | Worcester | CopyBet Proudly Backs UK Horse Raci | **Grand Clermont** | A | 0.365 | 0.037 | 0.025 | 0.676 | TIER_A VP30 |
| 18:22 | Catterick | British EBF Maiden Stakes (GBB Race | **Wilbur** | A | 0.584 | 0.210 | 0.068 | 0.887 | TIER_A VP30 |
| 18:30 | Leopardstown | GAIN The Advantage Series Handicap | **Only One Scobie** | B | 0.513 | 0.059 | 0.116 | 0.473 | VP30 |
| 18:52 | Catterick | Bowel Cancer Screening Programme Sa | **Lady Gormire** | A | 0.679 | 0.227 | 0.337 | 0.954 | TIER_A VP30 |
| 19:00 | Leopardstown | Ballycorus Stakes (Group 3) | **Native Warrior** | A | 0.562 | 0.132 | 0.079 | 0.951 | TIER_A VP30 |
| 19:10 | Worcester | CopyBet Support Safer Gambling Maid | **Kernie d'Airy** | C | 0.308 | 0.106 | 0.168 | 0.848 | VP30 |
| 19:22 | Catterick | racingtv.com/freetrial Handicap | **Powernap** | A | 0.384 | 0.045 | 0.043 | 0.805 | TIER_A VP30 |
| 19:30 | Leopardstown | Bulmers Live Apprentice Handicap | **Coeur d'Or** | A | 0.559 | 0.174 | 0.092 | 0.904 | TIER_A VP30 |
| 19:42 | Worcester | CopyBet For Your Daily Profit Boost | **Sunray Shadow** | A | 0.428 | 0.132 | 0.031 | 0.985 | TIER_A VP30 |
| 20:23 | Catterick | Try Racing TV For Free Now Handicap | **Lightning Tiger** | C | 0.355 | 0.256 | 0.211 | 0.994 | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (6)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 4:05 | NBY | 6f (Class 4) Last 9 outings(pos,rat | **Wild Clary** | B | 0.268 | 0.066 | 0.168 | 0.820 |  |
| 15:42 | Nottingham | Wildwest Beer Festival 4th July Han | **Wondrous Light** | B | 0.243 | 0.026 | 0.025 | 0.506 |  |
| 17:30 | Leopardstown | Irish EBF Median Sires Series Filli | **Cashel Queen** | B | 0.250 | 0.077 | 0.087 | 0.193 |  |
| 18:40 | Worcester | CopyBet Support Safer Gambling Maid | **Shamsat** | B | 0.280 | 0.121 | 0.211 | 0.911 |  |
| 20:53 | Worcester | CopyBet For Overnight Best Odds Gua | **October Hill** | B | 0.267 | 0.020 | 0.036 | 0.511 |  |
| 20:59 | Catterick | Racing Again 22nd June Handicap | **Uppercase** | B | 0.249 | 0.022 | 0.016 | 0.460 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-06-11T15:15:47.501912+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
# SIDECAR STACK OPERATOR CARD — 2026-06-03

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
| STRONG_STACK_PLUS | VP≥0.30 + MDS>0.50 + IMP>0.40 | 1 |
| STRONG_STACK | VP≥0.30 + MDS>0.50 (no IMP) | 0 |
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 2 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 25 |
| SUPPRESS | Tier B + VP<0.30 | 8 |

**Total races scanned:** 76  
**VP30 selections:** 28

---

## A. ELITE STACK — Tier A + VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 18:35 | Ripon | Book Online At ripon-races.co.uk Ma | **Gone By** | A | 0.985 | 0.654 | 0.505 | 0.996 | TIER_A VP30 MDS_HIGH IMP_HIGH |

## B. STRONG STACK PLUS — VP30 + MDS + IMP (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 18:35 | Ripon | Book Online At ripon-races.co.uk Ma | **Gone By** | A | 0.985 | 0.654 | 0.505 | 0.996 | TIER_A VP30 MDS_HIGH IMP_HIGH |

## C. STRONG STACK — VP30 + MDS (0)

*No signals for this stack today.*

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (2)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:30 | Newton Abbot | Sun Racing Free Tickets With Sun Cl | **Yellow Card** | A | 0.498 | 0.310 | 0.437 | 0.971 | TIER_A VP30 IMP_HIGH |
| 18:10 | Curragh | Pension Structures Irish EBF Maiden | **Sirocco Sands** | A | 0.563 | 0.144 | 0.603 | 0.800 | TIER_A VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (25)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:48 | Nottingham | £9 Racedays At Nottingham Racecours | **True Charm** | B | 0.321 | 0.093 | 0.321 | 0.525 | VP30 |
| 15:00 | Newton Abbot | Edmundson Electrical Torquay Novice | **Franigane** | A | 0.596 | 0.069 | 0.015 | 0.675 | TIER_A VP30 |
| 15:18 | Nottingham | British Stallion Studs EBF Maiden F | **Miss Tuite** | B | 0.325 | 0.086 | 0.149 | 0.420 | VP30 |
| 15:30 | Newton Abbot | Par Inn Novices' Handicap Chase | **Daring Plan** | A | 0.389 | 0.030 | 0.064 | 0.727 | TIER_A VP30 |
| 15:48 | Nottingham | Wildwest Beer Festival 4th July Fil | **Lillie Margot** | B | 0.328 | 0.024 | 0.032 | 0.235 | VP30 |
| 16:00 | Newton Abbot | Charles Darrow Mares' Handicap Hurd | **Miss Goldfire** | B | 0.347 | 0.024 | 0.017 | 0.487 | VP30 |
| 16:18 | Nottingham | Hospitality At Nottingham Racecours | **Give Me The Night** | X | 0.303 | 0.017 | 0.061 | 0.261 | VP30 |
| 16:30 | Newton Abbot | Clearance Handicap Hurdle | **Howth** | B | 0.358 | 0.040 | 0.024 | 0.460 | VP30 |
| 16:48 | Nottingham | Watch RacingTV Handicap (GBBPlus Ra | **Barbury Boy** | B | 0.426 | 0.022 | 0.038 | 0.361 | VP30 |
| 17:00 | Newton Abbot | WestCountry Food Supplies Handicap  | **Ambassador** | B | 0.416 | 0.058 | 0.141 | 0.800 | VP30 |
| 17:18 | Nottingham | Dine In Sherwoods Restaurant Handic | **Rinky Tinky Tinky** | A | 0.682 | 0.059 | 0.227 | 0.794 | TIER_A VP30 |
| 18:00 | Ripon | British Stallion Studs EBF Novice S | **Fantasy Force** | A | 0.720 | 0.208 | 0.377 | 0.792 | TIER_A VP30 |
| 18:20 | Warwick | EHB Residential Maiden Hurdle (GBB  | **Louis Veron** | A | 0.748 | 0.197 | 0.262 | 0.822 | TIER_A VP30 |
| 18:55 | Warwick | Insight Surveyors Handicap Hurdle | **Spitalfield** | A | 0.418 | 0.087 | 0.143 | 0.896 | TIER_A VP30 |
| 19:20 | Curragh | Sky Bet Race To The Ebor Handicap | **Dawn Rising** | B | 0.370 | 0.017 | 0.043 | 0.377 | VP30 |
| 19:30 | Warwick | Virtus Property Services Handicap H | **Modern Style** | C | 0.356 | 0.045 | 0.016 | 0.557 | VP30 |
| 19:42 | Ripon | weatherbysshop.co.uk Handicap | **Bay Breeze** | B | 0.331 | 0.014 | 0.050 | 0.231 | VP30 |
| 19:55 | Curragh | Try Racing TV For Free Now At racin | **Arrietty** | B | 0.377 | 0.066 | 0.220 | 0.468 | VP30 |
| 20:25 | Curragh | Sky Bet Build A Bet Handicap | **Irish Rumour** | B | 0.364 | 0.015 | 0.130 | 0.461 | VP30 |
| 20:30 | Warwick | Stockton House Mares' Handicap Hurd | **Siorai** | C | 0.353 | 0.032 | 0.058 | 0.476 | VP30 |
| 21:00 | Warwick | Taylor Wimpey Strategic Land Midlan | **Zestful Hope** | A | 0.639 | 0.052 | 0.030 | 0.803 | TIER_A VP30 |
| — | — | — | **Gone By** | A | 0.834 | 0.247 | 0.088 | 0.892 | TIER_A VP30 |
| — | — | — | **Bull Shark** | C | 0.354 | 0.045 | 0.087 | 0.223 | VP30 |
| — | — | — | **Dunkerque** | B | 0.341 | 0.093 | 0.082 | 0.023 | VP30 |
| — | — | — | **Barbury Boy** | C | 0.311 | 0.045 | 0.088 | 0.037 | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (8)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 16:40 | Curragh | Sky Bet Extra Places Handicap | **Gonna Be Golden** | B | 0.296 | 0.012 | 0.128 | 0.217 |  |
| 17:10 | Curragh | TRI Equestrian Maiden | **The Piper's Call** | B | 0.299 | 0.114 | 0.631 | 0.713 | IMP_HIGH |
| 18:45 | Curragh | Sky Bet Price Boosts Premier Handic | **Real Encounter** | B | 0.230 | 0.011 | 0.037 | 0.216 |  |
| 19:10 | Ripon | Bishopton Equine Handicap | **Eeetee** | B | 0.216 | 0.010 | 0.032 | 0.142 |  |
| — | — | — | **Canaria Queen** | B | 0.248 | 0.086 | 0.082 | 0.204 |  |
| — | — | — | **Karakula Dancer** | B | 0.234 | 0.040 | 0.088 | 0.027 |  |
| — | — | — | **Menhaal** | B | 0.194 | 0.035 | 0.087 | 0.107 |  |
| — | — | — | **Sirocco Sands** | B | 0.163 | 0.029 | 0.087 | 0.099 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-06-03T10:57:55.484358+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
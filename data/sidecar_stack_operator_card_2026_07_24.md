# SIDECAR STACK OPERATOR CARD — 2026-07-24

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
| ELITE_STACK | Tier A + VP≥0.30 + MDS>0.50 | 2 |
| STRONG_STACK_PLUS | VP≥0.30 + MDS>0.50 + IMP>0.40 | 2 |
| STRONG_STACK | VP≥0.30 + MDS>0.50 (no IMP) | 0 |
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 1 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 32 |
| SUPPRESS | Tier B + VP<0.30 | 9 |

**Total races scanned:** 55  
**VP30 selections:** 35

---

## A. ELITE STACK — Tier A + VP30 + MDS (2)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 16:48 | Cork | Irish EBF Auction Series Maiden (IR | **Hanney Boy** | A | 0.848 | 0.612 | 0.716 | 0.999 | TIER_A VP30 MDS_HIGH IMP_HIGH |
| 18:40 | York | Ire-Incentive, It Pays To Buy Irish | **Coral Cove** | A | 0.656 | 0.572 | 0.538 | 0.993 | TIER_A VP30 MDS_HIGH IMP_HIGH |

## B. STRONG STACK PLUS — VP30 + MDS + IMP (2)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 16:48 | Cork | Irish EBF Auction Series Maiden (IR | **Hanney Boy** | A | 0.848 | 0.612 | 0.716 | 0.999 | TIER_A VP30 MDS_HIGH IMP_HIGH |
| 18:40 | York | Ire-Incentive, It Pays To Buy Irish | **Coral Cove** | A | 0.656 | 0.572 | 0.538 | 0.993 | TIER_A VP30 MDS_HIGH IMP_HIGH |

## C. STRONG STACK — VP30 + MDS (0)

*No signals for this stack today.*

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:00 | Thirsk | Sky Bet Go-Racing-In-Yorkshire Summ | **Little Lady Karen** | A | 0.509 | 0.353 | 0.435 | 0.994 | TIER_A VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (32)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 13:40 | Uttoxeter | Chloe Mediumship Novices' Hurdle (G | **Likewhatyousee** | A | 0.414 | 0.175 | 0.236 | 0.975 | TIER_A VP30 |
| 14:10 | Uttoxeter | Bridal Rooms Uttoxeter Handicap Hur | **Littletown Lad** | A | 0.404 | 0.100 | 0.149 | 0.538 | TIER_A VP30 |
| 14:20 | Ascot | Sports4Causes October Club EBF Fill | **Sorrengail** | A | 0.384 | 0.179 | 0.086 | 0.694 | TIER_A VP30 |
| 14:30 | Thirsk | Sky Bet For The Fans EBF Novice Sta | **Blessed Voyager** | A | 0.558 | 0.467 | 0.377 | 0.964 | TIER_A VP30 |
| 14:55 | Ascot | Flexjet Pat Eddery Stakes (Listed R | **Silver Dominion** | A | 0.436 | 0.094 | 0.080 | 0.750 | TIER_A VP30 |
| 15:05 | Thirsk | Ruby Lodge Care Home In Thirsk Nurs | **Liveadream** | A | 0.557 | 0.065 | 0.116 | 0.570 | TIER_A VP30 |
| 15:30 | Ascot | John Guest Racing Brown Jack Handic | **Kirchner** | A | 0.522 | 0.142 | 0.010 | 0.938 | TIER_A VP30 |
| 15:40 | Thirsk | Graham Lee Injured Jockeys' Fund Do | **Tupero** | A | 0.642 | 0.235 | 0.020 | 0.859 | TIER_A VP30 |
| 16:18 | Thirsk | NRFC Leading Roof Excellence Fillie | **Miss Rainbow** | D | 0.303 | 0.023 | 0.049 | 0.420 | VP30 |
| 16:40 | Ascot | Chapel Down Handicap | **Be Frank** | C | 0.333 | 0.020 | 0.047 | 0.393 | VP30 |
| 16:53 | Thirsk | JW4X4 Northallerton Handicap | **Dubai Venture** | A | 0.526 | 0.097 | 0.017 | 0.924 | TIER_A VP30 |
| 17:12 | Ascot | Sodexo Live! Fillies' Handicap | **Dandy Magic** | A | 0.406 | 0.025 | 0.058 | 0.523 | TIER_A VP30 |
| 17:15 | Sandown | Close Brothers Asset Finance Appren | **Mrembo** | A | 0.375 | 0.041 | 0.059 | 0.690 | TIER_A VP30 |
| 17:18 | Chepstow | On The River Ball+Chain Nursery Han | **Devon Angel** | A | 0.555 | 0.055 | 0.080 | 0.785 | TIER_A VP30 |
| 17:22 | Cork | Irish Stallion Farms EBF Rated Race | **Sirocco Sands** | A | 0.605 | 0.110 | 0.051 | 0.692 | TIER_A VP30 |
| 17:27 | Thirsk | Racing Excellence Apprentice Handic | **So Grateful** | A | 0.635 | 0.063 | 0.084 | 0.756 | TIER_A VP30 |
| 17:35 | Uttoxeter | QuinnBet Mares' Open National Hunt  | **Sparkling Water** | A | 0.456 | 0.144 | 0.207 | 0.862 | TIER_A VP30 |
| 17:47 | Sandown | Chasemore Farm EBF Maiden Fillies'  | **Not My Type** | B | 0.319 | 0.124 | 0.087 | 0.307 | VP30 |
| 18:26 | Chepstow | Cheeseburger Aaron Handicap | **Prefer The Sister** | A | 0.624 | 0.155 | 0.031 | 0.857 | TIER_A VP30 |
| 18:33 | Cork | Navigation Road Maiden | **Stooked** | B | 0.314 | 0.195 | 0.386 | 0.782 | VP30 |
| 18:55 | Sandown | Close Brothers Handicap | **Cyrano De Bergerac** | A | 0.459 | 0.138 | 0.007 | 0.550 | TIER_A VP30 |
| 19:01 | Chepstow | LSL Racing Horse Sales Handicap (Ch | **Nammos** | B | 0.384 | 0.031 | 0.081 | 0.778 | VP30 |
| 19:21 | Kilbeggan | Hurley Family Maiden Hurdle | **Rusty Harkness** | A | 0.410 | 0.076 | 0.021 | 0.839 | TIER_A VP30 |
| 19:30 | Sandown | Close Brothers Invoice Finance Hand | **Cristo** | B | 0.346 | 0.059 | 0.010 | 0.585 | VP30 |
| 19:36 | Chepstow | 3A's Caravan & Motorhome Classified | **Knightmare** | A | 0.516 | 0.124 | 0.062 | 0.655 | TIER_A VP30 |
| 19:43 | Cork | Buy Tickets Online At www.corkracec | **Alphonsus Liguori** | A | 0.822 | 0.283 | 0.212 | 0.952 | TIER_A VP30 |
| 19:50 | York | British EBF Lyric Fillies' Stakes ( | **Diamond Rain** | A | 0.801 | 0.283 | 0.084 | 0.999 | TIER_A VP30 |
| 19:56 | Kilbeggan | Egan Stone Kilbeggan Handicap Chase | **Grange Walk** | B | 0.311 | 0.032 | 0.073 | 0.545 | VP30 |
| 20:05 | Sandown | Close Brothers Motor Finance Handic | **Norfolk Blue** | A | 0.379 | 0.057 | 0.019 | 0.821 | TIER_A VP30 |
| 20:11 | Chepstow | Sophie Busson Memorial Handicap | **So Smart** | A | 0.585 | 0.065 | 0.013 | 0.690 | TIER_A VP30 |
| 20:18 | Cork | Racing Again August 3rd Handicap | **Borora Aura** | B | 0.475 | 0.033 | 0.182 | 0.473 | VP30 |
| 20:46 | Chepstow | Weir Mechanical Solutions Handicap | **City Escape** | B | 0.353 | 0.016 | 0.022 | 0.330 | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (9)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:40 | Uttoxeter | Bridal Rooms Uttoxeter Handicap Hur | **Cawthorne Banker** | B | 0.207 | 0.024 | 0.012 | 0.454 |  |
| 15:15 | Uttoxeter | Craig Reid Retirement Handicap Chas | **Izzy's Grey** | B | 0.236 | 0.037 | 0.062 | 0.594 |  |
| 16:25 | Uttoxeter | Louise Hall Hen Party Handicap Hurd | **Jammy Jay** | B | 0.277 | 0.013 | 0.085 | 0.503 |  |
| 17:05 | Kilbeggan | Tom McCormack Memorial Cup Maiden H | **Mysilverriverfeale** | B | 0.280 | 0.186 | 0.393 | 0.993 |  |
| 17:40 | Kilbeggan | Massey Ferguson Johnston Farm Equip | **Dream Shaper** | B | 0.204 | 0.015 | 0.115 | 0.513 |  |
| 17:52 | Chepstow | Apex Transport Planning Summer Suns | **Forest Berry** | B | 0.258 | 0.047 | 0.043 | 0.274 |  |
| 18:11 | Kilbeggan | Massey Ferguson Johnston Farm Equip | **Western Opera** | B | 0.188 | 0.017 | 0.139 | 0.498 |  |
| 19:15 | York | Tomahawk Handicap | **Dorney Lake** | B | 0.294 | 0.005 | 0.075 | 0.193 |  |
| 20:30 | Kilbeggan | Racing Again On 8th August Handicap | **Love Like This** | B | 0.272 | 0.032 | 0.086 | 0.541 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-07-23T22:43:59.369074+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
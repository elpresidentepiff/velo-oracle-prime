# SIDECAR STACK OPERATOR CARD — 2026-05-19

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
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 0 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 13 |
| SUPPRESS | Tier B + VP<0.30 | 20 |

**Total races scanned:** 38  
**VP30 selections:** 13

---

## A. ELITE STACK — Tier A + VP30 + MDS (0)

*No signals for this stack today.*

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (0)

*No signals for this stack today.*

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (0)

*No signals for this stack today.*

## E. VP30 BASE — VP30 only (13)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 3:00 | Newcastle | Total Performance Data - 10 Years A | **Littlecote** | X | 1.000 | 0.139 | 0.088 | 0.856 | VP30 |
| 7:50 | Hexham | Northumberland County Show Novices' | **Passing Diamond** | X | 1.000 | 0.139 | 0.082 | 0.973 | VP30 |
| 6:00 | Huntingdon | Tattersalls Ireland May Hit & P2P S | **Crackalackin** | X | 1.000 | 0.139 | 0.085 | 0.987 | VP30 |
| 6:42 | Cork | Cork Racecourse Maiden € 13,000 Tot | **Al Haarith** | X | 1.000 | 0.139 | 0.088 | 0.874 | VP30 |
| 8:30 | Huntingdon | Tattersalls Online Novices' Hunters | **On Lovers Walk** | X | 1.000 | 0.139 | 0.067 | 0.984 | VP30 |
| 4:00 | Newcastle | In Loving Memory Of Yvonne Rush Nov | **Gold Digger** | X | 1.000 | 0.139 | 0.088 | 0.827 | VP30 |
| 2:20 | Nottingham | £9 Racedays At Nottingham Novice St | **Runman** | X | 1.000 | 0.139 | 0.088 | 0.866 | VP30 |
| 7:42 | Cork | Mallow Fillies Maiden € 13,000 Tota | **Carmel'S Phoenix** | A | 0.923 | 0.302 | 0.050 | 0.865 | TIER_A VP30 |
| 2:40 | Lingfield | Sky Sports Racing Sky 415 Restricte | **Vidmiyr** | A | 0.549 | 0.051 | 0.019 | 0.901 | TIER_A VP30 |
| 8:00 | Huntingdon | Tattersalls Ireland May Hit & P2P S | **Ice Jet** | A | 0.514 | 0.051 | 0.090 | 0.999 | TIER_A VP30 |
| 7:20 | Hexham | Lynn Siddall Memorial Handicap Chas | **Milan Milos** | A | 0.324 | 0.062 | 0.191 | 0.994 | TIER_A VP30 |
| 6:30 | Huntingdon | Tattersalls Online Handicap Chase ( | **Pleasure Garden** | B | 0.324 | 0.022 | 0.032 | 0.981 | VP30 |
| 6:50 | Hexham | Port Of Blyth Novices' Handicap Cha | **Lewa House** | B | 0.309 | 0.017 | 0.074 | 0.957 | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (20)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 7:00 | Huntingdon | Tattersalls Ireland May Hit & P2P S | **Klervia** | B | 0.272 | 0.016 | 0.084 | 0.935 |  |
| 6:20 | Hexham | Port Of Blyth Handicap Chase (GBB R | **Conquer The Breeze** | B | 0.253 | 0.035 | 0.086 | 0.952 |  |
| 5:20 | Lingfield | Sky Sports Racing Virgin 512 Handic | **Beau Jardine** | B | 0.234 | 0.018 | 0.100 | 0.873 |  |
| 7:12 | Cork | Blackwater Apprentice Handicap € 20 | **Goal Exceeded** | B | 0.226 | 0.015 | 0.081 | 0.838 |  |
| 4:45 | Lingfield | Sky Sports Racing Virgin 512 Handic | **Reidh** | B | 0.223 | 0.021 | 0.111 | 0.771 |  |
| 2:30 | Newcastle | Celebrating 10 Years Of Tapeta At N | **Edwardtheninth** | B | 0.220 | 0.009 | 0.018 | 0.675 |  |
| 5:05 | Newcastle | Book Northumberland Plate Day Ticke | **Annie Edson Taylor** | B | 0.208 | 0.008 | 0.019 | 0.383 |  |
| 5:50 | Hexham | Tynedale Agricultural Society Condi | **Watchoutitscookie** | B | 0.206 | 0.017 | 0.084 | 0.859 |  |
| 5:42 | Cork | Buy Tickets Online At www.corkracec | **Steel Magnolia** | B | 0.203 | 0.028 | 0.184 | 0.667 |  |
| 7:30 | Huntingdon | Tattersalls Online Handicap Hurdle  | **Gasmani** | B | 0.196 | 0.011 | 0.016 | 0.584 |  |
| 4:20 | Nottingham | Conferences And Events At Nottingha | **Pretty Spirited** | B | 0.196 | 0.011 | 0.080 | 0.731 |  |
| 8:50 | Hexham | Jason Arnup After Party 6th June Ha | **King Kodiak** | B | 0.192 | 0.015 | 0.075 | 0.829 |  |
| 3:40 | Lingfield | Simon Duggan The Bad Ama Handicap ( | **No Gain** | B | 0.182 | 0.012 | 0.087 | 0.749 |  |
| 3:50 | Nottingham | Events And Hospitality At Nottingha | **Domination** | B | 0.179 | 0.011 | 0.052 | 0.528 |  |
| 5:12 | Cork | Follow Us On Social Media Handicap  | **Joyful Tidings** | B | 0.179 | 0.012 | 0.076 | 0.656 |  |
| 8:20 | Hexham | Port Of Blyth Handicap Hurdle (Clas | **Well Educated** | B | 0.178 | 0.013 | 0.079 | 0.822 |  |
| 4:10 | Lingfield | Follow @attheraces On Instagram Han | **Poetic Grace** | B | 0.172 | 0.011 | 0.072 | 0.593 |  |
| 2:10 | Lingfield | Get Raceday Ready Handicap (Class 5 | **Big Bear Hug** | B | 0.163 | 0.004 | 0.007 | 0.419 |  |
| 5:55 | Lingfield | Free Bets On attheraces.com Handica | **Harry Brown** | B | 0.150 | 0.008 | 0.034 | 0.720 |  |
| 3:20 | Nottingham | Dine In Sherwoods Restaurant Handic | **Lady Lauren** | B | 0.144 | 0.007 | 0.025 | 0.470 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-05-19T12:03:14.357021+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
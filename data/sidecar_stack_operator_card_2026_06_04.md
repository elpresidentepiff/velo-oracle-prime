# SIDECAR STACK OPERATOR CARD — 2026-06-04

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
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 6 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 27 |
| SUPPRESS | Tier B + VP<0.30 | 1 |

**Total races scanned:** 43  
**VP30 selections:** 33

---

## A. ELITE STACK — Tier A + VP30 + MDS (0)

*No signals for this stack today.*

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (0)

*No signals for this stack today.*

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (6)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 17:30 | Leopardstown | Irish Stallion Farms EBF Fillies Ma | **Margot Mae** | A | 0.410 | 0.141 | 0.541 | 0.676 | TIER_A VP30 IMP_HIGH |
| 18:10 | Lingfield (AW) | Sky Sports Racing Sky 415 'Confined | **Sunshine Star** | A | 0.543 | 0.220 | 0.410 | 0.901 | TIER_A VP30 IMP_HIGH |
| 18:50 | Ffos Las | Llanelli Mind Novice Stakes (GBB Ra | **Real Trouble** | A | 0.583 | 0.410 | 0.461 | 0.942 | TIER_A VP30 IMP_HIGH |
| 19:00 | Leopardstown | Irish Stallion Farms EBF Median Auc | **Fleur De Provence** | A | 0.551 | 0.222 | 0.483 | 0.858 | TIER_A VP30 IMP_HIGH |
| 19:40 | Lingfield (AW) | Download The At The Races App EBF R | **Fire Thunder** | A | 0.577 | 0.284 | 0.511 | 0.963 | TIER_A VP30 IMP_HIGH |
| 20:10 | Lingfield (AW) | Download The At The Races App EBF R | **Ron's Angel** | A | 0.726 | 0.249 | 0.424 | 0.929 | TIER_A VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (27)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:00 | Uttoxeter | Racing To School Reaches 25 Years N | **Loriko** | A | 0.792 | 0.352 | 0.155 | 0.981 | TIER_A VP30 |
| 14:12 | Wetherby | Vauxhall Knaresborough Britsh EBF F | **Ziggy Starshine** | A | 0.659 | 0.212 | 0.271 | 0.861 | TIER_A VP30 |
| 14:21 | Hamilton | Sodexo Live! 2yo Series EBF Maiden  | **Angels Passing** | C | 0.387 | 0.117 | 0.016 | 0.769 | VP30 |
| 14:30 | Uttoxeter | JAL Roofing Novices' Hurdle (GBB Ra | **Coumeenoole** | A | 0.646 | 0.312 | 0.100 | 0.961 | TIER_A VP30 |
| 14:42 | Wetherby | Vauxhall Knaresborough Britsh EBF F | **Cheeky Chesca** | A | 0.354 | 0.118 | 0.185 | 0.573 | TIER_A VP30 |
| 15:00 | Uttoxeter | Nourkrin Handicap Hurdle | **Secret Trix** | A | 0.459 | 0.061 | 0.037 | 0.705 | TIER_A VP30 |
| 15:12 | Wetherby | Amstel Fillies' Novice Stakes (GBB  | **Veil Of Clouds** | B | 0.382 | 0.075 | 0.088 | 0.220 | VP30 |
| 15:21 | Hamilton | Weatherbys Global Stallions Handica | **Pearl Eye** | A | 0.686 | 0.082 | 0.082 | 0.701 | TIER_A VP30 |
| 15:30 | Uttoxeter | JMI Planning 10 Years In Business M | **Regal Renaissance** | B | 0.411 | 0.154 | 0.017 | 0.937 | VP30 |
| 15:42 | Wetherby | Heineken 0.0 Fillies' Handicap | **Nanoscience** | B | 0.352 | 0.022 | 0.043 | 0.162 | VP30 |
| 15:51 | Hamilton | Weatherbys Digital Solutions Clyde  | **Eternal Force** | B | 0.369 | 0.045 | 0.022 | 0.623 | VP30 |
| 16:00 | Uttoxeter | Litholexal Handicap Hurdle | **Beorma** | A | 0.608 | 0.061 | 0.036 | 0.566 | TIER_A VP30 |
| 16:12 | Wetherby | Malvern Castle And Compass Hospital | **Ciao Capo** | B | 0.345 | 0.055 | 0.038 | 0.413 | VP30 |
| 16:30 | Uttoxeter | Turf Services Handicap Chase (ARC S | **Wheresmemoneygone** | B | 0.328 | 0.029 | 0.017 | 0.434 | VP30 |
| 16:42 | Wetherby | Book Your Autumn Hospitality Packag | **Inspired** | B | 0.310 | 0.018 | 0.037 | 0.240 | VP30 |
| 17:03 | Uttoxeter | Quinnbet Handicap Hurdle | **Ask A Sainte** | A | 0.482 | 0.053 | 0.027 | 0.560 | TIER_A VP30 |
| 17:10 | Lingfield (AW) | Sky Sports Racing Virgin 512 Handic | **Adelaide Bay** | B | 0.302 | 0.024 | 0.032 | 0.379 | VP30 |
| 17:22 | Hamilton | Hampton By Hilton Hamilton Park Han | **Recobella** | C | 0.374 | 0.047 | 0.055 | 0.425 | VP30 |
| 17:40 | Lingfield (AW) | attheraces.com/marketmovers Handica | **Peregrine Falcon** | B | 0.436 | 0.043 | 0.032 | 0.485 | VP30 |
| 17:50 | Wetherby | Book Tickets Online At wetherbyraci | **Data Fata Secutus** | B | 0.302 | 0.026 | 0.023 | 0.227 | VP30 |
| 18:30 | Leopardstown | King George V Cup (Listed Race) | **Endorsement** | A | 0.837 | 0.470 | 0.203 | 0.998 | TIER_A VP30 |
| 18:40 | Lingfield (AW) | Free Bets On attheraces.com Handica | **Raspoutine** | A | 0.655 | 0.089 | 0.043 | 0.740 | TIER_A VP30 |
| 19:20 | Ffos Las | Pro Panther Handicap | **Devious Devan** | B | 0.333 | 0.019 | 0.034 | 0.275 | VP30 |
| 19:30 | Leopardstown | BOYLE Sports 'Home Of The Early Pay | **Sweet Baby Zou** | C | 0.336 | 0.035 | 0.018 | 0.403 | VP30 |
| 19:50 | Ffos Las | New Thomas Arms Handicap | **Kelly Burn** | B | 0.522 | 0.052 | 0.072 | 0.450 | VP30 |
| 20:20 | Ffos Las | Go Maintenance Classified Stakes | **Buck Barrow** | B | 0.472 | 0.145 | 0.211 | 0.868 | VP30 |
| 20:50 | Ffos Las | New Thomas Arms Handicap | **Ghost Story** | A | 0.607 | 0.059 | 0.034 | 0.624 | TIER_A VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 20:30 | Leopardstown | Leopardstown Premier Lounge Handica | **Chirac** | B | 0.265 | 0.013 | 0.043 | 0.136 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-06-05T01:21:13.825331+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
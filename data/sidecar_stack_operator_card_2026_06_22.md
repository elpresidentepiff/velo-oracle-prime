# SIDECAR STACK OPERATOR CARD — 2026-06-22

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
| STRONG_STACK_PLUS | VP≥0.30 + MDS>0.50 + IMP>0.40 | 1 |
| STRONG_STACK | VP≥0.30 + MDS>0.50 (no IMP) | 1 |
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 1 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 25 |
| SUPPRESS | Tier B + VP<0.30 | 2 |

**Total races scanned:** 33  
**VP30 selections:** 28

---

## A. ELITE STACK — Tier A + VP30 + MDS (2)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:45 | Musselburgh | 100% Racing TV Profits Back To Raci | **Lady Dublin** | A | 0.713 | 0.641 | 0.321 | 0.989 | TIER_A VP30 MDS_HIGH |
| 18:35 | Brighton | Download The Fairplay App Now EBF M | **Roxa Love** | A | 0.702 | 0.571 | 0.507 | 0.995 | TIER_A VP30 MDS_HIGH IMP_HIGH |

## B. STRONG STACK PLUS — VP30 + MDS + IMP (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 18:35 | Brighton | Download The Fairplay App Now EBF M | **Roxa Love** | A | 0.702 | 0.571 | 0.507 | 0.995 | TIER_A VP30 MDS_HIGH IMP_HIGH |

## C. STRONG STACK — VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:45 | Musselburgh | 100% Racing TV Profits Back To Raci | **Lady Dublin** | A | 0.713 | 0.641 | 0.321 | 0.989 | TIER_A VP30 MDS_HIGH |

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 18:45 | Windsor | Track Radio On Digital & DAB Restri | **House Of Medici** | B | 0.325 | 0.305 | 0.410 | 0.926 | VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (25)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:15 | Musselburgh | Future Ticketing Handicap | **Only Dream Big** | A | 0.676 | 0.090 | 0.041 | 0.771 | TIER_A VP30 |
| 14:30 | Catterick | British EBF Maiden Fillies' Stakes  | **Roots In Touche** | A | 0.581 | 0.360 | 0.274 | 0.937 | TIER_A VP30 |
| 15:00 | Catterick | Jimmy Loxam Is 80 Today "Confined"  | **Albegone** | B | 0.324 | 0.040 | 0.016 | 0.510 | VP30 |
| 15:15 | Musselburgh | Tamper-Proof Handicap | **Patontheback** | B | 0.331 | 0.011 | 0.031 | 0.233 | VP30 |
| 15:30 | Catterick | Catterick Racecourse Supporting Rac | **Battenburg Belle** | A | 0.509 | 0.061 | 0.027 | 0.646 | TIER_A VP30 |
| 15:45 | Musselburgh | Haysmith By A Nose 60th Birthday Ha | **Sophiesticate** | A | 0.580 | 0.037 | 0.077 | 0.851 | TIER_A VP30 |
| 16:00 | Catterick | Congratulations To The Happy Couple | **Yorkshire Queen** | C | 0.369 | 0.035 | 0.038 | 0.565 | VP30 |
| 16:15 | Musselburgh | Racing TV Profits Returned To Racin | **Wee Mary** | B | 0.489 | 0.039 | 0.011 | 0.272 | VP30 |
| 16:35 | Catterick | Start Your Racing TV Free Trial Han | **Valley Of Flowers** | A | 0.608 | 0.272 | 0.043 | 0.997 | TIER_A VP30 |
| 16:45 | Musselburgh | Stand In What You Stand For Handica | **Port Darwin** | A | 0.806 | 0.123 | 0.117 | 0.983 | TIER_A VP30 |
| 17:15 | Musselburgh | Watch On Racing TV Apprentice Handi | **Approaching Dawn** | A | 0.568 | 0.055 | 0.081 | 0.799 | TIER_A VP30 |
| 17:25 | Ballinrobe | Ronan & Tom Gibbons Memorial Appren | **Zitkala Sa** | C | 0.335 | 0.082 | 0.039 | 0.556 | VP30 |
| 17:45 | Windsor | Royal Windsor Supports Racing Staff | **Just King High** | B | 0.485 | 0.029 | 0.081 | 0.406 | VP30 |
| 17:55 | Ballinrobe | Irish Stallion Farms EBF Median Auc | **Wonderfulwonderful** | A | 0.431 | 0.198 | 0.193 | 0.838 | TIER_A VP30 |
| 18:05 | Brighton | Bet Now With fairplaybet.co.uk Hand | **Harry Brown** | A | 0.519 | 0.071 | 0.034 | 0.838 | TIER_A VP30 |
| 18:15 | Windsor | British Stallion Studs EBF Newcomer | **Perfect Nation** | B | 0.311 | 0.070 | 0.087 | 0.223 | VP30 |
| 19:05 | Brighton | Watch Live Racing On fairplaybet.co | **Gearing's Point** | A | 0.546 | 0.081 | 0.077 | 0.764 | TIER_A VP30 |
| 19:17 | Windsor | Fitzdares Sprint Series Handicap (W | **Nogo's Dream** | C | 0.346 | 0.036 | 0.062 | 0.607 | VP30 |
| 19:37 | Brighton | Fairplay Lets Bet On It! Handicap | **Joycean Way** | A | 0.669 | 0.237 | 0.077 | 0.915 | TIER_A VP30 |
| 19:50 | Windsor | Carrington Wealth Management Handic | **Rumbustious** | A | 0.472 | 0.081 | 0.043 | 0.910 | TIER_A VP30 |
| 20:00 | Ballinrobe | GAIN The Advantage Series Handicap | **Miss Australie** | B | 0.355 | 0.012 | 0.103 | 0.295 | VP30 |
| 20:10 | Brighton | Fairplay Daily Price Boosts "Confin | **King Of War** | A | 0.608 | 0.219 | 0.107 | 0.923 | TIER_A VP30 |
| 20:20 | Windsor | Fitzdares Taking Bets Since 1882 Ha | **Wedgewood** | B | 0.413 | 0.067 | 0.131 | 0.335 | VP30 |
| 20:30 | Ballinrobe | Irish Stallion Farms EBF Fillies Ha | **La Dame Blanche** | B | 0.371 | 0.026 | 0.086 | 0.563 | VP30 |
| 20:50 | Windsor | Vnetrix Cyber Security Solutions Ha | **Mertoun** | A | 0.776 | 0.059 | 0.083 | 0.614 | TIER_A VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (2)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 17:10 | Catterick | Racing Again 8th July Handicap | **Captain Cess** | B | 0.257 | 0.024 | 0.007 | 0.253 |  |
| 18:25 | Ballinrobe | Lodge At Ashford Castle Maiden | **Mano Chicago** | B | 0.269 | 0.205 | 0.154 | 0.904 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-06-22T20:05:09.123115+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
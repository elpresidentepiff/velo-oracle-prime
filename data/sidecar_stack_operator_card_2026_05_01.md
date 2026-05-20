# SIDECAR STACK OPERATOR CARD — 2026-05-01

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
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 1 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 13 |
| SUPPRESS | Tier B + VP<0.30 | 9 |

**Total races scanned:** 43  
**VP30 selections:** 15

---

## A. ELITE STACK — Tier A + VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 8:00 | Warwick | Carr & Day & Martin Open Hunters' C | **Unexpected Party** | A | 0.428 | 0.502 | 0.086 | 0.956 | TIER_A VP30 MDS_HIGH |

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 8:00 | Warwick | Carr & Day & Martin Open Hunters' C | **Unexpected Party** | A | 0.428 | 0.502 | 0.086 | 0.956 | TIER_A VP30 MDS_HIGH |

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 1:45 | Newmarket | Darley EBF Maiden Fillies' Stakes ( | **Earth Shot** | A | 0.362 | 0.496 | 0.545 | 0.990 | TIER_A VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (13)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 5:40 | Warwick | GB Pointing Open Hunters' Chase | **Mister Coffey** | A | 0.571 | 0.381 | 0.052 | 0.975 | TIER_A VP30 |
| 4:30 | Warwick | Connolly's Red Mills Open Hunters'  | **Great Valley** | B | 0.465 | 0.450 | 0.023 | 0.976 | VP30 |
| 2:40 | Goodwood | British Stallion Studs John Dunlop  | **Pacific Avenue** | A | 0.425 | 0.224 | 0.027 | 0.987 | TIER_A VP30 |
| 6:50 | Warwick | Natural Green Creative Spaces Mares | **Police Academy** | A | 0.400 | 0.231 | 0.098 | 0.798 | TIER_A VP30 |
| 2:20 | Newmarket | JCB Newmarket Stakes (Listed Race)  | **Poseidon's Warrior** | A | 0.386 | 0.271 | 0.035 | 0.989 | TIER_A VP30 |
| 4:55 | Ascot | Darley British EBF Fillies' Novice  | **So Regal** | A | 0.371 | 0.185 | 0.077 | 0.734 | TIER_A VP30 |
| 6:40 | Punchestown | Boodles Champion Hurdle (Grade 1) | **Lossiemouth** | A | 0.366 | 0.359 | 0.049 | 0.808 | TIER_A VP30 |
| 2:00 | Ascot | Ascot Shop Royal Ascot Two-Year-Old | **Adaay Of Scarlett** | B | 0.348 | 0.133 | 0.039 | 0.874 | VP30 |
| 7:25 | Warwick | Foran Equine Open Hunters' Chase | **Slipway** | B | 0.344 | 0.059 | 0.013 | 0.500 | VP30 |
| 6:15 | Warwick | Jonathan Neesom Memorial Open Hunte | **Crawter** | C | 0.333 | 0.069 | 0.011 | 0.698 | VP30 |
| 3:50 | Goodwood | British Stallion Studs EBF Daisy Wa | **Crepe Suzette** | A | 0.328 | 0.145 | 0.099 | 0.976 | TIER_A VP30 |
| 6:30 | Newcastle (AW) | Roflow Specialist Ventilation & Deh | **Eklleem** | B | 0.308 | 0.341 | 0.386 | 0.913 | VP30 |
| 4:40 | Newmarket | Pertemps Network King Charles II St | **Ellusive Butterfly** | B | 0.308 | 0.027 | 0.041 | 0.740 | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (9)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 5:53 | Newcastle (AW) | Roflow Dust & Fume Lev Systems Hand | **Melinda** | B | 0.283 | 0.043 | 0.139 | 0.881 |  |
| 4:50 | Punchestown | Hanlon Concrete Irish EBF Glencarra | **Dinoblue** | B | 0.273 | 0.450 | 0.136 | 0.960 |  |
| 4:05 | Newmarket | Betfred "Nifty 50" Handicap | **Benacre** | B | 0.268 | 0.029 | 0.139 | 0.884 |  |
| 4:45 | Newcastle (AW) | Quaff Box Handicap | **Fallacious Promise** | B | 0.267 | 0.060 | 0.058 | 0.948 |  |
| 5:00 | Goodwood | Fitzdares Dedicated Personal Bettin | **Foothold** | B | 0.254 | 0.014 | 0.027 | 0.739 |  |
| 4:25 | Goodwood | Fitzdares Offer Top Prices At Goodw | **Kiss And Run** | B | 0.245 | 0.017 | 0.078 | 0.645 |  |
| 7:02 | Newcastle (AW) | Northumbria Leisure For Gaming Mach | **Stoic Poet** | B | 0.243 | 0.018 | 0.063 | 0.637 |  |
| 3:30 | Newmarket | Betfred Jockey Club Stakes (Group 2 | **Santorini Star** | B | 0.229 | 0.026 | 0.065 | 0.594 |  |
| 7:33 | Newcastle (AW) | Hays Travel: Nobody Offers You More | **Blufferonthebus** | B | 0.228 | 0.023 | 0.086 | 0.677 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-05-02T10:53:59.743874+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
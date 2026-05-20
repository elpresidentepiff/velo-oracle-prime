# SIDECAR STACK OPERATOR CARD — 2026-05-02

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
| STRONG_STACK | VP≥0.30 + MDS>0.50 (no IMP) | 2 |
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 1 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 8 |
| SUPPRESS | Tier B + VP<0.30 | 8 |

**Total races scanned:** 55  
**VP30 selections:** 11

---

## A. ELITE STACK — Tier A + VP30 + MDS (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 1:55 | Uttoxeter | Support The Stoke City Foundation " | **Tap Tap Shamie** | A | 0.372 | 0.503 | 0.352 | 0.978 | OK | TIER_A VP30 MDS_HIGH |

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (2)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 4:40 | Hexham | mybettingsites.com/ie Everything Ne | **Seeyouinmydreams** | B | 0.438 | 0.644 | 0.293 | 0.999 | OK | VP30 MDS_HIGH |
| 1:55 | Uttoxeter | Support The Stoke City Foundation " | **Tap Tap Shamie** | A | 0.372 | 0.503 | 0.352 | 0.978 | OK | TIER_A VP30 MDS_HIGH |

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 5:50 | Doncaster | Ings Environmental Susan Duker Memo | **Rocket Boots** | A | 0.393 | 0.258 | 0.585 | 0.827 | OK | TIER_A VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (8)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 2:10 | Thirsk | British EBF Fillies' Novice Stakes  | **Town Queen** | A | 0.571 | 0.447 | 0.334 | 0.974 | OK | TIER_A VP30 |
| 6:15 | Hexham | Max And Naomi Are Getting Married N | **Moonshine Man** | A | 0.470 | 0.030 | 0.077 | 0.920 | OK | TIER_A VP30 |
| 1:35 | Thirsk | Steve Poskitt's 60th Birthday Restr | **Tamam Star** | A | 0.430 | 0.353 | 0.287 | 0.906 | OK | TIER_A VP30 |
| 4:15 | Punchestown | SBK Irish EBF Mares Champion Hurdle | **Wodhooh** | B | 0.407 | 0.381 | 0.068 | 0.985 | OK | VP30 |
| 2:05 | Goodwood | Fitzdares Conqueror Fillies' Stakes | **Blue Bolt** | A | 0.346 | 0.205 | 0.029 | 0.900 | OK | TIER_A VP30 |
| 7:32 | Doncaster | Free Race Replays On attheraces.com | **Trucial Pearl** | A | 0.333 | 0.036 | 0.143 | 0.969 | OK | TIER_A VP30 |
| 1:20 | Uttoxeter | Support The Stoke City Foundation " | **Lexington Wood** | A | 0.331 | 0.313 | 0.262 | 0.773 | OK | TIER_A VP30 |
| 12:55 | Goodwood | Elston Supports UK Financial Advise | **Ciarrai Abu** | B | 0.301 | 0.174 | 0.220 | 0.777 | OK | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (8)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Meta | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 1:30 | Goodwood | Fitzdares Chelmer Fillies' Stakes ( | **Fitzella** | B | 0.288 | 0.069 | 0.078 | 0.853 | OK |  |
| 6:27 | Doncaster | Sky Sports Racing Virgin 512 Handic | **Papa Cocktail** | B | 0.283 | 0.030 | 0.127 | 0.775 | OK |  |
| 5:05 | Goodwood | Fitzdares Telephone And Text Bettin | **Startled** | B | 0.246 | 0.046 | 0.078 | 0.766 | OK |  |
| 2:45 | Goodwood | Munro UK Equity Income Fund Handica | **Appier** | B | 0.244 | 0.011 | 0.036 | 0.579 | OK |  |
| 3:10 | Uttoxeter | Lord Thomas Playdough Ryan Novices' | **Tom Desjy** | B | 0.244 | 0.106 | 0.163 | 0.762 | OK |  |
| 1:45 | Newmarket | Betfred Handicap (Heritage Handicap | **Double Rush** | B | 0.238 | 0.138 | 0.071 | 0.719 | OK |  |
| 3:50 | Uttoxeter | Pirtek UK & Ireland Handicap Hurdle | **Corsican Caper** | B | 0.236 | 0.018 | 0.096 | 0.518 | OK |  |
| 3:20 | Goodwood | Highclere Castle Gin Handicap | **Rory Rocket** | B | 0.234 | 0.017 | 0.081 | 0.875 | OK |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-05-02T15:40:35.109780+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
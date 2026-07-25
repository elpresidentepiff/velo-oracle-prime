# SIDECAR STACK OPERATOR CARD — 2026-06-24

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
| VP30_IMPROVE | VP≥0.30 + IMP>0.40 (no MDS) | 1 |
| VP30_BASE | VP≥0.30 only (no MDS, no IMP) | 12 |
| SUPPRESS | Tier B + VP<0.30 | 15 |

**Total races scanned:** 39  
**VP30 selections:** 13

---

## A. ELITE STACK — Tier A + VP30 + MDS (0)

*No signals for this stack today.*

## B. STRONG STACK PLUS — VP30 + MDS + IMP (0)

*No signals for this stack today.*

## C. STRONG STACK — VP30 + MDS (0)

*No signals for this stack today.*

## D. VP30 + IMPROVE — VP30 + IMP (no MDS) (1)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 14:21 | Salisbury | Dragon Symbol Standing At Whitsbury | **Cavalier** | A | 0.327 | 0.186 | 0.417 | 0.573 | TIER_A VP30 IMP_HIGH |

## E. VP30 BASE — VP30 only (12)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 10:30 | Worcester | CopyBet Proudly Backs UK Horse Raci | **Doyouknowwhatimean** | B | 0.318 | 0.074 | 0.059 | 0.654 | VP30 |
| 11:00 | Worcester | CopyBet Daily World Cup Profit Boos | **Most Wanted** | A | 0.357 | 0.085 | 0.176 | 0.780 | TIER_A VP30 |
| 11:30 | Worcester | Lawson Froggatt Is 80 Today Nationa | **Thepassingtyphoon** | A | 0.373 | 0.188 | 0.243 | 0.764 | TIER_A VP30 |
| 14:00 | Carlisle | Get Best Odds With Oddschecker Maid | **Silesia** | A | 0.429 | 0.263 | 0.396 | 0.723 | TIER_A VP30 |
| 16:55 | Salisbury | Showcasing Standing At Whitsbury Ma | **Raspoutine** | A | 0.547 | 0.120 | 0.205 | 0.750 | TIER_A VP30 |
| 17:05 | Carlisle | Stablemate By Agma Cumberland Plate | **Bravais** | A | 0.376 | 0.073 | 0.150 | 0.661 | TIER_A VP30 |
| 17:35 | Carlisle | Racing Staff Week Fillies' Handicap | **Who Wants Me** | A | 0.340 | 0.064 | 0.161 | 0.607 | TIER_A VP30 |
| 17:40 | Naas | ARKequine Handicap | **Realtin Fantasy** | B | 0.328 | 0.062 | 0.170 | 0.494 | VP30 |
| 18:10 | Naas | Race & Stay Irish Racing Tours Rate | **Go Just Do It** | A | 0.360 | 0.067 | 0.019 | 0.660 | TIER_A VP30 |
| 18:40 | Naas | Al Shira'aa Racing Irish EBF Jannah | **Cameo** | A | 0.464 | 0.068 | 0.122 | 0.680 | TIER_A VP30 |
| 18:50 | Kempton (AW) | Unibet More Extra Place Races Filli | **Brave Byreflection** | B | 0.316 | 0.043 | 0.191 | 0.553 | VP30 |
| 20:54 | Kempton (AW) | Tom Farrell Memorial Handicap | **Break Point** | B | 0.348 | 0.047 | 0.075 | 0.427 | VP30 |

## F. SUPPRESS — Tier B + VP<0.30 (15)

| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |
|---|---|---|---|---|---:|---:|---:|---:|---|
| 12:00 | Worcester | FBC Manby Bowdler Handicap Hurdle | **Gone In Sixty** | B | 0.184 | 0.053 | 0.194 | 0.612 |  |
| 12:30 | Worcester | Squarcle Sprint Novices' Hurdle (Ar | **Hawk's Rock** | B | 0.173 | 0.118 | 0.352 | 0.794 |  |
| 14:51 | Salisbury | Whitsbury Manor Stud Supporting Ins | **HK Fourteen** | B | 0.250 | 0.039 | 0.061 | 0.227 |  |
| 15:00 | Carlisle | Download The Oddschecker App EBF Re | **Mottaret** | B | 0.203 | 0.142 | 0.377 | 0.431 |  |
| 15:21 | Salisbury | Juddmonte EBF Restricted Novice Sta | **Everatease** | B | 0.215 | 0.097 | 0.424 | 0.460 | IMP_HIGH |
| 16:02 | Carlisle | Irish Stallion Farms EBF Eternal St | **Ellusive Butterfly** | B | 0.265 | 0.041 | 0.093 | 0.556 |  |
| 17:25 | Salisbury | Madar Corporation Handicap | **Sail On Sailor** | B | 0.240 | 0.020 | 0.084 | 0.194 |  |
| 17:30 | Ffos Las | Dandara EBF Novice Stakes (GBB Race | **This Moment** | B | 0.254 | 0.085 | 0.324 | 0.352 |  |
| 18:00 | Ffos Las | Dandara Golwg Gwendraeth Handicap | **Green Valentine** | B | 0.285 | 0.030 | 0.153 | 0.316 |  |
| 18:20 | Kempton (AW) | Unibet/EBF Restricted Novice Stakes | **Jazzy Blue** | B | 0.240 | 0.105 | 0.532 | 0.534 | IMP_HIGH |
| 19:00 | Ffos Las | Dress For The Occasions Handicap | **Emery Down** | B | 0.230 | 0.031 | 0.115 | 0.260 |  |
| 19:20 | Kempton (AW) | Unibet Supporting Safer Gambling/EB | **Jimtrott** | B | 0.159 | 0.070 | 0.324 | 0.380 |  |
| 19:30 | Ffos Las | Preventapest Handicap | **Port Erin** | B | 0.290 | 0.055 | 0.060 | 0.356 |  |
| 19:50 | Kempton (AW) | Try Unibet's New Smartview Racecard | **Notimeforchitchat** | B | 0.222 | 0.031 | 0.182 | 0.455 |  |
| 20:30 | Ffos Las | Dress For The Occasions Handicap | **Spirit Dreamer** | B | 0.234 | 0.062 | 0.203 | 0.363 |  |

---

**No scoring changes. No model changes. No SQPE changes. No router changes. No staking. No live execution. No Telegram betting alerts.**

*Generated: 2026-06-24T23:45:05.620785+00:00*

*OPERATOR VISIBILITY ONLY — These are sidecar stack signals. They do not change live scoring, do not trigger staking, and are not betting instructions.*
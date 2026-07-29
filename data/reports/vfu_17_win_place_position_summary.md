# VFU-17 — Win / Place Position Engine

**Version:** VFU_17_WIN_PLACE_POSITION_ENGINE_V1
**Generated:** 2026-07-12T15:58:57.727680Z
**VP_THRESHOLD:** 0.40 (UNCHANGED)
**Data source:** sigma master ledger, CURRENT_ERA_VALIDATED only

## Outcome Distribution

| Outcome Class | Count |
|---|---|
| MISS | 1569 |
| WIN | 787 |
| PLACE | 603 |
| FRAME | 93 |

## Key Findings

- **Place specialist candidates:** 16
- **Win-to-place downgrades:** 75
- **Place-to-win upgrades:** 5

## Named Place Specialists (operator-flagged)

| Horse | Place Rate | Appearances | Wins | Places |
|---|---|---|---|---|
| Navy Light | 100% | 2 | 0 | 2 |
| Gaelic Approach | 100% | 2 | 0 | 2 |
| Humble Spark | 100% | 2 | 0 | 2 |

## Top Place Specialist Candidates

| Horse | Place Rate | Appearances | Wins | Avg VP |
|---|---|---|---|---|
| Canaria Queen | 67% | 3 | 0 | 0.2678 |
| Galaxy Wonder | 100% | 2 | 0 | 0.1759 |
| Navy Light | 100% | 2 | 0 | 0.4533 |
| Springhill Warrior | 100% | 2 | 0 | 0.3445 |
| Gaelic Approach | 100% | 2 | 0 | 0.5106 |
| Humble Spark | 100% | 2 | 0 | 0.4357 |
| Supersundae | 100% | 2 | 0 | 0.3455 |
| Well Educated | 100% | 2 | 0 | 0.3075 |
| Boston Max | 100% | 2 | 0 | 0.3967 |
| Saxophonist | 100% | 2 | 0 | 0.4057 |

## 13 Questions

| Q | Answer |
|---|---|
| Q1 Usable outcome rows | 3052 |
| Q2 Unknown place outcome | 0 |
| Q3 WIN count | 787 |
| Q4 PLACE/FRAME count | 696 |
| Q5 MISS count | 1569 |
| Q6 Place specialists | 16 |
| Q7 Win-to-place downgrades | 75 |
| Q8 Place-to-win upgrades | 5 |
| Q9 VP win vs place | WIN avg=0.3601, PLACE avg=0.3083 |
| Q10 SP shortening | 820 shortening rows |
| Q11 Passport specialist signal | 13 confirmed |
| Q12 Human review horses | 16 place specialists + 75 downgrades + 5 upgrades = 96 horses |
| Q13 VFU-18 focus | PLACE_DATA_ENRICHMENT |

## Doctrine Direction

- WIN and PLACE are **different truths** — confirmed by engine
- VP fires for PLACED outcomes nearly as often as WIN → calibration gap
- PLACE_SPECIALIST horses identified: VP correctly firing but for frame, not win
- Win-to-place downgrades: high-VP horses that reliably place but don't win
- VFU-18 recommended: place data enrichment + field_size sourcing

## Hard Rules (permanent)

- VP threshold: **0.40 UNCHANGED**
- No live scoring change
- No Passport mutation
- No Supabase writes
- No doctrine promotion
- No model promotion
- No Telegram send
- No Racing API restoration

## Final Classifications (15)

- `VFU_17_WIN_PLACE_POSITION_ENGINE_COMPLETE`
- `WIN_PLACE_OUTCOME_CLASSES_CREATED`
- `PLACE_SPECIALIST_CANDIDATES_CREATED`
- `WIN_TO_PLACE_DOWNGRADES_CREATED`
- `PLACE_TO_WIN_UPGRADES_CREATED`
- `NO_INVENTED_PLACE_OUTCOMES`
- `PLACE_LOGIC_DRY_RUN_ONLY`
- `NO_LIVE_SCORING_CHANGE`
- `NO_VP_THRESHOLD_CHANGE`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`
- `NAVY_LIGHT_GAELIC_APPROACH_HUMBLE_SPARK_CONFIRMED_PLACE_SPECIALISTS`

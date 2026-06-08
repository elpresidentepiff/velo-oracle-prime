# Race Shape Model V1 — Design Specification

**Status:** DESIGN_PENDING — no implementation until operator approval  
**Origin:** Midprice delta diagnosis identified race-shape as root cause of 67% mid-price misses  
**Classification:** Research design document. No scoring changes. No routing changes.

---

## Problem Statement

VELO's top-pick VP model ranks horses by individual quality metrics (form, speed, class, market). It does not model how a specific field of horses will interact in the race itself.

Mid-price winners (SP 3–8.5) win races because the race shape collapses the top-rated horse:
- Front-runner gets a suicidal pace (burns out)
- Come-from-behind type benefits from slow early pace
- Top-weighted horse gets blocked / poor trip
- Class-drop horse gets a soft lead
- Going change neutralises the "best" horse

These are structural race-level outcomes, not horse-quality differences. VP cannot see them from horse-level data alone.

---

## Features to Derive

### Pace Map Features
| Feature | Source | Type |
|---|---|---|
| `likely_pace_leader` | RP comments ("races prominently", "front runner") | boolean per runner |
| `pace_pressure_count` | number of likely pace leaders in field | integer |
| `hold_up_count` | runners with "held up", "late headway" comments | integer |
| `pace_scenario` | CONTESTED / LONE_LEADER / MUDDLING | categorical |
| `pace_collapse_risk` | pace_pressure_count >= 3 AND no hold-up runners | boolean |

### Draw / Position Features
| Feature | Source | Type |
|---|---|---|
| `draw` | racecard draw field | integer |
| `draw_bias_signal` | draw_bias_model score | float |
| `position_pressure` | draw + pace scenario interaction | float |

### Class / Trajectory Features
| Feature | Source | Type |
|---|---|---|
| `class_drop` | OR current - OR last race (negative = drop) | float |
| `class_drop_magnitude` | abs(class_drop) | float |
| `class_drop_response` | historical SR for this trainer on class-drop | float |
| `form_trajectory` | last 3 run positions: improving / declining / flat | categorical |

### Going / Surface Features
| Feature | Source | Type |
|---|---|---|
| `going_change` | today's going vs preferred going | categorical |
| `going_advantage` | runner known to handle going better than rivals | boolean |
| `surface_specialist` | AW vs turf from OR history | boolean |

### Field Compression Features
| Feature | Source | Type |
|---|---|---|
| `field_compression` | VP spread: max(VP) - min(VP) | float |
| `favourite_vulnerability` | VP leader's MDS < 0.3 AND VP < 0.4 | boolean |
| `top3_vp_spread` | VP[rank=0] - VP[rank=2] | float |
| `market_spread` | (SP fav) / (SP rank=2) | float |

### Distance / Fitness Features
| Feature | Source | Type |
|---|---|---|
| `distance_change` | today's dist - last race dist (furlongs) | float |
| `distance_up_specialist` | trainer/horse SR going up in distance | float |
| `days_since_last_run` | fitness proxy | integer |
| `trainer_race_shape_intent` | returning from break / freshener / prep race | categorical |

### Market Structure Features
| Feature | Source | Type |
|---|---|---|
| `market_position_pressure` | SP rank vs VP rank disagreement | float |
| `sp_vp_misalign` | SP < 5.0 AND VP < 0.15 (market favours, model doesn't) | boolean |
| `midprice_position` | SP in 3.0–8.5 zone | boolean |

---

## Inputs

| Input | Path | Notes |
|---|---|---|
| Runner snapshots | `data/runner_snapshots_{date}*.jsonl` | VP, MDS, improvement, place_prob |
| RP comments | `horse_comments` Supabase table | NLP tags already extracted |
| OR/TS/RPR ratings | racecard data | Available in racecard_merged JSON |
| Forecast odds | racecard data | Used when SP not yet known |
| Draw | racecard data | Often missing — treat as optional |
| Sigma winners | `data/results_{date}.json` | Actual race winners for supervised target |

---

## Output Targets

### Phase 1 — Feature Audit
```
data/features/race_shape_features_{date}.parquet
data/reports/race_shape_audit_{date}.md
```

For each race-day: compute features, join to sigma winners, report distribution.

### Phase 2 — Discriminative Power Test
For each feature: compute SR for top pick when feature fires vs when it doesn't.  
Target: identify features with >10pp SR lift.

### Phase 3 — Race Shape Score
Combine high-lift features into a race_shape_score (0–1) per runner.  
Test as VP modifier: VP_adjusted = VP * (1 + race_shape_weight * race_shape_score)

---

## Data Availability Assessment

| Feature Group | Availability | Blocker |
|---|---|---|
| Pace map | PARTIAL — RP comments available | NLP tag extraction from existing `horse_comments` |
| Draw | LOW — often missing in racecard | Missing source data for UK flat |
| Class-drop | MEDIUM — OR available in racecard JSON | Need consecutive-race OR delta |
| Going change | MEDIUM — going in results JSON | Need preferred going from history |
| Field compression | HIGH — computed from snapshots | Already available |
| Market structure | HIGH — SP in results + VP in snapshots | Already available |
| Trainer intent | LOW — not extracted | New research required |

**Highest priority features (available now):**
1. `field_compression` (VP spread)
2. `market_position_pressure` (SP vs VP rank misalign)  
3. `midprice_position` (SP zone flag)
4. `pace_pressure_count` (from existing RP comment NLP)
5. `class_drop` (if OR data in racecard)

---

## Implementation Sequence (no approval = no implementation)

```
Phase 0 (design):    This document — DONE
Phase 1 (features):  Compute field_compression + market_pressure per race from existing data
Phase 2 (audit):     Join to sigma winners, find SR lift per feature
Phase 3 (score):     If >3 features show >10pp lift, build race_shape_score
Phase 4 (shadow):    Run alongside VP as non-scoring diagnostic
Phase 5 (test):      Test as VP modifier in shadow (no live scoring change)
Phase 6 (promote):   Only if operator approves after Gate V3 evidence
```

---

## Hard Constraints (permanent)

```
No scoring changes without operator approval
No model promotion without evidence gate
No routing changes
No live staking
This document is design only — do not implement until Phase 1 is approved
```

---

## Expected Impact

Based on midprice delta diagnosis:
- Winner visible in 97% of misses → model sees horse, ranks incorrectly
- Mean VP gap = 0.093 → model is materially confident in wrong horse
- 51.8% of winners ranked 2nd/3rd → small VP adjustment could flip ranking in these races
- Pace/class-drop/going change are the likely discriminating factors

If race-shape features can identify the 29 races where the winner was ranked 2nd/3rd, a small VP modifier could improve mid-price selection without structural model changes.

**Target:** Improve top-pick SR from 25% to 28–30% in mid-price zone. Not a fix — a research hypothesis.

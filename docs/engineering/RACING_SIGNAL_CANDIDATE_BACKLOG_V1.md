# Racing Signal Candidate Backlog V1

## Overview
This backlog identifies 13 high-value signals derived from the Racing Intelligence Research Layer. These signals target "Selection Leakage" and "Chalk Blindness" and are prioritized for future shadow experiments.

| Signal Name | Source Fields | Required Keys | Expected Value | Status |
| :--- | :--- | :--- | :--- | :--- |
| **`trainer_course_score`** | `trainer_name`, `course` | `trainer_id:course` | Performance at track | SHADOW_ANALYSIS |
| **`trainer_distance_score`** | `trainer_name`, `dist` | `trainer_id:dist` | Distance proficiency | SHADOW_ANALYSIS |
| **`jockey_course_score`** | `jockey_name`, `course` | `jockey_id:course` | Rider track efficiency | SHADOW_ANALYSIS |
| **`trainer_jockey_combo_score`**| `trainer`, `jockey` | `t:j_id` | Stable/Rider synergy | SHADOW_ANALYSIS |
| **`horse_distance_preference`** | `horse_id`, `dist_f` | `horse_id:dist` | Horse efficiency | SHADOW_ANALYSIS |
| **`horse_going_preference`** | `horse_id`, `going` | `horse_id:going` | Surface specialty | SHADOW_ANALYSIS |
| **`course_volatility_score`** | `course` | `course_id` | Field chaos proxy | SHADOW_ANALYSIS |
| **`distance_switch_signal`** | `dist_f` | `horse_id:history` | Distance change impact | SHADOW_ANALYSIS |
| **`class_drop_signal`** | `race_class` | `horse_id:history` | Class drop advantage | BLOCKED_BY_HFS |
| **`field_size_chaos_proxy`** | `scored` (runners) | `race_id` | Traffic volatility | SHADOW_ANALYSIS |
| **`market_rank_rescue_signal`** | `market_rank` | `race_id` | Selection rescue | BLOCKED_BY_MARKET |
| **`favourite_sanity_signal`** | `prob`, `market_fav` | `race_id` | selection sanity | BLOCKED_BY_MARKET |
| **`top3_containment_signal`** | `rank` | `race_id` | selection grouping | BLOCKED_BY_MARKET |

## Implementation Roadmap
1.  **Phase 1**: Shadow analysis using local JSON snapshots (No HFS required).
2.  **Phase 2**: Full-scale HFS backfill after training-safety audit (DATABASE_URL required).

---
*Authorized by VÉLØ Command Authority | Intelligence Division*

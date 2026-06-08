# RECONCILIATION PROVENANCE MAP

This document maps the current matching routes used in the Sigma reconciliation loop (`run_results_sigma.py`) and identifies areas of fragility.

| Route | Logic | Fragility | Status |
| :--- | :--- | :--- | :--- |
| **Race ID Exact** | `predictions[race_id] == results_by_id[race_id]` | High confidence if ID format is stable. | **Primary** |
| **Race ID Normalized** | SL-style ID normalized to VELO 24h format. | Format re-calculation risk. | **Secondary** |
| **Course + Time** | `(norm_course, bst_time) == results_by_course_time` | ±3 min tolerance; course name normalization. | **Fallback** |
| **Horse Name** | Case-insensitive string match on `horse` name. | Nicknames, punctuation, abbreviations. | **Fallback (High Risk)** |
| **Horse ID** | `horse_id` match within a race. | Not always present in all result sources. | **Underutilized** |

## Fragility Analysis (2026-06-02)
1. **String Matching:** Currently, the system relies on resolving "pick horse names" from the `velo_verdicts.selections` JSON array. If the `top_rank_horse_id` doesn't match an ID in the selections, it fallbacks to string names.
2. **Result Normalization:** The `cache` source (Sporting Life) derives winners and top 3 based on string positions and names, which can drift from the Racing API or RP sources.
3. **Ambiguity:** Multiple races at the same track with close start times can cause mismatches in the Course+Time fallback.

## Proposed ID-First Policy
1. Match **Race** by `race_id`.
2. Match **Horse** by `horse_id`.
3. Only use **Names** as a labeled `MATCH_DEGRADED` fallback.
4. **Quarantine** unresolved matches instead of forcing a miss.

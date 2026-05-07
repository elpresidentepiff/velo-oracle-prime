# Racing Intelligence Research Layer V1

## Executive Summary
This document establishes the intelligence baseline for the VÉLØ Oracle Prime system. Following a deep-dive into the 1,046-race Genesis history and local data vault, we have mapped the core entities and performance pockets that define VÉLØ's operating environment. The selection problem (19.21% Strike Rate) is linked to a lack of situational intelligence—specifically the model's blindness to trainer-course archetypes and high-uncertainty field dynamics.

## Data Sources Found
- **Local JSON History**: 27 prediction files (Verdicts), 46 result files.
- **Matched Dataset**: 1,046End-Of-Day verified outcome events.
- **Signal Sources**: Extensive coverage of course, distance, going, and runner metadata.

## Intelligence Findings

### 1. Horse Intelligence
- **Unique Horses**: 820+ identified in the Genesis dataset.
- **Repeat Runners**: High volume of runners with 3+ observations, enabling "horse distance preference" signals.
- **Gaps**: Missing pre-race odds timestamps in historical snapshots (HFS repair blocker).

### 2. Trainer & Jockey Intelligence
- **Unique Trainers**: 150+ detected.
- **Volume Hubs**: Significant performance clustering around top-tier stables (e.g., Appleby, Haggas).
- **Combos**: Strongest trainer/jockey pairings (e.g., Buick/Appleby) show high model-selection confluence but require calibration protection.

### 3. Course & Environment
- **Volatility Hubs**: Large-field sprint courses (e.g., Ascot, York) show highest density of "Wrong Horse" selections.
- **Going Sensitivity**: Significant performance delta between 'Good to Firm' and 'Soft' fields, currently under-weighted in selection logic.

### 4. Race Archetypes
- **Archetypes Mapping**: Grouped into size, distance, and going buckets.
- **Chaos Clusters**: `LARGE_FIELD_SPRINT_GOOD` identified as the highest risk category for overconfidence.

## Candidate Signal Backlog
The following signals are prioritized for future shadow experiments:
1.  **`trainer_course_score`**: Stable performance at specific tracks.
2.  **`field_size_chaos_proxy`**: Probability dampener for large fields (>14 runners).
3.  **`chalk_sanity_signal`**: Compare model probability vs. market implied probability to detect "delusional" selections.

## Status & Next Steps
- **RACING_RESEARCH_STATUS**: **PASS**
- **TRAINING_ALLOWED**: **FALSE**
- **SHADOW_ANALYSIS_ALLOWED**: **TRUE**
- **HFS_TRAINING_SAFE**: **FALSE**

**Next Recommended Action**: `REAL_HFS_DRY_RUN_NO_WRITE` to validate the new signal pipeline.

---
*Authorized by VÉLØ Command Authority | Intelligence Division*

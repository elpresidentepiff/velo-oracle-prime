# VÉLØ — Architecture Decisions

## 2026-03-16

### D001 — Three-layer intelligence architecture
Decision: VÉLØ operates on three distinct intelligence layers:
- MICRO: 1.7M-row runner-level raceform corpus (historical patterns, form, doctrine)
- MACRO: BHA Racing Data Pack 2012-2024 (structural racing context, regime detection)
- LIVE: Racing API real-time data (current runners, today's market, live doctrine)
Rationale: no single layer is sufficient. The horse, the race, the market, the regime, and structural environment must all inform the final verdict.

### D002 — Specialist models over monolithic SQPE growth
Decision: do NOT grow one monolithic SQPE. Build specialist model families (improvement, market deception, release window, draw bias, breeding, place/frame, comment intelligence). Combine via meta-ensemble VELO_PRIME_prob.
Rationale: rpr_vs_field dominates monolithic SQPE. Specialist models can surface regime-specific signals that get washed out in a single trained-on-everything model.

### D003 — VELO_PRIME_prob meta-ensemble target
Decision: final production probability = meta-ensemble of: base SQPE v17, improvement_score, release_day_prob, market_deception_score, place_prob, macro_competitiveness_index, macro_favourite_compression_index.
Rationale: answers not just "best horse" but "best horse, in the right regime, at the right time, with the right fit, against the right market lie."

### D004 — BHA macro data as structural context, not runner evidence
Decision: BHA Data Pack stats are NOT runner-level features. They provide structural racing context that informs regime classification, confidence calibration, favourite trap logic, and chaos mode. They are joined at race/year/code level, not runner level.
Rationale: applying industry-level stats at runner level would be ecological fallacy.

### D005 — Provenance preservation on all BHA data
Decision: all BHA data points carry ambiguity_flag where source inconsistency exists (especially HIT methodology change pre/post 2016, 2024 abandonment table misalignment). Nothing is silently fixed.
Rationale: downstream users of this data need to know which numbers are solid and which carry uncertainty.

### D006 — Chronological train/test split is mandatory
Decision: all models must use date-based train/test split. No random splits. Test set = most recent years (2024-2025 for raceform-trained models).
Rationale: random splits allow future data to inform past predictions, producing artificially inflated metrics.

### D007 — Live-usability classification required for every model
Decision: every model artifact must declare LIVE-USABLE or RESEARCH-ONLY. LIVE-USABLE = feature set can be reproduced at inference time using only pre-race available data. RESEARCH-ONLY = requires post-race data or data not available before the race.
Rationale: a beautiful research model that cannot be used at prediction time has zero betting value.

### D008 — Macro regime context is race-level, NOT runner-level
Decision: MacroContext (BHA-derived indices) is attached once per race, not once per runner. Within a race, all runners share the same macro regime. The regime modifies confidence/weights, not individual runner scores.
Rationale: the regime is a property of the racing environment in that year, not a property of individual horses.

### D009 — Chaos mode uses structural season collapse, not abandonment rate
Decision: chaos_mode fires on COVID_year flag OR fixture_strain_index < 0.72 (structural collapse). High abandonment years (2018-2019, 2023 with ~6% abandon rate) are NOT chaos — they are normal weather variation. Do NOT trigger on abandonment_stress_index alone.
Rationale: 2019 and 2023 had high abandon rates but were normal racing seasons. Only COVID-level truncated seasons are structural chaos.

### D010 — VELO_PRIME_prob weights (v1)
Decision: SQPE 45% + improvement 12% + release_window 10% + market_deception 10% + place 8% + comment_intel 8% + longshot 7% (applied only when sp >= 10.0). Macro modifiers applied after weighting.
Rationale: SQPE dominates because ratings-only (Mode A) outperforms any market combo (L004). Specialist models provide additive edge on regime-specific signals. Weights sum to 1.0 across available models.

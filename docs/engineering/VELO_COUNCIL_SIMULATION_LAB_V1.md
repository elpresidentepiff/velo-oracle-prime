# VÉLØ Council Simulation Lab V1

**Status:** DESIGN ONLY  
**Phase:** 7 — Research  
**Classification:** `COUNCIL_SIMULATION_SHADOW_ONLY` / `NO_LIVE_POLICY_CHANGES` / `DESIGN_ONLY`

---

## Purpose

Run identical historical race days through multiple policy worlds simultaneously. Compare outcomes across policies before any live change. The Council reviews the comparison before any promotion decision.

---

## Policy Worlds

| World | Policy | Description |
|---|---|---|
| A | Current VÉLØ (SQPE_IMPROVEMENT_MDS_V1) | Baseline — current production weights |
| B | Race Shape warning policy | Add race_shape_warning as suppression signal |
| C | CPU Gate V2 challenger | SQPE V18 or CPU challenger as primary |
| D | Strict quarantine policy | Any contamination → full day quarantine |
| E | Conservative no-learning policy | Learning admitted only for VP≥0.40 + Tier A |
| F | International lagged-only policy | HK/FR form-only, no market signal |

Each world runs on the same historical race days and produces:
- SR (strike rate)
- Frame rate
- Brier score
- False suppression rate (how often a winner was suppressed)
- Missed winners (winner not in top-3 ranked)
- Contamination detection accuracy
- Learning eligibility accuracy
- Promotion safety score

---

## Simulation Runner (Design)

```python
# Pseudocode — implementation in Phase 7
for world in WORLDS:
    results = []
    for race_day in historical_days:
        scores = world.score(race_day)
        result = world.evaluate(scores, actual_results[race_day])
        results.append(result)
    report[world.name] = aggregate(results)
```

The runner reads historical parquets only. Never touches live state.

---

## Council Review Workflow

1. Simulation complete → Council evidence packet generated
2. Council reviews comparison table across all policy worlds
3. If a challenger world shows improvement at n≥100 days: eligible for promotion discussion
4. Promotion requires El Presidente explicit sign-off
5. No automatic promotion at any threshold

---

## Hard Rules

```
NO_LIVE_POLICY_CHANGES: simulation is read-only research
NO_AUTOMATIC_PROMOTION: simulation findings are evidence, not decision
NO_LIVE_SCORING: simulation cannot affect VP or weights
SHADOW_ONLY: all simulation runs are shadow-only
```

```
COUNCIL_SIMULATION_LAB_V1_STATUS: DEFINED
IMPLEMENTATION: PHASE 7 — after Phase 3 harness + Phase 1 spec
```

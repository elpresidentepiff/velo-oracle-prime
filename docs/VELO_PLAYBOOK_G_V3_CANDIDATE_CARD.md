# VELO Playbook G V3 Candidate Card

## Identity
- Candidate: `ratings + doctrine + structure core + temperature scaling`
- Status: `offline_research_candidate_only`
- `not_for_deployment = true`
- Market features excluded from core: `true`
- Calibration method: `temperature_scaling_without_market`

## Why This Candidate Matters
- It is the first Playbook G candidate that:
  - beats the market baseline cleanly
  - beats the `market + ratings` baseline
  - keeps raw market features out of the learner
  - preserves HK and FR gains
  - improves calibration without market recrowding

## Core Metrics
- test log loss: `1.271421`
- test Brier: `0.067636`
- test ECE: `0.034484`
- top-1: `54.39%`
- top-3: `86.84%`

## Comparison
- market-only:
  - log loss `1.725229`
  - Brier `0.085483`
- market + ratings:
  - log loss `1.481647`
  - Brier `0.076613`
- uncalibrated V3 core:
  - log loss `1.434518`
  - Brier `0.073330`
  - ECE `0.042030`

## Market Isolation
- probability correlation to market: `0.4842`
- top-1 overlap with market: `0.3684`
- both are inside the approved isolation gates

## Jurisdiction Read
- `HK`: positive vs market
- `FR`: positive vs market
- `JPN`: informational only
- `2025`: sensitivity-only, too small for governance

## Core Guardrails
- no leakage
- no outcome fields
- no prior model outputs
- no production writes
- no HFS mutation
- no `training_eligible` changes
- no Playbook E

## What Still Blocks Promotion
- this package is research-only, not production-ready
- the full V3 suite still failed because market-assisted variants re-crowded the signal
- calibrated-candidate-specific stability evidence is still required
- `2025` remains too small
- no approved shadow or promotion governance path exists yet

## Next Governance Gate
- run a calibrated-candidate stability audit
- review calibration durability without raw market recrowding
- decide whether this package can be elevated from research candidate to shadow-only candidate

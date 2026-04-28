# Playbook G V3 Calibration Repair Design

- Recommendation: `GO_DESIGN_APPROVED_PENDING_REVIEW`
- Objective: Repair probability calibration for the ratings + doctrine + structure core without letting market information recrowd or dominate the model.

## Arms
- `CR-1` `core_uncalibrated_baseline`: Reference point for pure ratings + doctrine + structure behavior.
- `CR-2` `core_isotonic_no_market`: Repair calibration using validation-only isotonic on core scores without any market inputs.
- `CR-3` `core_platt_no_market`: Test logistic/Platt calibration on core scores only.
- `CR-4` `core_temperature_scaling_no_market`: Apply one-parameter confidence scaling to reduce overconfidence without changing ranking.
- `CR-5` `core_jurisdiction_aware_calibration_no_market`: Allow HK/FR-specific calibration on core scores only if validation support is adequate.
- `CR-6` `core_market_aware_calibration_guardrailed`: Optional market-aware calibration-side metadata experiment with strict recrowding gates and no raw market feature learning in the core.
- `CR-7` `core_residual_confidence_dampening`: Shrink extreme core probabilities toward race-level neutrality without using raw market features.
- `CR-8` `core_conservative_probability_shrinkage`: Apply conservative post-hoc shrinkage to improve calibration while preserving the core ranking signal.

## Hard Gates
- Market correlation ceiling: `<= 0.58`
- Top-1 market overlap ceiling: `<= 0.45`
- Core log-loss floor: `<= 1.434518`
- Core Brier floor: `<= 0.07333`

## Next Step
- Review this calibration-repair design, then approve or reject offline calibration-repair execution.

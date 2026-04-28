# Playbook G V3 Calibration Repair Results

- Design checkpoint: `651a1b8482a9f637aa6c63b7f3cfb39575e009ad`
- Final verdict: `PASS`
- Recommendation: `GO_CALIBRATION_REPAIR_CANDIDATE` - A calibration repair candidate exists for offline research review

## Arms
- `core_uncalibrated_baseline`: log loss `1.561109`, Brier `0.079582`, ECE `0.06363`, corr `0.5439`, overlap `0.3684`
- `core_isotonic_without_market`: log loss `1.434518`, Brier `0.073330`, ECE `0.04203`, corr `0.4823`, overlap `0.3772`
- `core_platt_without_market`: log loss `1.850769`, Brier `0.089326`, ECE `0.06247`, corr `0.5126`, overlap `0.3684`
- `core_temperature_scaling_without_market`: log loss `1.271421`, Brier `0.067636`, ECE `0.03448`, corr `0.4842`, overlap `0.3684`
- `core_jurisdiction_aware_calibration_without_market`: log loss `1.429028`, Brier `0.075373`, ECE `0.04730`, corr `0.4781`, overlap `0.3421`
- `core_market_aware_calibration_with_strict_isolation_guardrails`: log loss `1.607929`, Brier `0.080976`, ECE `0.02450`, corr `0.9835`, overlap `0.9298`
- `core_residual_confidence_dampening`: log loss `1.561109`, Brier `0.079582`, ECE `0.06363`, corr `0.5439`, overlap `0.3684`
- `core_conservative_probability_shrinkage`: log loss `1.561109`, Brier `0.079582`, ECE `0.06363`, corr `0.5439`, overlap `0.3684`

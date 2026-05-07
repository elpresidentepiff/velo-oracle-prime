# VÉLØ Shadow Experiment Plan V1

## Baseline
- **Dataset**: 1,046 matched Genesis races (2026-03-17 to 2026-05-05).
- **Strike Rate**: 19.21%
- **Brier Score**: 0.3359 (Global)
- **Calibration Error Count**: 132

## Experiment 1: High-Prob Volatility Cap
- **Hypothesis**: Capping max probability at 0.40 in large fields will reduce CALIBRATION_ERROR outcomes.
- **Metric**: Brier Score delta, Strike Rate stability.
- **Method**: Run `scripts/post_genesis_audit_driver.py` with an `adjusted_prob` overlay.

## Experiment 2: Chalk Sanity Filter
- **Hypothesis**: Forcing model selection to stay in the Market Top 3 when the favorite is strong (>45%) will capture "Easy Winners."
- **Metric**: Strike Rate increase vs. Favorite Overfit risk.

## Forbidden Actions
- No production scoring edits.
- No live model weight changes.
- No real-money execution.

## Next Step
Implement `scripts/shadow_experiment_runner.py` to replay Genesis history with these overlays and compare results.

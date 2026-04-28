# Playbook G V3 Offline Dry Run

- Design checkpoint: `300835d55eac4a9566d28a033ec537eb90de8a52`
- Eligible races / runners: `1697 / 18575`
- Best model by log loss: `ratings_plus_doctrine_with_market_calibration`
- Best model by Brier: `ratings_plus_doctrine_with_market_calibration`
- Final verdict: `FAIL`
- Recommendation: `FAIL_AND_REVIEW_V3` - V3 does not yet justify progression beyond offline research`

## Test Metrics
- `market_only_baseline`: log loss `1.725229`, Brier `0.085483`, top-1 `35.96%`, top-3 `69.30%`, ECE `0.01758`
- `market_plus_ratings_baseline`: log loss `1.481647`, Brier `0.076613`, top-1 `42.11%`, top-3 `78.95%`, ECE `0.02056`
- `doctrine_only_baseline`: log loss `2.107233`, Brier `0.097886`, top-1 `13.16%`, top-3 `39.47%`, ECE `0.00498`
- `ratings_plus_doctrine_core`: log loss `1.434518`, Brier `0.073330`, top-1 `55.26%`, top-3 `86.84%`, ECE `0.04203`
- `ratings_plus_doctrine_with_market_calibration`: log loss `1.314588`, Brier `0.067147`, top-1 `57.89%`, top-3 `89.47%`, ECE `0.04007`
- `ratings_plus_doctrine_residual_over_market`: log loss `1.407549`, Brier `0.074198`, top-1 `49.12%`, top-3 `86.84%`, ECE `0.03578`
- `hk_diagnostic`: log loss `1.218489`, Brier `0.051502`, top-1 `58.62%`, top-3 `75.86%`, ECE `0.02259`
- `fr_diagnostic`: log loss `1.425462`, Brier `0.082240`, top-1 `45.24%`, top-3 `80.95%`, ECE `0.05192`
- `year_2025_sensitivity_report`: log loss `1.665667`, Brier `0.072839`, top-1 `46.15%`, top-3 `88.46%`, ECE `0.03997` (sensitivity-only)

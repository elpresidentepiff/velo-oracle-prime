# Shadow Overlay Observation Layer V1

## Overview
The Shadow Overlay Observation Layer provides daily comparative analysis between VÉLØ's baseline probabilities and experimental calibration overlays. It allows the VÉLØ Command Authority to monitor the stability and efficacy of proposed scoring repairs over time without incurring operational risk to the production "brain."

## Primary Overlays Tracked
1.  **`calibration_cap_35`**: Primary candidate. Limits maximum probability to 0.35 to improve Brier score honesty.
2.  **`calibration_cap_30`**: Stress test candidate. Highly aggressive probability dampening.
3.  **`volatility_confidence_cap`**: Environmental risk control. Uses field size as a proxy to cap confidence in high-traffic races.

## Operational Flow
The observation runner executes nightly following the EOD Study Layer:
1.  **Ingest**: Loads daily predictions and matched results.
2.  **Simulation**: Re-calculates metrics (Brier Score, High-Confidence Losses) for each overlay.
3.  **Audit**: Confirms that winner selection (Strike Rate) remains identical to the baseline.
4.  **Reporting**: Generates a daily observation JSON and updates the rolling summary.

## Safety Guards
- **Selection Isolation**: Overlays are strictly forbidden from changing the selected horse_id. Strike rate must remain unchanged.
- **State Protection**: No mutation of `sentient_state.json`.
- **Cloud-Silent**: No Supabase writes.
- **Market Gated**: "Easy Winner" rescues and "Chalk Sanity" are explicitly blocked from claims until pre-race market ranking data is integrated.

## Reporting Artifacts
- `data/shadow_overlay_observation_{YYYYMMDD}.json`: Daily performance comparison.
- `data/shadow_overlay_observation_summary_v1.json`: Rolling metrics across all observed dates.

## Usage
```bash
PYTHONPATH=. python3 scripts/shadow_overlay_observation_runner.py --date YYYY-MM-DD
```

# VÉLØ Shadow Model Experiment Results V1

## Overview
This report summarizes the results of shadow-only scoring repair experiments conducted against the 1,046-race Genesis replay baseline. The experiments simulated various 'overlays' designed to mitigate probability drift and environmental volatility without modifying production code.

## Baseline Performance
- **Dataset**: 1,046 Matched Genesis Races
- **Strike Rate**: 19.21%
- **Brier Score**: 0.3360
- **High-Confidence Losses**: 132 (Prob > 0.45)

## Experiment Results

| Overlay Name | Brier Score | High-Conf Losses | Strike Rate | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 0.3360 | 132 | 19.21% | N/A |
| **Calibration Cap 40** | 0.1544 | 0 | 19.21% | KEEP_FOR_LONGER_SHADOW_REPLAY |
| **Calibration Cap 35** | 0.1542 | 0 | 19.21% | KEEP_FOR_LONGER_SHADOW_REPLAY |
| **Calibration Cap 30** | 0.1538 | 0 | 19.21% | KEEP_FOR_LONGER_SHADOW_REPLAY |
| **Volatility Cap** | 0.1543 | 48 | 19.21% | KEEP_FOR_LONGER_SHADOW_REPLAY |
| **Chalk Sanity Filter** | 0.1543 | 48 | 19.21% | NEEDS_MARKET_DATA |

## Key Findings
1.  **Risk Control vs. Winner Selection**: Calibration dampening materially improves probability honesty and Brier score by reducing overconfidence in short-priced selections. However, **it does not improve winner selection or rescue easy winners.** The strike rate remains unchanged at 19.21%.
2.  **Calibration Dampening**: Capping probabilities at 0.30–0.40 provides a large improvement in Brier Score and completely eliminates 'Strike' category implosions in the historical dataset from a risk-control perspective.
3.  **Volatility Protection**: Field size acts as an effective proxy for environmental chaos, suppressing overconfidence in high-traffic fields.
4.  **Market Awareness**: The Chalk Sanity Filter is blocked by a lack of historical `favourite_won` data in the Genesis dataset but remains a high-priority architectural target for live Betfair integration.

## Safety Verification
- **Production Scoring Changed**: FALSE
- **Model Weights Changed**: FALSE
- **Supabase Writes Attempted**: FALSE
- **Live Sentient State Touched**: FALSE
- **HFS Features Used**: FALSE (Field size proxy only)

---
*Authorized by VÉLØ Command Authority | Model Intelligence Division*

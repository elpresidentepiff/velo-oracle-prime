# VÉLØ Model Score Improvement Backlog V1

## Objective
Prioritize scoring logic improvements based on the Post-Genesis and Sigma audits. These improvements target "Score Leakage" and calibration errors identified in the 1,046-race history.

## Prioritized Improvements

### 1. High-Confidence Probability Drift (Priority: 1)
- **Issue**: Strike Rate on >40% probabilities is significantly lower than implied.
- **Goal**: Apply a "Volatility Cap" to flatten extreme probabilities in Chaos environments.
- **Safety**: Safe to implement now (Shadow Mode).

### 2. Favourite Sanity Gap (Priority: 2)
- **Issue**: Model deviates from market favorites without strong doctrine evidence.
- **Goal**: Implement a `market_confluence` signal that weights selection higher if it aligns with the top 2 market runners.
- **Safety**: Requires Betfair/Live market data integration.

### 3. "Chaos Bloom" Scoring Modifier (Priority: 3)
- **Issue**: Environmental volatility is not reflected in runner-level scoring.
- **Goal**: Penalize front-runners in high-chaos fields (large fields + market uncertainty).
- **Safety**: Safe to implement after HFS repair.

### 4. Loss-Type Feedback Weighting (Priority: 4)
- **Issue**: Sentient state recognizes loss types but model does not use them for real-time adjustments.
- **Goal**: Bridge Playbook G patterns to runner selection gates.
- **Safety**: Promotion Gate Required.

---
*Authorized by VÉLØ Command Authority | Engineering Division*

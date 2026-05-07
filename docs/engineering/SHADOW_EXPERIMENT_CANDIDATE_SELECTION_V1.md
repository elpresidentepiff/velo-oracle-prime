# VÉLØ Shadow Experiment Candidate Selection V1

## Overview
Based on the results of the shadow scoring experiments conducted against the 1,046-race Genesis replay, this document formalizes the selection of repair candidates for longer-term shadow observation and defines the current status of model selection repairs.

## Candidate Selection
The following overlays have been selected for extended shadow replay:

### 1. Primary Candidate: `calibration_cap_35`
- **Role**: PRIMARY_LONGER_SHADOW_REPLAY
- **Reason**: Provides significant Brier score improvement (-0.18) and eliminates high-confidence selection failures in the baseline dataset without being overly aggressive in probability suppression.
- **Note**: Improves probability honesty, not selection quality.

### 2. Stress Test Candidate: `calibration_cap_30`
- **Role**: SECONDARY_STRESS_TEST
- **Reason**: Achieved the best overall Brier score but carries a higher risk of inducing model underconfidence.

### 3. Risk-Control Candidate: `volatility_confidence_cap`
- **Role**: RISK_CONTROL_SHADOW_REPLAY
- **Reason**: Successfully suppresses overconfidence in large fields using field size as a proxy for environmental chaos.

## Selection Repair Status: NOT SOLVED
The experiments confirmed that while probability honesty (Brier Score) was materially improved, **the actual winner selection (Strike Rate) remained unchanged at 19.21%.** No easy winners were rescued in this phase.

## Blockers & Next Data Requirements
The "Easy Winner" rescue mission and "Chalk Sanity" repairs are currently blocked by a lack of granular market and ranking data in the historical Genesis source.

**Next Required Data Points**:
- Actual winner model rank
- Market rank (pre-race)
- Pre-race odds timestamps (for HFS validation)
- Definitive favourite identity
- Full field ranking snapshots

## Safety Mandate
**No production scoring changes are authorized.** All evolutionary work remains strictly confined to the shadow intelligence cycle.

---
*Authorized by VÉLØ Command Authority | Model Intelligence Division*

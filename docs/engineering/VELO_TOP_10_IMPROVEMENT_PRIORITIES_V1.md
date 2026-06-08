# VÉLØ TOP 10 IMPROVEMENT PRIORITIES V1

This document outlines the narrowed priority pool and hard constraints for the VÉLØ Oracle Prime roadmap.

## 1. Top 20 Promotion Pool

| Rank | Concept | Classification | Reason |
| :--- | :--- | :--- | :--- |
| 1 | Dashboards & Visual Feedback | TOP_10_ESSENTIAL | Foundation for operator confidence. |
| 2 | Sigma Loop / Outcome Honesty | TOP_10_ESSENTIAL | Essential for truth-based learning. |
| 3 | Sidecar ELO / Field Strength | TOP_10_ESSENTIAL | Critical for contextualizing raw ratings. |
| 4 | Bias-Variance Engine | TOP_10_ESSENTIAL | Required for reliable model calibration. |
| 5 | Markov Hidden-State Engine | TOP_10_ESSENTIAL | Enables intent-aware state tracking. |
| 6 | Latent Concept Learning | TOP_10_ESSENTIAL | Captures unmodeled domain signals. |
| 7 | Agentic RAG / Dossier Access | TOP_10_ESSENTIAL | Automates intelligence synthesis. |
| 8 | Graph Knowledge Map | TOP_10_ESSENTIAL | Tracks complex trainer/owner connections. |
| 9 | Calibration Baseline | TOP_10_ESSENTIAL | Anchors probabilities to reality. |
| 10 | Secure Agent Runtime / Harness | TOP_10_ESSENTIAL | Ensures safe autonomous execution. |
| 11 | Multi-Variate Decay | TOP_15_SUPPORT | Enhances form weighting precision. |
| 12 | Jockey Continuity Signals | TOP_15_SUPPORT | Proxies for intent and familiarity. |
| 13 | Surface/Going Specialist Map | TOP_15_SUPPORT | Required for high-precision filtering. |
| 14 | Post-Race Excuse Extraction | TOP_15_SUPPORT | Crucial for identifying concealed form. |
| 15 | Draw Advantage Heatmaps | TOP_15_SUPPORT | Essential for flat-racing edge cases. |

## 2. Top 10 Essential

**Dashboards & Visual Feedback:** Foundation for operator confidence. This isn't just about pretty UI; it's about surfacing the "why" behind the probability so the human operator can intervene effectively.

**Sigma Loop / Outcome Honesty:** Essential for truth-based learning. We cannot improve what we cannot measure honestly. The Sigma loop is the heartbeat of our closed-loop intelligence.

**Sidecar ELO / Field Strength:** Critical for contextualizing raw ratings. A 90 RPR at Epsom isn't the same as a 90 RPR at Southwell. ELO gives us the cross-venue normalization we've been missing.

**Bias-Variance Engine:** Required for reliable model calibration. This allows us to quantify the uncertainty of each prediction, identifying where the model is overconfident or under-informed.

**Markov Hidden-State Engine:** Enables intent-aware state tracking. Horses aren't static; they are in states of preparation or release. Markov modeling allows us to track these latent transitions over a campaign.

**Latent Concept Learning:** Captures unmodeled domain signals. This allows the system to identify patterns (like "The Drift Trap") that traditional linear features often miss.

**Agentic RAG / Dossier Access:** Automates intelligence synthesis. By giving agents direct access to historical dossiers and spotlights, we bridge the gap between structured data and expert intuition.

**Graph Knowledge Map:** Tracks complex trainer/owner connections. The racing world is a web of relationships. Graph mapping allows us to detect intent by observing stable patterns across stables.

**Calibration Baseline:** Anchors probabilities to reality. Without a baseline, "25%" is just a number. This ensures our predicted strike rates match empirical outcomes over thousands of samples.

**Secure Agent Runtime / Harness:** Ensures safe autonomous execution. As we move toward agentic operations, the harness provides the sandboxed environment and hard blocks required for system integrity.

## 3. Top 15 Close-Tie Support

**Multi-Variate Decay:** Enhances form weighting precision. Recognizes that not all historical runs decay at the same rate, depending on the venue and going.

**Jockey Continuity Signals:** Proxies for intent and familiarity. Tracks when a stable's go-to jockey is retained specifically for a cash run.

**Surface/Going Specialist Map:** Required for high-precision filtering. Identifies horses whose probability is strictly dependent on specific ground conditions.

**Post-Race Excuse Extraction:** Crucial for identifying concealed form. Automates the parsing of post-race reports to find "hidden" reasons for a poor finish.

**Draw Advantage Heatmaps:** Essential for flat-racing edge cases. Quantifies the statistical bias of starting stalls across different courses and distances.

## 4. Recommended Build Order

1. **Dashboard** (Visual feedback loop)
2. **Sigma** (Outcome honesty)
3. **Sidecar Elo** (Contextual field strength)
4. **Bias-Variance** (Uncertainty quantification)
5. **Markov** (State-tracking engine)
6. **Latent Concepts** (Unmodeled signal capture)
7. **Agentic RAG** (Intelligence synthesis)
8. **Graph Knowledge** (Relationship mapping)
9. **Calibration Baseline** (Ground-truth anchoring)
10. **Secure Agent Runtime/Harness** (Safe autonomous execution)

## 5. Hard Restrictions

```text
- No latent concept enters scoring without sidecar evaluation against closed outcomes
- No agent can mutate live scoring without explicit operator approval
- No graph/RAG evidence can override model output until closed-outcome validation
- No all-time JTC-D
- No RPR in morning model features
- No same-race SP in morning model features
- No promotion without closed outcomes
- No model claim from sample n<50
```

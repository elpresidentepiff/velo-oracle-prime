# Live Weight Contract Audit

- Audit date: `2026-05-08`
- Racecard source: `persisted_verdict_runtime_sample`
- Races traced: `49`
- Trace race: `None None | rac_11929346`

## Final Contract

| Signal | Declared weight | Passed into ensemble? | Non-null? | Changes VP? | Status |
|---|---:|---|---|---|---|
| sqpe_v17 | 0.45 | YES | YES | YES | LIVE_WEIGHTED |
| improvement_score | 0.12 | YES | YES | YES | LIVE_WEIGHTED |
| release_window_score | 0.0 | YES | YES | NO | LIVE_WEIGHTED |
| market_deception_score | 0.1 | YES | YES | YES | LIVE_WEIGHTED |
| place_prob | 0.08 | YES | YES | NO | LIVE_WEIGHTED |
| comment_intel_score | 0.0 | YES | YES | NO | LIVE_WEIGHTED |
| longshot_score | 0.07 | YES | YES | NO | DEFAULTED_ONLY |
| racing_api_enrichment_shadow_score |  | NO | NO | NO | SHADOW_ONLY |
| trainer/jockey/course/distance stats |  | NO | NO | NO | SHADOW_ONLY |

## Ablation Proof

| Component | Top before | Top after | Top prob delta | Max runner delta | Ranking changed |
|---|---|---|---:|---:|---|
| improvement_score | Illy's Roo | Illy's Roo | 0.035 | 0.035 | NO |
| release_window_score | Illy's Roo | Illy's Roo | 0.0 | 0.0 | NO |
| market_deception_score | Illy's Roo | Illy's Roo | 0.0022 | 0.0079 | NO |
| place_prob | Illy's Roo | Illy's Roo | 0.0 | 0.0 | NO |
| comment_intel_score | Illy's Roo | Illy's Roo | 0.0 | 0.0 | NO |
| longshot_score | Illy's Roo | Illy's Roo | 0.0 | 0.0 | NO |

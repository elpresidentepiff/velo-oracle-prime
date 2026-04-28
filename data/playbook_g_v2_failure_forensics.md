# Playbook G V2 Failure Forensics

- Final recommendation: `C` - run V3 ratings+doctrine-first experiment
- Core finding: `doctrine is alive, but raw market input degrades the full stack relative to ratings + doctrine`
- Market + ratings test log loss: `1.481647`
- Market + ratings + doctrine test log loss: `1.507078`
- Ratings + doctrine test log loss: `1.481028`

## Key Calls
- Market interference: `market raw input is too loud in the full stack`
- HK improvement: `HK improved because doctrine + ratings helped ranking without requiring raw market dominance`
- FR improvement: `FR remains the strongest regime for doctrine-enhanced models`
- 2025 instability: `2025 is still too small to anchor governance decisions on its own`
- Market as raw input: `test market as benchmark/calibration/residual, not as default raw feature in the core V3 model`
- Residual-learning V3 arm: `yes`

## Recommendation
V2 showed doctrine contributes real signal and fixes the HK failure, but the best overall log loss came from ratings + doctrine, not the raw full stack. The next clean experiment is to treat ratings + doctrine as the core and demote market to residual/calibration roles instead of feeding it blindly into the stack.

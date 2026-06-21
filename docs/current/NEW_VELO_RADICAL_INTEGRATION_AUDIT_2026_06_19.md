# NEW VELO RADICAL INTEGRATION AUDIT

**Date:** 2026-06-19  
**Status:** AUDIT_COMPLETE  
**Decision:** Integrate as a protected Radical Shadow lane. Do not create a disconnected new repo.

## Executive decision

The repo already contains the bones of the new Velo. The strongest path is not a fresh rewrite and not blind promotion of Old Velo. The right move is a strangler-integrated Radical Shadow lane that uses:

- New Build doctrine/passport scoring as the clean morning model.
- Sigma win/frame gates as the bet/pass and cash-run selector.
- Late market sidecars as a separate time-boxed lane.
- Harness and source-truth gates as the protection layer.
- VFU/Sigma learning as the feedback loop.

This keeps the current race-day system safe while letting the new architecture prove itself race by race.

## What already exists

| Asset | Classification | Use in new Velo |
|---|---|---|
| `data/raceform_v17_features.parquet` | TREASURE | 1.7M runner-row historical replay universe. Use for offline proof, not as a live leakage source. |
| `data/new_build/` | TREASURE | Clean ML lane with honest train/val/test discipline. This is the primary new-model foundation. |
| Horse passports | TREASURE | Memory layer. Best used with RP doctrine features, not alone. |
| `scripts/train/train_new_build_doctrine_passport_challenger.py` | NEW TREASURE | Shadow-only clean model: no RPR, no SP, no market leakage. |
| `scripts/audit/passport_sigma_training_test.py` | NEW TREASURE | Confirms RP doctrine + passport beats passport-only and uses no banned RPR/market fields. |
| `scripts/audit/radical_edge_discovery.py` | NEW TREASURE | Finds profitable and toxic execution regimes from Sigma history. |
| `models/radical_sigma_gate_staging/` | SHADOW TREASURE | Win/frame gates with strong AUC lift; not live yet. |
| JTC-D profile bank | HIGH-VALUE QUARANTINE | Huge signal, but all-time leakage risk. Rebuild lagged/date-bounded before use. |
| Market sidecars | LATE LANE ONLY | Strong signal but must never contaminate morning truth. |
| Harness / TaskContract / Sentinel | PROTECTION LAYER | Should guard new Velo work and race-day execution. |
| `RUN_PRIME_STRANGLER_PLAN.md` | OPERATING PATH | Safest route to integrate without breaking live scoring. |

## Evidence from latest tests

### Passport vs RP files

Latest clean holdout test:

| Model | AUC | Top-1 | Verdict |
|---|---:|---:|---|
| Passport only | 0.6362 | 24.71% | Useful, but not enough alone. |
| RP core no RPR/no market | 0.6870 | 24.82% | Better structure. |
| RP doctrine no ratings/no market | 0.6916 | 26.04% | Velo doctrine adds signal. |
| RP core + passport | 0.6989 | 26.09% | Passport helps. |
| RP doctrine + passport | 0.7018 | 26.90% | Best clean lane. |

Conclusion: New Velo should not be passport-only. It should be RP race-shape + Velo doctrine + passport memory.

### Sigma gate evidence

Latest innovation universe:

- Rows: 1,104
- Current unfiltered ROI: -7.29%
- Current unfiltered strike: 25.36%
- Current frame: 55.80%

Gate lift:

| Gate | Baseline AUC | Gate AUC | Best current use |
|---|---:|---:|---|
| Win gate | 0.5806 | 0.7494 | Bet/pass research gate. |
| Frame gate | 0.6641 | 0.7878 | Cash-run / acca / place-confidence gate. |

Best execution regimes found:

- Field size 6-8: n=338, SR 31.07%, frame 69.23%, ROI +13.73%.
- Class 4 and field size 6-8: n=242, SR 35.12%, frame 71.90%, ROI +12.38%.
- Class 4 and field size 2-5: n=72, SR 45.83%, frame 87.50%, ROI +9.94%.
- Router v1=1/v2=1/v6=0: n=80, SR 41.25%, frame 80.00%, ROI +3.04%.
- Odds 8-14 with field size 6-8: n=31, SR 16.13%, frame 48.39%, ROI +80.65%. Small sample, shadow only.

Toxic execution regimes:

- Field size 9-12: n=421, ROI -27.80%.
- Longshots 15+: n=133, ROI -26.32%.
- Class 5: n=132, ROI -41.06%.
- Class 5 and field size 9-12: n=63, ROI -74.56%.
- Longshots 15+ and field size 9-12: n=64, ROI -76.56%.

Conclusion: New Velo should stop trying to bet every race. It should score every race, then gate execution.

## Create or integrate?

Integrate. A separate new repo would repeat the same failure mode: good ideas living outside race-day truth. The correct structure is:

```text
src/velo/radical/
  feature_contract.py
  doctrine_passport_model.py
  sigma_gate.py
  regime_router.py
  sidecar_registry.py
  decision_packet.py

scripts/ops/run_radical_shadow_today.py
docs/current/NEW_VELO_RADICAL_ARCHITECTURE.md
tests/test_radical_*.py
```

The first command must be shadow-only. It should read the same race-day artifacts as Old/New Velo, write its own decision packet, and never mutate live verdicts.

## Promotion law

New Velo is not live until all of this is true:

1. It runs beside Old Velo for real race days.
2. It proves no RPR, no final SP, no market leakage in morning scoring.
3. It writes per-race pass/bet/cash-run reasons.
4. It beats Old Velo on the same settled result set after costs.
5. Harness confirms source truth, artifact presence, and no stale-data run.
6. LLM Council / Mission Control can inspect the decision packet without reading code.

## Quarantine list

Do not promote these into Radical Velo yet:

- RPR-heavy SQPE as the primary model.
- Final SP/implied probability in morning scoring.
- All-time JTC-D sidecars without date boundaries.
- International sidecars without current-era UK/IRE proof.
- Racing API enrichment.
- Any live write into `velo_verdicts` from Radical Shadow.

## First build slice

Build `run_radical_shadow_today.py` as a no-side-effect daily lane:

1. Load today racecard from RP truth artifacts.
2. Build RP doctrine features and passport features.
3. Score with the doctrine+passport shadow model.
4. Apply Sigma win and frame gates.
5. Apply regime router using field size, class, odds band, VP band, and course.
6. Attach sidecar observations only.
7. Write JSON + Markdown decision packet.
8. Dashboard reads the packet as `Radical Shadow`, not live picks.

## Final verdict

The gold is already in the repo. The new Velo should be a protected integration, not a fresh detached build.

**Name:** Radical Velo Shadow  
**Primary model:** RP doctrine + passport memory  
**Execution layer:** Sigma gate + regime router  
**Protection:** Harness + source truth + strangler plan  
**Status:** Build next, shadow-only.

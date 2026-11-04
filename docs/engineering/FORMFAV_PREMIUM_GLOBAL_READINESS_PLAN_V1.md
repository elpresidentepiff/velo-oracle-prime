# FormFav Premium + Velo Delivery Plan V1

**Effective:** 2026-11-04

**Mode:** PAPER/SHADOW only

**Contract:** `FORMFAV-PREMIUM-RERUN-01`

## Verified starting point

- Premium market capture is active across GB, IE, FR and HK in the observed window.
- The governed 2026-11-04 FormFav gate covered 47 races and 531 runners; all 47 races had form and predictions.
- Prime's frozen 07:27 UTC scoring batch remains canonical: 47 races, 533 runners, 1,931 canonical model rows.
- The first repeat run exposed schema drift in `runner_prediction_snapshots` and stopped at Old Velo rather than inventing missing data.
- The additive schema repair is applied. A recovery batch reconstructed 533 runner rows across 47 races from the frozen verdict without rescoring or modifying Prime.

## Daily operating sequence

1. FormFav card/form/prediction readiness.
2. RP HTML canonical GB/IE capture and parse.
3. Prime scoring and complete runner snapshot persistence.
4. Read-back proof: hydrate the latest snapshot batch from Supabase in a clean-container-compatible format.
5. Old Velo, No-RPR, New Build, Champion Intent and established paper/shadow lanes.
6. Dashboard publication with actual artifact status; never render a missing lane as complete.
7. Premium price checkpoints at T-120, T-60, T-30, T-10, T-5, T-1 and last pre-off where available.
8. EOD results, Sigma, multi-model scorecard, Mission Control, Council, final Mission Control refresh and learning gates.

## Premium evidence contract

- Preserve provider race ID, runner identity, bookmaker, market type, capture time and scheduled off time.
- Keep opening/high/low/current price, best win/place, bookmaker count, FormFav fair probability, consensus, edge and market rank.
- Never use post-off evidence in a pre-race evaluation.
- Never collapse missing into zero.
- FormFav prediction is an independent challenger, not an ordinary Prime feature.
- Market blends are sensitivity probes until strict forward settlement proves value.

## Change tracking

Every shadow comparison records:

- frozen Prime generation timestamp;
- FormFav prediction timestamp;
- Premium market capture minute;
- runner identity coverage;
- original Prime top pick;
- candidate top pick at 10%, 20% and 30% evidence sensitivity;
- the first pre-off minute at which a market-enhanced candidate changes the top pick.

The 2026-11-04 first pass found 47 matched races, 9 Prime/FormFav top-pick agreements, and 24 races with usable pre-off Premium prices. FormFav-model sensitivity changed 5 top picks at 10% evidence and 6 at 20-30%. Premium prices changed 2 top picks at 10-20% and 3 at 30%. These are change counts, not proof of improvement.

## Promotion gates

1. Identity match coverage and timestamp validity pass.
2. At least 100 strictly forward settled races per jurisdictional lane.
3. Same-race comparison against frozen Prime and captured market favourite.
4. Calibration, log loss, Brier score, strike rate, frame rate and captured-price ROI reported with uncertainty.
5. No result leakage, no post-off feature, no retrospective price substitution.
6. Tribunal review and explicit operator approval.
7. Until all gates pass: PAPER/SHADOW only, no production weight or execution change.

## Global preparation

- Maintain jurisdiction-specific calibration for GB/IE, FR, HK, JP, AU/NZ and North America.
- Normalize local race date, UTC off time, surface, race code, course and reschedules.
- Fix the observed US provider/local-date mismatch before treating US absences as real missing data.
- Do not reuse UK/IE calibration globally without forward evidence.

## Current next actions

1. Deploy the snapshot recovery/read-back repair.
2. Rerun 2026-11-04 in a clean Railway container and verify every model plus dashboard publication.
3. Settle the 2026-11-04 shadow ablation after official results.
4. Repeat daily without changing Prime.
5. Add the Premium market lane to the dashboard only after its artifact contract is stable.

## Contract closeout classifications

- `RUNNER_SNAPSHOT_PERSISTENCE_REPAIRED`
- `IDEMPOTENT_RERUN_HYDRATION_REPAIRED`
- `FORMFAV_PREMIUM_ABLATION_SHADOW_ONLY`
- `PREDICTION_CHANGE_TIMESTAMPED`
- `NO_LIVE_SCORING_CHANGE`
- `NO_MODEL_WEIGHT_CHANGE`
- `NO_GATE_BYPASS`
- `NO_TELEGRAM_SEND`
- `NO_MODEL_PROMOTION`
- `PAPER_SIM_ONLY`

The governed test command itself is `NO_SUPABASE_WRITES`; the separately
authorised operational migration and frozen-verdict recovery are documented
above and were verified directly before deployment.

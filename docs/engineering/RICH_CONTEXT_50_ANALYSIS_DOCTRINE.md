# Rich Context: how the challenger must read 50+ features

Status: design contract; NOT a trained model, NOT a live betting signal.

## Feature families (all observed pre-off, each with provenance, timestamp, sample size and missingness)
1. Identity and card: canonical race/horse/trainer/jockey IDs, off time, class, field size, surface, distance, going, weight, draw.
2. Horse capability: structured last 3/5/10/20 runs, beaten lengths, finishing speed if observed, course/distance/going history, days off, fitness cycle.
3. Handicap geometry: current OR, last winning OR, best winning OR, OR trajectory, class changes, weight changes, out-of-handicap, comparison with opponents.
4. Pace and position: FormFav speed map, observed run style, early speed, settling, race pace pressure, draw bias with sample size.
5. Connections: trainer recent form, trainer/horse placement history, trainer-jockey pair history, booking changes, yard patterns by layoff/class/mark, historical reliability.
6. Intent/context: RP Spotlight and postdata, headgear, surgery, new stable, race targeting, prior educational run language, prior run narratives, market evidence and counter-evidence.
7. Market: pre-off price snapshots, liquidity/quality, movement relative to horse and field, independent of provider predictions.

## Analytical doctrine: evidence not folklore
- Score capability, readiness, race fit, and *apparent* intent separately. No claim to know private stable intentions.
- Handicap 'plot' requires current OR vs actual prior winning OR, similar race conditions, a plausible performance trajectory, and trainer-specific corroboration. Low OR alone is not proof.
- 'Stretch the legs' / preparatory run is a hypothesis only: require layoff/fitness sequence + race commentary + later-run pattern; never infer intent solely from beaten lengths.
- Jockey switch alone is neutral. Estimate improvement from comparable historic bookings, trainer-jockey pair records, claims, and context; shrink small samples.
- Trainer recent win rate is form, NOT intention. Estimate intent patterns only from time-safe historical training examples.
- Contradictions lower confidence. Missing data remains missing; defaults are marked imputed and excluded from evidence claims.
- FormFav provider probabilities and selections are kept separate from factual features to prevent circular model evaluation.
- No data after the race off may be used in a pre-race prediction. Identity must match canonical IDs and snapshots must be immutable.
- Rank all runners using an independently trained, calibrated model; show Top 3, score/probability only if calibrated, coverage and top supporting/opposing signals.
- Compare chronological holdout results with Prime and market baselines: log loss, Brier, calibration, rank hit rate, ROI only with realistic prices/costs and sample sizes.
- Shadow-only until predeclared performance, leakage, and data quality gates pass.

## Operator dashboard acceptance criteria
- All races and runners present, with explicit errors for missing records.
- Every feature shows observed / missing / imputed / invalid and source.
- Show 50+ **eligible analytical** features separately from metadata and presence flags.
- Display independent challenger Top 3 only after a model and valid score artifact exist. Otherwise display NO TRAINED PREDICTION, not a guessed rank.
- Show Prime vs challenger disagreement, trainer/jockey/horse intent evidence, handicap/pace/prep hypotheses and confidence.
- Preserve existing Prime decisions and staking boundaries.

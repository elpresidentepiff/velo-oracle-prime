# VÉLØ + FormFav UK Enhancement Plan V1

Status: **build prepared; shadow-only**
Primary market: **Great Britain first; Ireland second**.
Production rule: **no new FormFav feature changes VÉLØ Prime until it wins chronological out-of-sample ablation.**

## Why UK first

VÉLØ's strongest existing training, doctrine, Racing Post capture/merged cards, BHA context, RP history and specialist models are UK-centric. FormFav is therefore used first as a second-source feature expansion on races VÉLØ already understands.

The US experiment proved two rules: cross-jurisdiction transfer without calibration is unsafe; and provider history/completeness must be quality-gated before it is trusted.

## Current GB coverage observed for 2026-10-12

| Feature block | Coverage |
|---|---:|
| Form string | 93.2% |
| Overall career stats | 93.2% |
| Conditions stats | 93.2% |
| First-up stats | 93.2% |
| Class profile | 88.7% |
| Race class fit | 88.7% |
| Barrier/draw | 85.6% |
| Second-up stats | 84.0% |
| Form decorators | 82.2% |
| Speed map | 72.8% |
| Track stats | 53.1% |
| Distance stats | 35.9% |
| Track+distance stats | 21.5% |

Ireland currently has useful form/speed/class-profile coverage but much weaker class-fit and distance-context coverage, so GB is the first promotion target.

## Source architecture

The canonical Racing Post capture/injection/merged-card pipeline, plus BHA and VÉLØ history, remains source truth. FormFav is attached under source-specific fields with raw payload, timestamp, sample size and conflict flags. Disagreement is recorded; nothing is silently overwritten.

## Lane 1 — Pace / speed map

Inputs: runningStyle L/P/M/B/X, earlySpeedIndex 0-10, settlingPosition, and race paceScenario SLOW/MODERATE/FAST/VERY_FAST.

Shadow features: style one-hot, normalised early speed, settling percentile, leader/presser/high-speed counts, pace-shape-fit hint, and later draw x pace interactions.

## Lane 2 — Form map

Inputs: form, last20Starts, overall/track/distance/trackDistance/condition records, first-up and second-up records.

Every strike rate keeps its starts denominator. Context rates are shrunk toward conservative priors so 1/1 never masquerades as a stable 100% edge.

## Lane 3 — Class map

Inputs: current class, peak class, highest class won, optimal range, rising/stable/dropping trend, raceClassFit difference and assessment.

These are compared with VÉLØ's existing race_class, OR trajectory and improvement signals; disagreement becomes a feature.

## Lane 4 — Track / draw map

FormFav Pro supplies distance-specific barrier bias. VÉLØ requests the exact race distance with a 90-day rolling window and stores barrier starts, wins, places, advantage, strongest/weakest draw and bias strength.

Derived features use sample-size shrinkage and can later interact with speed-map position. This is deliberately stronger than treating raw draw number as universally meaningful.

## Lane 5 — Conditions / surface

Current going remains canonical. FormFav condition history is contextual evidence with explicit sample sizes and separate source provenance.

## Lane 6 — Connections

VÉLØ already owns strong UK trainer/jockey history. FormFav jockey/trainer-at-track signals are independent corroboration, not replacements.

## Lane 7 — Premium market

When Premium is enabled: current win/place quotes, open/high/low/close, movement history, bookmaker count and freshness enter a separate market lane. Live price, bookmaker SP, official SP and close remain distinct fields.

## Data-quality gate

Each runner gets identity-name match, draw conflict, quality score, quality tier and training eligibility. Missing data remains missing. Identity failures or unresolved source conflicts make a row ineligible for training.

## No double counting

Form badges are summaries of underlying evidence, so they start as diagnostics only. FormFav prediction probability is a challenger/meta lane, not a core feature. We do not count the same track/class/form fact two or three times.

## Evaluation

Ablations: BASELINE, +PACE, +FORM, +CLASS, +TRACK/DRAW, +CONDITIONS, +CONNECTION CROSS-CHECK, +MARKET, then FULL ENRICHED.

Measure winner/top2/top3, log loss, Brier score, probability calibration, ROI, rank correlation, and performance splits by course, distance, going, class, field size, handicap/non-handicap, flat/AW/jumps and price band.

## Promotion gate

A lane is promoted only with a minimum sample, chronological holdout lift, clean identity/provenance, acceptable calibration, robustness across relevant race splits, no outlier-only ROI, versioned feature schema and an immediate rollback to existing Prime.

## Implemented now

- FormFav distance-scoped track-bias client
- race-level paceScenario preservation
- 90-day exact-distance trackBias enrichment
- FORMFAV_UK_SHADOW_V1 feature extractor
- sample-size shrinkage
- identity/draw conflict checks
- quality score/training eligibility
- UK enhanced shadow-card builder
- durable formfav_uk_shadow_features report registration

Production VÉLØ Prime does **not** consume these new fields yet. The UK shadow builder now loads the same `rp_merged` cards used by `run_prime_today.py --source rp`; Racing API is not part of this UK live path.

## Next sequence

1. Validate tomorrow's GB shadow card and track-bias endpoint.
2. Backfill prior GB dates within provider rate limits.
3. Join pre-race snapshots to settled UK results.
4. Produce coverage and provider-disagreement reports.
5. Train separate pace/form/class/track challengers.
6. Run rolling chronological ablations.
7. Promote only proven lanes into Enhanced VÉLØ.
8. Add Premium market lane after live-price access is active.
9. Run old Prime and Enhanced VÉLØ side-by-side through rollout.
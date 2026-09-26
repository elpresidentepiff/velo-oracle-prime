# Velo Oracle Prime Forecasting Laboratory — 2026-09-26

## Scope and safety

- Analysis only; no live scoring, model weights, gates, Supabase rows, Telegram delivery, or canonical live/shadow state changed.
- Common historical corpus: 2,245 evaluated races from 2026-05-21 through 2026-09-24.
- Chronological blocks: train 1,027 races (through 2026-06-30), calibration 623 races (2026-07-05 through 2026-08-03), untouched test 595 races (2026-08-04 through 2026-09-24).
- All choices were fitted on train, locked on calibration, and opened once on the final holdout.

## Executive readout

1. **Calibrate Prime's probabilities.** A fixed temperature/power transform with beta 0.43 preserved every top-pick decision but reduced holdout log loss from 2.3884 to 2.1223, Brier from 0.9029 to 0.8522, and ECE from 0.0463 to 0.0084. The bootstrap interval for log-loss improvement was entirely favorable (-0.3305 to -0.2053).
2. **Do not promote Playbook G as a selector.** Across 2,245 races it changed only 28 picks (1.2%). The adjustment modestly improved proper scores but did not establish a top-pick or ROI edge. Status: INSUFFICIENT_PICK_CHANGES.
3. **The mechanism evidence rejects improvement_score as presently constructed.** SQPE + improvement underperformed SQPE alone and SQPE + MDS. In every core pairwise fit, improvement_score received a negative coefficient.
4. **SQPE + MDS is the strongest reconstructed subset, not a proven production replacement.** It improved holdout Brier and winner ranking versus stored G, with its clearest relative gains in 12+ runner fields. Top-pick and ROI bootstrap intervals still crossed zero.
5. **The market-blind core ranker contains ranking signal but not value evidence.** It lifted holdout top-1 accuracy from 23.19% to 25.38% and pairwise accuracy from 64.80% to 66.03%, while ROI worsened from -20.00% to -26.15%. Status: PARTIAL_RANKING_LIFT_NOT_PROMOTABLE.
6. **Late market remains champion.** On the same 595-race holdout, market top-1 accuracy was 30.08%, log loss 1.9831, Brier 0.8144, and ECE 0.0061. A model-market blend slightly raised top-1 to 30.25% but worsened proper scores, so the locked selection remained the late market alone.

## Untouched holdout comparison

| Track | Top-1 | Top-3 | Log loss | Brier | ROI | ECE |
|---|---:|---:|---:|---:|---:|---:|
| Raw stored base | 23.19% | — | 2.3884 | 0.9029 | -20.00% | 0.0463 |
| Temperature-calibrated stored G | 23.19% | 52.77% | 2.1223 | 0.8522 | -20.00% | 0.0084 |
| SQPE only | 23.53% | 53.11% | 2.1552 | 0.8511 | -18.69% | — |
| SQPE + MDS | 23.36% | 52.94% | 2.1162 | 0.8501 | -19.48% | — |
| Market-blind core pairwise ranker | 25.38% | 54.96% | 2.1317 | 0.8503 | -26.15% | — |
| Late pre-off market | 30.08% | — | 1.9831 | 0.8144 | -12.60% | 0.0061 |

## Playbook G benchmark

- 2,245 races and 22,203 runners.
- Base: 25.48% top-1, 54.65% top-3, -12.31% ROI.
- G: 25.66% top-1, 55.32% top-3, -11.78% ROI.
- Only 28 top-pick changes.
- Bootstrap top-1 delta: -0.04 to +0.40 percentage points.
- Bootstrap ROI delta: -0.77 to +1.71 percentage points.
- G's log-loss improvement was small but consistent; its ranking and ROI improvement was not proven.
- Raw Base and G proper scores were worse than uniform field probabilities before temperature correction, confirming severe overconfidence rather than lack of all ranking signal.

## Calibration challenger

- Locked beta for Base and G: 0.43.
- Raw Base -> calibrated G holdout:
  - top-1 unchanged: 23.19%.
  - log loss: 2.3884 -> 2.1223.
  - Brier: 0.9029 -> 0.8522.
  - ECE: 0.0463 -> 0.0084.
  - ROI unchanged: -20.00%.
- Calibration fixes probability honesty; it does not fix selection quality or economic value.

## Component mechanism ablation

- Locked variant: SQPE + MDS.
- Stored G -> SQPE + MDS:
  - top-1: 23.19% -> 23.36%.
  - top-3: 52.77% -> 52.94%.
  - log loss: 2.1223 -> 2.1162.
  - Brier: 0.8522 -> 0.8501.
  - mean winner rank: 4.24 -> 4.19.
  - pairwise winner accuracy: 64.80% -> 65.22%.
  - ROI: -20.00% -> -19.48%.
- Only Brier improvement had an entirely favorable 95% interval; other outcome deltas remain uncertain.
- On 326 model-v-market disagreements, model won 42 and market won 82.
- In large fields (12+), SQPE + MDS improved top-1 from 17.82% to 18.32% and ROI from -14.46% to -12.32%, but still trailed the market heavily on disagreement races.

## Market-blind pairwise ranker

- Locked variant: core features, C=0.1, gamma=0.64.
- Features: SQPE, improvement score, MDS; no odds, favourite flag, identity, or result-derived feature.
- Coefficients: SQPE +1.83, improvement -2.54, MDS +13.39.
- Stored G -> selected ranker:
  - top-1: 23.19% -> 25.38%.
  - top-3: 52.77% -> 54.96%.
  - pairwise accuracy: 64.80% -> 66.03%.
  - ROI: -20.00% -> -26.15%.
- Top-1 bootstrap interval ranged from 0.00 to +4.37 percentage points; proper-score and ROI intervals crossed zero.
- Expanded features performed worse, while NDS had only 22.4% training coverage and spotlight 63.1%, making the expanded coefficients unstable and unsuitable for interpretation.

## Controlled next step

Do not alter production weights. The evidence supports three forward, shadow-only actions subject to an explicit implementation plan and normal gates:

1. Apply beta 0.43 only to reported/calibration probabilities in a new shadow lane, preserving rankings, and evaluate ECE/log loss prospectively.
2. Add a daily market-blind core-ranker shadow prediction so it can accumulate independent disagreement evidence and settled ROI without retroactive fitting.
3. Add an SQPE+MDS mechanism shadow lane distinct from the existing 90%-MDS lane, and track it through the disagreement audit.

The current improvement_score should remain in production unchanged until a governed decision is made, but new research lanes should exclude it because both ablation and pairwise learning independently indicate negative contribution.

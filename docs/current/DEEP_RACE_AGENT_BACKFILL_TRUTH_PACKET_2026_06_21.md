# Deep Race Agent Backfill Truth Packet

Generated: 2026-06-21

## Contract

- Racing API used: **no**
- Source truth: RP HTML-derived local files and RP result JSON only.
- Scope: UK/IRE only. Known non-UK/IRE cards were excluded from the backfill.
- Status: paper-only. Nothing here is live staking law until Sigma/Mission Control accepts it.

## Backfill Files

- Agent report: `data/reports/deep_race_agent_v1_2026_06_01_to_2026_06_20_v2.json`
- Agent markdown: `data/reports/deep_race_agent_v1_2026_06_01_to_2026_06_20_v2.md`
- Evaluation report: `data/reports/deep_race_agent_v1_eval_2026_06_01_to_2026_06_20_v2.json`
- Evaluation markdown: `data/reports/deep_race_agent_v1_eval_2026_06_01_to_2026_06_20_v2.md`
- June 21 live-day agent report: `data/reports/deep_race_agent_v1_2026_06_21_v2.json`

## Backfill Coverage

- Raw review cards: 720
- UK/IRE review cards retained: 703
- Non-UK/IRE cards excluded: 17
- RP live identity files loaded: 112
- RP live identity runners loaded: 7,699
- Result files loaded: 20
- Result races loaded: 786
- Evaluated selections: 495
- Identity misses: 151
- Missing result rows: 63
- Non-runners: 11

## Overall Result

Blind £10 win staking across every evaluated Deep Race Agent card is not enough.

- Wins: 172 / 495
- Strike rate: 34.75%
- Frames: 328 / 495
- Frame rate: 66.26%
- Win P/L: -£428.00
- ROI: -8.65%

Conclusion: the agent has signal, but must be narrowed.

## Positive Verdict Buckets

Only two verdict buckets are positive in the backfill:

| Verdict | N | Wins | Frames | SR | Frame | P/L | ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| CASH_RUN_REVIEW | 114 | 49 | 89 | 42.98% | 78.07% | +£154.60 | +13.56% |
| UPGRADE_CANDIDATE_REVIEW | 109 | 41 | 72 | 37.61% | 66.06% | +£241.00 | +22.11% |

Negative buckets:

| Verdict | ROI |
|---|---:|
| NO_BET | -30.44% |
| WATCH_ONLY | -26.98% |
| PASS_WITH_SUPPORT_REVIEW | -36.09% |

Rule: do not let `WATCH_ONLY`, `NO_BET`, or `PASS_WITH_SUPPORT_REVIEW` near staking.

## Strongest Combinations

| Combination | N | SR | Frame | P/L | ROI |
|---|---:|---:|---:|---:|---:|
| CASH_RUN_REVIEW + LIVE_CONFIRMED | 61 | 37.7% | 75.4% | +£176.60 | +29.0% |
| UPGRADE_CANDIDATE_REVIEW + STRONG | 25 | 44.0% | 64.0% | +£66.80 | +26.7% |
| UPGRADE_CANDIDATE_REVIEW + TRI_WATCH | 109 | 37.6% | 66.1% | +£241.00 | +22.1% |
| CASH_RUN_REVIEW + TRI_CASH_RUN | 114 | 43.0% | 78.1% | +£154.60 | +13.6% |

First candidate staking gate:

- Include `CASH_RUN_REVIEW` only when identity is `LIVE_CONFIRMED`.
- Include `UPGRADE_CANDIDATE_REVIEW` only as an analyst upgrade, with preference for `STRONG` identity.
- Exclude `LIVE_CONFLICT`.
- Exclude all non-UK/IRE.
- Keep this paper-only until daily forward results prove it.

## Track Signal

Positive tracks with at least 8 evaluated selections:

| Track | N | SR | Frame | ROI |
|---|---:|---:|---:|---:|
| Leicester | 11 | 45.45% | 81.82% | +134.64% |
| Ffos Las | 10 | 50.00% | 90.00% | +67.00% |
| Nottingham | 13 | 38.46% | 76.92% | +53.85% |
| Market Rasen | 12 | 33.33% | 91.67% | +53.67% |
| Wolverhampton (AW) | 10 | 50.00% | 80.00% | +49.10% |
| Hexham | 13 | 46.15% | 69.23% | +25.23% |
| Worcester | 18 | 44.44% | 77.78% | +21.44% |
| Uttoxeter | 11 | 63.64% | 90.91% | +20.82% |
| Newmarket (July) | 14 | 42.86% | 71.43% | +15.21% |
| Redcar | 8 | 50.00% | 62.50% | +10.50% |

Poor tracks with at least 8 evaluated selections:

| Track | ROI |
|---|---:|
| Epsom | -100.00% |
| Thirsk | -100.00% |
| Bath | -87.64% |
| Fairyhouse | -69.44% |
| Down Royal | -60.00% |
| Ayr | -57.09% |
| Doncaster | -56.42% |
| Leopardstown | -52.27% |
| Limerick | -52.00% |
| Chepstow | -50.00% |
| Goodwood | -48.67% |

Track rule candidate:

- Promote positive-track evidence as support, not automatic staking.
- Treat poor-track evidence as a suppressor unless a stronger edge gate overrides it.
- Irish data remains mixed: Downpatrick was near flat, but Fairyhouse, Down Royal, Leopardstown and Limerick were poor in this sample.

## Dangerous False Friends

- `TRI_WATCH_STRONG` sounds good but was negative: ROI -25.32%.
- `PASS_WITH_SUPPORT_REVIEW` was negative: ROI -36.09%.
- `LIVE_ONLY` had good strike/frame but negative ROI, so identity alone does not justify staking.
- Some result rows still have identity misses from older mixed-source cards; do not use those for promotion.

## Next Implementation Step

Build a paper-only dashboard/mission-control panel called `Deep Agent Gate`:

- Green: `CASH_RUN_REVIEW + LIVE_CONFIRMED`
- Amber: `UPGRADE_CANDIDATE_REVIEW + STRONG`
- Suppress: `LIVE_CONFLICT`, non-UK/IRE, `PASS_WITH_SUPPORT_REVIEW`, `WATCH_ONLY`, `NO_BET`
- Track support: add positive-track boost and poor-track warning from this packet.
- No live staking until the gate is replayed and forward-tested through Sigma.

# VFU-22: Filtered EW Analysis — Operator Brief

Generated: 2026-06-18T00:30:05.073163+00:00

## CRITICAL: Look-Ahead Contamination Warning

Several dual-lane labels (`WIN_LANE_CONFIRMED`, `PLACE_LANE_CONFIRMED`, `FALSE_WIN_SIGNAL`,
`PLACE_SIGNAL_WIN_OUTCOME`) **encode the race outcome in their definition**.

- `WIN_LANE_CONFIRMED` SR=100% because only winning predictions receive this label post-race.
- `PLACE_SIGNAL_WIN_OUTCOME` SR=100% because every row in this bucket IS a win by definition.

These segments appear profitable but their ROI figures are **meaningless for prospective staking**.
They are struck through in the table below and excluded from recommendations.

## All Segment Results (1-unit EW stake per bet)

| Segment | n (SP) | SR | Frame | ROI | Verdict |
|---|---|---|---|---|---|
| ALL_ROWS (baseline) | 2633 | 27.2% | 50.6% | -11.0% | **LOSS** |
| VP >= 0.30 | 783 | 35.8% | 58.2% | -3.3% | **LOSS** |
| VP >= 0.40 | 386 | 42.5% | 64.2% | +3.4% | **PROFITABLE** |
| VP >= 0.60 | 82 | 48.8% | 73.2% | +0.6% | **PROFITABLE** |
| VP 0.20-0.30 | 520 | 22.7% | 44.8% | -23.1% | **LOSS** |
| VP 0.30-0.40 | 397 | 29.2% | 52.4% | -9.7% | **LOSS** |
| VP 0.40-0.60 | 304 | 40.8% | 61.8% | +4.1% | **PROFITABLE** |
| ~~WIN_LANE_CONFIRMED~~ | 164 | 100.0% | 100.0% | +97.1% | ~~PROFITABLE (CONTAMINATED)~~ |
| ~~WIN_LANE + VP>=0.30~~ | 164 | 100.0% | 100.0% | +97.1% | ~~PROFITABLE (CONTAMINATED)~~ |
| ~~WIN_LANE + VP>=0.40~~ | 164 | 100.0% | 100.0% | +97.1% | ~~PROFITABLE (CONTAMINATED)~~ |
| ~~PLACE_LANE_CONFIRMED~~ | 136 | 0.0% | 100.0% | -37.3% | ~~LOSS (CONTAMINATED)~~ |
| ~~PLACE_LANE + VP>=0.30~~ | 28 | 0.0% | 100.0% | -31.8% | ~~LOSS (CONTAMINATED)~~ |
| ~~PLACE_LANE + VP>=0.40~~ | 0 | None% | None% | n/a | ~~LOSS (CONTAMINATED)~~ |
| ~~FALSE_WIN_SIGNAL~~ | 144 | 0.0% | 9.0% | -92.7% | ~~LOSS (CONTAMINATED)~~ |
| ~~PLACE_SIGNAL_WIN_OUTCOME~~ | 220 | 100.0% | 100.0% | +133.5% | ~~PROFITABLE (CONTAMINATED)~~ |
| EACH_WAY_REVIEW | 44 | 0.0% | 100.0% | +34.5% | **PROFITABLE** |
| PLACE_SPECIALIST | 51 | 0.0% | 76.5% | -52.1% | **LOSS** |

## Prospective Profitable Segments (n ≥ 30, look-ahead free)

- **VP >= 0.40**: ROI=+3.4%  n=386  SR=42.5%  Frame=64.2%
- **VP >= 0.60**: ROI=+0.6%  n=82  SR=48.8%  Frame=73.2%
- **VP 0.40-0.60**: ROI=+4.1%  n=304  SR=40.8%  Frame=61.8%
- **EACH_WAY_REVIEW**: ROI=+34.5%  n=44  SR=0.0%  Frame=100.0%

## Contaminated Segments (EXCLUDED)

- ~~WIN_LANE_CONFIRMED~~: Apparent ROI=+97.1% — SR=100.0% by construction (outcome encoded in label)
- ~~WIN_LANE + VP>=0.30~~: Apparent ROI=+97.1% — SR=100.0% by construction (outcome encoded in label)
- ~~WIN_LANE + VP>=0.40~~: Apparent ROI=+97.1% — SR=100.0% by construction (outcome encoded in label)
- ~~PLACE_SIGNAL_WIN_OUTCOME~~: Apparent ROI=+133.5% — SR=100.0% by construction (outcome encoded in label)

## Prospective Tagging

The **prospective** profitable segments above will be tagged on live predictions going forward.
VP >= 0.40 is the primary candidate (n=386, ROI=+3.4%, consistent with the Unified Evidence Audit finding).
EACH_WAY_REVIEW (n=44, ROI=+34.5%) warrants tracking to build sample size.

## Governance

- `blocked_from_live_use = True`
- NO VP threshold change
- NO model change
- NO live staking — prospective tags are for tracking only
- Operator must authorise live staking separately (VFU-23+)

## STOP

STOP — operator review required before VFU-23 (live staking authorisation).

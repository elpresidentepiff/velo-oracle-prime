# CONFIDENCE_FLOOD_DIAGNOSTIC.md

**Status:** ACTIVE, RETROSPECTIVE_ONLY (VFU-23)
**Script:** `scripts/ops/build_confidence_flood_diagnostic.py`
**Tests:** `tests/test_confidence_flood_diagnostic.py`
**Evidence report:** `data/reports/vfu_23_confidence_flood_retrospective_diagnostic.md`
**Origin:** VFU-22 (`data/reports/vfu_22_false_green_feature_autopsy.md`) identified the
`CONFIDENCE_FLOOD_FALSE_GREEN` pattern. VFU-23 turns it into a repeatable, tested diagnostic.

## What this is

A post-Sigma diagnostic that reads existing `data/sigma_results/sigma_results_*.json`
artifacts and reports, per date, whether the VP Gatekeeper's GREEN/AMBER/RED
classification that day showed signs of a "confidence flood" — VP elevated broadly
across the field without the model actually discriminating that day's winners from
losers.

**This is retrospective only.** It requires Sigma to have already closed (i.e. results
must exist) and therefore cannot run pre-race and cannot inform same-day staking or
scoring decisions. It does not read or write anything in the live scoring path.

## Fields produced per date

| Field | Meaning |
|---|---|
| `date` | Race date |
| `sigma_status` | Copied from the source `sigma_results_*.json` (`PASS` / `PARTIAL_RESULTS_DIAGNOSTIC_ONLY` / etc.) |
| `n_races` | Row count in the source file |
| `day_sr` | That day's actual strike rate (`sr` field) |
| `avg_vp` | Mean `velo_prime_prob` across all rows |
| `n_vp_ge_040` / `n_vp_ge_045` | Count of picks at/above VP 0.40 / 0.45 |
| `vp_gate_class` | GREEN / AMBER / RED / UNCLASSIFIED — reproduced read-only from `docs/current/VP_GATEKEEPER_PROMOTION_V1.md` criteria (this diagnostic never writes back to that doctrine) |
| `avg_hit_prob` / `avg_miss_prob` | Mean VP among winning picks vs. losing picks that day (already present in source file) |
| `vp_discrimination_gap` | `avg_hit_prob - avg_miss_prob` |
| `gap_band` | `INVERTED` (<0) / `COMPRESSED` (0 to <0.05) / `WEAK` (0.05 to <0.08) / `HEALTHY` (>=0.08) / `UNKNOWN` (missing fields) |
| `confidence_flood_flag` | `True` when `vp_gate_class == GREEN` AND `gap_band in [INVERTED, COMPRESSED]` — a same-Sigma-close leading signal that does not require knowing `day_sr` |
| `false_green_confirmed` | `True` when `vp_gate_class == GREEN` AND `day_sr < 0.243` — ground truth, but only knowable after results land. **Never available pre-race. Never wire into the live gate.** |
| `notes` | Any data-quality caveats (e.g. lower-confidence sigma_status, missing fields) |

## Known limitation (see full report for detail)

`confidence_flood_flag` is a coarser proxy than `false_green_confirmed` — in the VFU-23
run against 31 available dates, it caught 4 of the 6 known false-green days and flagged
1 true-green day. It is a useful triage signal, not a substitute for the ground-truth
check. Do not treat a day as safe merely because `confidence_flood_flag` is `False`.

## How to run

```bash
PYTHONPATH=. python scripts/ops/build_confidence_flood_diagnostic.py \
  --out data/current/confidence_flood_diagnostic_latest.json
```

Add `--sigma-results-dir <path>` to point at a different corpus (e.g. after new dates
accumulate).

## What this explicitly does not do

- Does not change `docs/current/VP_GATEKEEPER_PROMOTION_V1.md` criteria or thresholds.
- Does not touch live scoring, `run_prime_today.py`, or `velo_prime_ensemble.py`.
- Does not write to Supabase.
- Does not send Telegram.
- Does not promote any model.
- Cannot run before Sigma closes for a given date.

## Next step

Any future mission to use `confidence_flood_flag` as a pre-race caution signal would
require a separate, explicitly operator-approved mission that changes the VP Gatekeeper
itself — out of scope for VFU-23 by task contract (`ops/task_contracts/VFU-23.json`
forbids `pre_race_gate_change` and `vp_gate_criteria_change`).

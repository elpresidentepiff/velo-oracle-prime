# CONFIDENCE_FLOOD_ROOT_CAUSE_SPLIT.md

**Status:** ACTIVE, PATHOLOGY CLASSIFICATION ONLY (VFU-24)
**Script:** `scripts/ops/build_confidence_flood_root_cause_split.py`
**Tests:** `tests/test_confidence_flood_root_cause_split.py`
**Evidence report:** `data/reports/vfu_24_confidence_flood_root_cause_split.md`
**Origin:** VFU-22 found `CONFIDENCE_FLOOD_FALSE_GREEN`; VFU-23 built a retrospective
diagnostic for it; VFU-24 splits the six confirmed false-green days into root-cause
subtypes, because two of them (2026-06-18, 2026-06-19) were false-green despite a
HEALTHY VP discrimination gap — proving the pattern is not one disease.

## What this is

A read-only script that imports `build_confidence_flood_diagnostic.run_diagnostic`
(VFU-23, unmodified) and adds: cohort share fields (`n_vp_ge_040_share`,
`n_vp_ge_045_share`), row-level fields not already in the VFU-23 output
(`winner_sp_median`, `miss_class_breakdown`, `high_conf_sr`, `frame_rate`), a
three-way cohort split (`FALSE_GREEN_DAYS` / `TRUE_GREEN_DAYS` / `NON_GREEN_DAYS`),
and a subtype classifier for the six known false-green days.

**This is pathology classification only.** It proposes no fix, no threshold change,
no VP Gatekeeper mutation.

## Subtypes

| Subtype | Trigger | Axis |
|---|---|---|
| `GAP_COLLAPSE_FALSE_GREEN` | `false_green_confirmed` AND `gap_band in [INVERTED, COMPRESSED]` | Primary (mutually exclusive with below) |
| `HEALTHY_GAP_FALSE_GREEN` | `false_green_confirmed` AND `gap_band == HEALTHY` | Primary |
| `THRESHOLD_FLOOD_FALSE_GREEN` | `n_vp_ge_040_share` or `n_vp_ge_045_share` is `ABOVE_TRUE_GREEN_P75` relative to the true-green cohort | Secondary |
| `MARKET_ENVIRONMENT_FALSE_GREEN` | `winner_sp_median` sits entirely outside the true-green cohort's min–max range (a genuine outlier, not just "different from the mean") | Secondary |
| `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` | `winner_sp_median` does not clear that outlier bar | Secondary (negative finding, disclosed rather than hidden) |
| `SAMPLE_CAPTURE_QUALITY_FALSE_GREEN` | `sigma_status != PASS`, or `avg_hit_prob`/`avg_miss_prob`/`day_sr`/`n_races` missing | Secondary |
| `UNRESOLVED_FALSE_GREEN` | `HEALTHY_GAP_FALSE_GREEN` primary with zero positive secondary subtype found | Secondary (honest fallback) |

Cohort-relative bands for threshold pressure (`ABOVE_TRUE_GREEN_P75` /
`ABOVE_TRUE_GREEN_MEDIAN` / `WITHIN_TRUE_GREEN_RANGE` / `BELOW_TRUE_GREEN_MEDIAN` /
`TRUE_GREEN_COHORT_INSUFFICIENT`) are computed from the true-green cohort's own
quartiles each run — never a fixed doctrine number, since the dispatch explicitly
forbade inventing one.

## Result on the current 31-date corpus

All 6 known false-green days classified, zero unexpected extras. Split: 4
`GAP_COLLAPSE_FALSE_GREEN` (06-09, 06-16, 06-23, 06-30), 2 `HEALTHY_GAP_FALSE_GREEN`
(06-18, 06-19). Both healthy-gap days carry `THRESHOLD_FLOOD_FALSE_GREEN` as a
secondary subtype. `SAMPLE_CAPTURE_QUALITY_FALSE_GREEN` and `UNRESOLVED_FALSE_GREEN`
did not fire for any of the six in this sample. Full table and cohort comparison:
`data/reports/vfu_24_confidence_flood_root_cause_split.md`.

## How to run

```bash
PYTHONPATH=. python scripts/ops/build_confidence_flood_root_cause_split.py \
  --out data/current/confidence_flood_root_cause_split_latest.json
```

## What this explicitly does not do

- Proposes no cure, no VP Gatekeeper threshold or criteria change.
- Does not touch live scoring, Supabase, Telegram, or model promotion.
- Does not modify `scripts/ops/build_confidence_flood_diagnostic.py` (VFU-23) — only
  imports and reuses its classification logic, so the two stay in sync by construction.

## Next step

Any mission to design an actual fix (e.g. a second gate criterion sensitive to
threshold-flood or gap collapse) is out of scope here and would need its own
operator-approved mission — VFU-24's task contract (`ops/task_contracts/VFU-24.json`)
explicitly forbids `cure_design`, `pre_race_gate_change`, and `vp_gate_criteria_change`.

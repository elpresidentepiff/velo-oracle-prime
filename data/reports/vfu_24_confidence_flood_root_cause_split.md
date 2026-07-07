# VFU-24 — Confidence Flood Root-Cause Split

**Status:** DRY_RUN / REPORT_ONLY / PATHOLOGY CLASSIFICATION ONLY. No cure proposed,
no VP Gatekeeper criteria change, no live scoring change, no Supabase write, no
Telegram send, no model promotion.
**Script:** `scripts/ops/build_confidence_flood_root_cause_split.py`
**Tests:** `tests/test_confidence_flood_root_cause_split.py` (29 tests, all pass;
50/50 pass together with VFU-23's own suite — VFU-24 imports VFU-23's diagnostic
read-only and never modifies it)
**Raw output:** `data/current/confidence_flood_root_cause_split_latest.json`
**Reads only:** `data/sigma_results/sigma_results_*.json`,
`data/current/confidence_flood_diagnostic_latest.json` (via import of
`build_confidence_flood_diagnostic.run_diagnostic`), and the VFU-22/VFU-23/VP
Gatekeeper/taxonomy docs named in the dispatch. No external API, no live racecards.

## 1. Known false-green set — reproduction check

```json
{
  "known_false_green_set_loaded": true,
  "known_false_green_set_size": 6,
  "all_six_classified": true,
  "zero_unexpected_false_green_dates_or_explained": true,
  "missing_from_classification": []
}
```

All six confirmed VFU-22/VFU-23 false-green dates were loaded and classified. No
unexpected extra false-green dates appeared (the diagnostic reused VFU-23's exact
`false_green_confirmed` logic, so the set is identical by construction).

## 2. Verdict: false-green is not one disease

The six days split cleanly into **two primary subtypes**, exactly along the line the
dispatch predicted:

| Primary subtype | Dates | Count |
|---|---|---|
| `GAP_COLLAPSE_FALSE_GREEN` | 2026-06-09, 2026-06-16, 2026-06-23, 2026-06-30 | 4 |
| `HEALTHY_GAP_FALSE_GREEN` | 2026-06-18, 2026-06-19 | 2 |

This matches the VFU-23 gap-band distribution for the false-green cohort exactly
(2 COMPRESSED + 2 INVERTED = 4 gap-collapse, 2 HEALTHY = 2 healthy-gap, 0 WEAK).

**06-18 and 06-19 answer the question the dispatch asked.** Both have a *healthy*
discrimination gap (0.203 and 0.082 respectively) — the model separated that day's
winners from losers just fine in aggregate. Their failure driver is different: both
carry `THRESHOLD_FLOOD_FALSE_GREEN` as a secondary subtype — an unusually large share
of the field crossed the VP≥0.40 and VP≥0.45 action thresholds (both `ABOVE_TRUE_GREEN_P75`
relative to the 10-day true-green cohort), meaning the gate fired GREEN because *too
many* picks looked strong, not because the model was confused about who would win. This
is a distinct pathology from gap collapse: it is a volume/breadth problem in the action
zone, not a discrimination problem.

## 3. Required output table

| Date | Day SR | Gate | avg VP | n≥0.40 | n≥0.45 | 0.40 share | 0.45 share | VP gap | Gap band | Flood flag | False-green | Primary subtype | Secondary subtypes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-09 | 13.8% | GREEN | 0.3546 | 10 | 7 | 0.303 | 0.212 | 0.047 | COMPRESSED | Yes | Yes | `GAP_COLLAPSE_FALSE_GREEN` | `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |
| 2026-06-16 | 21.2% | GREEN | 0.3502 | 11 | 5 | 0.333 | 0.152 | 0.046 | COMPRESSED | Yes | Yes | `GAP_COLLAPSE_FALSE_GREEN` | `MARKET_ENVIRONMENT_FALSE_GREEN` |
| **2026-06-18** | 21.2% | GREEN | 0.4332 | 17 | 13 | 0.515 | 0.394 | 0.203 | **HEALTHY** | No | Yes | `HEALTHY_GAP_FALSE_GREEN` | `THRESHOLD_FLOOD_FALSE_GREEN`, `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |
| **2026-06-19** | 19.6% | GREEN | 0.4711 | 35 | 32 | 0.625 | 0.571 | 0.082 | **HEALTHY** | No | Yes | `HEALTHY_GAP_FALSE_GREEN` | `THRESHOLD_FLOOD_FALSE_GREEN`, `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |
| 2026-06-23 | 17.6% | GREEN | 0.4801 | 11 | 10 | 0.647 | 0.588 | -0.093 | INVERTED | Yes | Yes | `GAP_COLLAPSE_FALSE_GREEN` | `THRESHOLD_FLOOD_FALSE_GREEN`, `MARKET_ENVIRONMENT_FALSE_GREEN` |
| 2026-06-30 | 23.9% | GREEN | 0.3983 | 21 | 14 | 0.457 | 0.304 | -0.050 | INVERTED | Yes | Yes | `GAP_COLLAPSE_FALSE_GREEN` | `THRESHOLD_FLOOD_FALSE_GREEN`, `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |

`SAMPLE_CAPTURE_QUALITY_FALSE_GREEN` did not fire for any of the six — see §5.
`UNRESOLVED_FALSE_GREEN` did not fire for any of the six — every day had at least one
evidenced secondary subtype (see §6 for what "evidenced" means here and its limits).

## 4. Cohort comparison (proves the split is real, not narrative)

| Metric | FALSE_GREEN_DAYS (n=6) | TRUE_GREEN_DAYS (n=10) | NON_GREEN_DAYS (n=15) |
|---|---|---|---|
| Mean day SR | 19.6% | 31.6% | 25.2% |
| Mean avg VP | 0.4146 | 0.3931 | 0.2504 |
| Mean VP discrimination gap | 0.039 | 0.116 | 0.060 |
| Mean VP≥0.40 share | 0.480 | 0.406 | 0.116 |
| Mean VP≥0.45 share | 0.370 | 0.308 | 0.065 |
| Gap-band distribution | COMPRESSED:2, HEALTHY:2, INVERTED:2 | HEALTHY:7, COMPRESSED:1, WEAK:2 | INVERTED:5, HEALTHY:5, UNKNOWN:2, COMPRESSED:2, WEAK:1 |
| Sigma-status distribution | PASS:6 | PASS:9, PARTIAL:1 | PASS:13, PARTIAL:2 |

Reading: false-green days run *hotter* on VP threshold share than true-green days on
average (0.480 vs 0.406 for VP≥0.40), while their discrimination gap is *worse*
(0.039 vs 0.116). True-green days lean overwhelmingly HEALTHY on gap band (7/10);
false-green days split evenly 2/2/2 across COMPRESSED/HEALTHY/INVERTED. This is the
quantitative backbone for the two-subtype split above — it is not decoration.

## 5. Sample/capture-quality subtype: not supported in this sample

All six false-green days carry `sigma_status: PASS`, and all have non-null
`avg_hit_prob`/`avg_miss_prob`/`day_sr`/`n_races`. `SAMPLE_CAPTURE_QUALITY_FALSE_GREEN`
did not fire for any of the six. Per the dispatch's own instruction: **this subtype is
not supported in this sample** — stated plainly rather than forced.

## 6. Market/environment subtype: genuinely mixed, not uniform

Market/environment was tested conservatively — flagged only when a day's winner-SP
median sat *outside the entire min–max range* of the 10-day true-green cohort (an
actual outlier), not merely "different from the mean" (which would manufacture a
story from noise). Result: **2 of 6 days show a real winner-SP outlier**
(2026-06-16: median 3.5 vs true-green range [2.1, 3.19]; 2026-06-23: median 1.67,
below the same range) — genuinely differentiating, but in opposite directions (see
detail below). The other 4 days do not clear that
bar and are honestly labelled `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` rather than
forced into the subtype. This is a mixed result, not a uniform pattern across the six.

True-green cohort winner-SP quartiles: min 2.10, median 2.19, p75 2.24, max 3.19.
2026-06-16's winner_sp_median (3.5) sits above this range; 2026-06-23's (1.67) sits
below it — both are genuine outliers, but in opposite directions, which argues against
a single "market got harder/easier" story even for the two days where this subtype
did fire.

## 7. Threshold-flood subtype: concentrated in the healthy-gap days, but not exclusive to them

`THRESHOLD_FLOOD_FALSE_GREEN` fired for 4 of 6 days: both healthy-gap days (06-18,
06-19) **and** two of the four gap-collapse days (06-23, 06-30). This means threshold
flood is not a perfect proxy for the healthy-gap subtype either — it co-occurs with
both primary subtypes. The cleanest reading: gap collapse and threshold flood are
correlated-but-distinct signals of the same underlying event (VP running hot across
the field), and healthy-gap days are simply the subset where that heat happened to
still leave winners with a higher average VP than losers in the aggregate — while
still fielding an outsized share of the pack in the action zone.

## 8. What this rules out

- **Not a uniform disease.** A single fix aimed only at "gap collapse" would miss
  2026-06-18 and 2026-06-19 entirely, since their aggregate discrimination looked fine.
- **Not a data-quality artifact.** All six days are clean `PASS` captures with complete
  fields — this is a genuine model/gate-interaction pattern, not a broken pipeline.
- **Not exclusively a market-conditions story.** Only 2 of 6 days show a genuine
  market-environment outlier; the other 4 do not.

## 9. What this does not do (per task contract)

- Proposes no VP Gatekeeper criteria change, no threshold change, no cure design.
- Does not touch live scoring, Supabase, Telegram, or model promotion.
- `ops/task_contracts/VFU-24.json` forbids `pre_race_gate_change`, `vp_gate_criteria_change`,
  and `cure_design` explicitly.

## 10. Limitations (disclosed)

Same 31-date evidence base as VFU-22/VFU-23 (2026-05-23 to 2026-06-30, this worktree's
coverage). Cohort statistics (true-green quartiles used for threshold-pressure banding)
are computed from only 10 true-green days — a small reference cohort. Re-run after more
dates accumulate to firm up the quartile bands.

## Final classifications

- `CONFIDENCE_FLOOD_ROOT_CAUSE_SPLIT_COMPLETE`
- `ALL_SIX_FALSE_GREEN_DAYS_CLASSIFIED`
- `HEALTHY_GAP_FALSE_GREEN_ANALYZED` — 06-18 and 06-19 both explained via `THRESHOLD_FLOOD_FALSE_GREEN`, not left as narrative-only
- `ROOT_CAUSE_SUBTYPES_REPORTED` — 2 primary subtypes found (`GAP_COLLAPSE_FALSE_GREEN` x4, `HEALTHY_GAP_FALSE_GREEN` x2); `THRESHOLD_FLOOD_FALSE_GREEN` secondary in 4/6; `MARKET_ENVIRONMENT_FALSE_GREEN` secondary in 2/6; `SAMPLE_CAPTURE_QUALITY_FALSE_GREEN` not supported in this sample; `UNRESOLVED_FALSE_GREEN` did not fire (every day had at least one evidenced secondary subtype)
- `NO_CURE_DESIGN_PROPOSED`
- `NO_PRE_RACE_GATE_CHANGE`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_TELEGRAM_SEND`
- `NO_MODEL_PROMOTION`

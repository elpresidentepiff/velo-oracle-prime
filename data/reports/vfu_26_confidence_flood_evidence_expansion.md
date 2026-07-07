# VFU-26 — Confidence Flood Evidence Expansion

**Status:** DRY_RUN / REPORT_ONLY / EVIDENCE EXPANSION ONLY. No cure implemented, no VP
Gatekeeper criteria change, no live scoring change, no Supabase write, no Telegram
send, no model promotion.
**Question this mission answers:** does the VFU-22/VFU-23/VFU-24/VFU-25
`CONFIDENCE_FLOOD_FALSE_GREEN` finding survive more evidence?
**Script:** `scripts/ops/expand_confidence_flood_evidence.py`
**Tests:** `tests/test_confidence_flood_evidence_expansion.py` (21 tests, all pass;
71/71 pass combined with VFU-23's and VFU-24's own suites)
**Raw output:** `data/current/confidence_flood_evidence_expansion_latest.json`

## 0. Where the additional evidence came from

This repo's `data/sigma_results/` directory held 31 dates (2026-05-23 to 2026-06-30).
An existing local artifact directory — the sister worktree of this same project
(`velo-oracle-prime`, the dirty dev copy referenced throughout this project's own
session history, used for local runtime scoring before results are captured into this
clean worktree) — held **11 additional dates** not yet present here: 2026-05-28,
06-15, 06-22, 06-24, 06-25, 06-26, 06-27, 06-28, 06-29, 07-04, 07-05. These are
pre-existing local artifacts (not external API calls, not live racecards), so per the
dispatch's explicit allowance they were copied into this worktree's
`data/sigma_results/` directory (gitignored — this is local data enrichment, not a git
change) so the existing discovery logic picks them up naturally. **Expansion
succeeded: 31 → 42 dates scanned (+11).**

## 1. Baseline reproduction (must happen before any new conclusion)

```json
{
  "baseline_false_green_set": ["2026-06-09","2026-06-16","2026-06-18","2026-06-19","2026-06-23","2026-06-30"],
  "new_false_green_dates": ["2026-06-15","2026-06-26","2026-06-28","2026-07-05"],
  "removed_false_green_dates": [],
  "unchanged_false_green_dates": ["2026-06-09","2026-06-16","2026-06-18","2026-06-19","2026-06-23","2026-06-30"],
  "baseline_fully_reproduced": true
}
```

**All 6 known false-green dates reproduced exactly, zero removed.** The expanded
corpus found **4 new false-green dates** (2026-06-15, 06-26, 06-28, 07-05) —
false-green rate roughly held (see §2).

## 2. Evidence Expansion Summary

| Metric | Baseline (VFU-22/23/24, 31 dates) | Expanded (42 dates) | Delta | Notes |
|---|---|---|---|---|
| sigma_dates_scanned | 31 | 42 | +11 | New dates from sister worktree local artifacts |
| green_days | 16 | 23 | +7 | |
| false_green_days | 6 | 10 | +4 | |
| false_green_rate | 37.5% | 43.5% | +6.0pp | **Rate held and slightly increased — the disease is not shrinking with more evidence** |
| true_green_days | 10 | 13 | +3 | |
| gap_collapse_false_green | 4 | 6 | +2 | Still the majority subtype (6 of 10) |
| healthy_gap_false_green | 2 | 3 | +1 | |
| threshold_flood_false_green | 4 | 5 | +1 | (as secondary subtype count, may co-occur with either primary) |
| market_environment_false_green | 2 | 4 | +2 | Proportion roughly stable (2/6=33% baseline vs 4/10=40% expanded) |
| sample_capture_quality_false_green | 0 | 0 | 0 | Still not supported in this sample — all false-green days remain clean `PASS` captures |
| unresolved_false_green | 0 | **1** | **+1** | **New finding — see §6** |

## 3. Guard Coverage Table

Computed against all 23 GREEN days in the expanded corpus (13 true-green + 10
false-green), using ground truth = `false_green_confirmed`:

| Guard | Target subtype | TP | FP | FN | TN | Coverage (recall) | FP rate | FN rate | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Gap-Collapse Guard | `GAP_COLLAPSE_FALSE_GREEN` | 6 | 1 | 4 | 12 | 60.0% | 7.7% | 40.0% | 1 false-positive (2026-06-11, COMPRESSED gap on a genuinely true-green day, SR 33.3%) — this exact case was already disclosed as a risk in VFU-23/VFU-25; now confirmed real |
| Threshold-Flood Guard | `HEALTHY_GAP_FALSE_GREEN` + `THRESHOLD_FLOOD_FALSE_GREEN` | 5 | 4 | 5 | 9 | 50.0% | **30.8%** | 50.0% | **False-positive rate is meaningfully worse than the small VFU-24/25 sample suggested (which showed 0/10 true-green false positives)** — see §7 |
| Combined Green-Day Risk Overlay | Both | 10 | 5 | **0** | 8 | **100.0%** | 38.5% | 0.0% | Perfect recall on the known false-green set, but at real precision cost: **more than 1 in 3 true-green days would be flagged** |

## 4. Market Outlier Table (all 23 GREEN days)

| Date | False-green confirmed | Winner SP median | Market outlier band | Primary subtype | Caught by gap guard | Caught by threshold guard | Caught by combined overlay |
|---|---|---|---|---|---|---|---|
| 2026-06-03 | No | — | WITHIN_RANGE | — | No | No | No |
| 2026-06-04 | No | — | WITHIN_RANGE | — | No | Yes | Yes |
| 2026-06-05 | No | — | INSUFFICIENT_EVIDENCE | — | No | No | No |
| 2026-06-06 | No | — | INSUFFICIENT_EVIDENCE | — | No | No | No |
| 2026-06-08 | No | — | INSUFFICIENT_EVIDENCE | — | No | No | No |
| **2026-06-09** | **Yes** | n/a (no winner_sp captured) | INSUFFICIENT_EVIDENCE | `GAP_COLLAPSE_FALSE_GREEN` | Yes | No | Yes |
| 2026-06-11 | No | — | INSUFFICIENT_EVIDENCE | — | **Yes (false positive)** | No | Yes |
| 2026-06-12 | No | — | INSUFFICIENT_EVIDENCE | — | No | No | No |
| 2026-06-13 | No | — | INSUFFICIENT_EVIDENCE | — | No | No | No |
| 2026-06-14 | No | — | WITHIN_RANGE | — | No | No | No |
| **2026-06-15** | **Yes** | 2.31 | WITHIN_RANGE | `GAP_COLLAPSE_FALSE_GREEN` | Yes | No | Yes |
| **2026-06-16** | **Yes** | 3.50 | **OUTLIER** | `GAP_COLLAPSE_FALSE_GREEN` | Yes | No | Yes |
| **2026-06-18** | **Yes** | 2.50 | WITHIN_RANGE | `HEALTHY_GAP_FALSE_GREEN` | No | Yes | Yes |
| **2026-06-19** | **Yes** | 2.38 | WITHIN_RANGE | `HEALTHY_GAP_FALSE_GREEN` | No | Yes | Yes |
| 2026-06-20 | No | — | WITHIN_RANGE | — | No | Yes | Yes |
| 2026-06-22 | No | — | WITHIN_RANGE | — | No | Yes | Yes |
| **2026-06-23** | **Yes** | 1.67 | **OUTLIER** | `GAP_COLLAPSE_FALSE_GREEN` | Yes | Yes | Yes |
| **2026-06-26** | **Yes** | 3.00 | WITHIN_RANGE | `HEALTHY_GAP_FALSE_GREEN` | No | Yes | Yes |
| 2026-06-27 | No | — | WITHIN_RANGE | — | No | Yes | Yes |
| **2026-06-28** | **Yes** | 1.865 | **OUTLIER** | `UNRESOLVED_FALSE_GREEN` | No | Yes | Yes |
| **2026-06-30** | **Yes** | 2.88 | WITHIN_RANGE | `GAP_COLLAPSE_FALSE_GREEN` | Yes | No | Yes |
| 2026-07-04 | No | — | WITHIN_RANGE | — | No | No | No |
| **2026-07-05** | **Yes** | 4.00 | **OUTLIER** | `GAP_COLLAPSE_FALSE_GREEN` | Yes | No | Yes |

**Answer to the required check — do market-environment outliers remain a separate
hole?** Yes, partially confirmed and partially narrowed: of the 10 confirmed
false-green days, **4 show a genuine winner-SP outlier** (06-16, 06-23, 06-28, 07-05).
All 4 of those are *also* caught by at least one guard (gap-collapse or
threshold-flood) — so in this expanded sample, no false-green day was missed by
*both* guards *and* explained *only* by a market outlier. That is a narrowing of the
VFU-25 concern (which worried a market-only miss could slip through both guards
entirely). However, this is not the same as saying market environment is irrelevant:
it remains the *strongest secondary signal* on 4 of 10 days, and the guards catching
those days does not mean the guards are catching them *for the right reason* — the
overlap could be coincidental at this sample size. **This should not be read as
"solved."**

## 5. Per-Date Diagnostic Table (all 42 scanned dates)

| Date | sigma_status | n_races | Day SR | Gate | avg VP | 0.40 share | 0.45 share | VP gap | Gap band | False-green | Primary subtype | Secondary subtypes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-21 | PASS | 0 | 29.6% | UNCLASSIFIED | — | — | — | — | UNKNOWN | No | — | — |
| 2026-05-22 | PASS | 0 | 25.0% | UNCLASSIFIED | — | — | — | — | UNKNOWN | No | — | — |
| 2026-05-23 | PARTIAL | 45 | 28.9% | RED | 0.188 | 0.044 | 0.022 | 0.032 | COMPRESSED | No | — | — |
| 2026-05-24 | PASS | 14 | 28.6% | RED | 0.214 | 0.000 | 0.000 | -0.011 | INVERTED | No | — | — |
| 2026-05-25 | PASS | 34 | 20.6% | RED | 0.231 | 0.000 | 0.000 | 0.029 | COMPRESSED | No | — | — |
| 2026-05-26 | PASS | 33 | 18.2% | UNCLASSIFIED | 0.311 | 0.242 | 0.152 | -0.005 | INVERTED | No | — | — |
| 2026-05-27 | PASS | 32 | 31.3% | UNCLASSIFIED | 0.285 | 0.188 | 0.063 | 0.138 | HEALTHY | No | — | — |
| **2026-05-28 (new)** | PARTIAL | 0 | — | UNCLASSIFIED | — | — | — | — | UNKNOWN | No | — | — |
| 2026-05-29 | PASS | 27 | 22.2% | RED | 0.205 | 0.074 | 0.037 | -0.020 | INVERTED | No | — | — |
| 2026-05-30 | PASS | 35 | 11.4% | RED | 0.171 | 0.029 | 0.000 | 0.096 | HEALTHY | No | — | — |
| 2026-05-31 | PARTIAL | 21 | 9.5% | RED | 0.231 | 0.048 | 0.000 | 0.180 | HEALTHY | No | — | — |
| 2026-06-01 | PASS | 21 | 28.6% | RED | 0.244 | 0.095 | 0.095 | 0.162 | HEALTHY | No | — | — |
| 2026-06-02 | PASS | 27 | 37.0% | AMBER | 0.269 | 0.074 | 0.074 | -0.002 | INVERTED | No | — | — |
| 2026-06-03 | PASS | 19 | 26.3% | GREEN | 0.441 | 0.421 | 0.316 | 0.197 | HEALTHY | No | — | — |
| 2026-06-04 | PARTIAL | 34 | 38.2% | GREEN | 0.440 | 0.471 | 0.412 | 0.182 | HEALTHY | No | — | — |
| 2026-06-05 | PASS | 39 | 33.3% | GREEN | 0.352 | 0.410 | 0.333 | 0.122 | HEALTHY | No | — | — |
| 2026-06-06 | PASS | 49 | 26.1% | GREEN | 0.386 | 0.408 | 0.306 | 0.119 | HEALTHY | No | — | — |
| 2026-06-07 | PASS | 30 | 21.4% | UNCLASSIFIED | 0.337 | 0.300 | 0.200 | 0.068 | WEAK | No | — | — |
| 2026-06-08 | PASS | 35 | 38.7% | GREEN | 0.375 | 0.400 | 0.286 | 0.086 | HEALTHY | No | — | — |
| **2026-06-09** | PASS | 33 | 13.8% | GREEN | 0.355 | 0.303 | 0.212 | 0.047 | COMPRESSED | **Yes** | `GAP_COLLAPSE_FALSE_GREEN` | `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |
| 2026-06-10 | PASS | 34 | 20.7% | UNCLASSIFIED | 0.325 | 0.294 | 0.147 | 0.119 | HEALTHY | No | — | — |
| 2026-06-11 | PASS | 40 | 33.3% | GREEN | 0.393 | 0.400 | 0.350 | 0.045 | COMPRESSED | No | — | — |
| 2026-06-12 | PASS | 51 | 39.1% | GREEN | 0.369 | 0.373 | 0.255 | 0.137 | HEALTHY | No | — | — |
| 2026-06-13 | PASS | 58 | 28.1% | GREEN | 0.369 | 0.328 | 0.241 | 0.127 | HEALTHY | No | — | — |
| 2026-06-14 | PASS | 29 | 27.6% | GREEN | 0.399 | 0.345 | 0.207 | 0.067 | WEAK | No | — | — |
| **2026-06-15 (new)** | PASS | 26 | 23.1% | GREEN | 0.356 | 0.346 | 0.192 | 0.013 | COMPRESSED | **Yes** | `GAP_COLLAPSE_FALSE_GREEN` | `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |
| **2026-06-16** | PASS | 33 | 21.2% | GREEN | 0.350 | 0.333 | 0.152 | 0.046 | COMPRESSED | **Yes** | `GAP_COLLAPSE_FALSE_GREEN` | `MARKET_ENVIRONMENT_FALSE_GREEN` |
| 2026-06-17 | PASS | 35 | 45.7% | RED | 0.246 | 0.114 | 0.057 | -0.008 | INVERTED | No | — | — |
| **2026-06-18** | PASS | 33 | 21.2% | GREEN | 0.433 | 0.515 | 0.394 | 0.203 | HEALTHY | **Yes** | `HEALTHY_GAP_FALSE_GREEN` | `THRESHOLD_FLOOD_FALSE_GREEN`, `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |
| **2026-06-19** | PASS | 56 | 19.6% | GREEN | 0.471 | 0.625 | 0.571 | 0.082 | HEALTHY | **Yes** | `HEALTHY_GAP_FALSE_GREEN` | `THRESHOLD_FLOOD_FALSE_GREEN`, `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |
| 2026-06-20 | PASS | 48 | 25.0% | GREEN | 0.409 | 0.500 | 0.375 | 0.075 | WEAK | No | — | — |
| **2026-06-22 (new)** | PASS | 31 | 25.8% | GREEN | 0.482 | 0.613 | 0.548 | 0.123 | HEALTHY | No | — | — |
| **2026-06-23** | PASS | 17 | 17.6% | GREEN | 0.480 | 0.647 | 0.588 | -0.093 | INVERTED | **Yes** | `GAP_COLLAPSE_FALSE_GREEN` | `THRESHOLD_FLOOD_FALSE_GREEN`, `MARKET_ENVIRONMENT_FALSE_GREEN` |
| **2026-06-24 (new)** | PASS | 4 | 50.0% | AMBER | 0.295 | 0.250 | 0.000 | 0.148 | HEALTHY | No | — | — |
| **2026-06-25 (new)** | PASS | 10 | 30.0% | RED | 0.230 | 0.000 | 0.000 | -0.104 | INVERTED | No | — | — |
| **2026-06-26 (new)** | PASS | 39 | 23.1% | GREEN | 0.477 | 0.641 | 0.564 | 0.207 | HEALTHY | **Yes** | `HEALTHY_GAP_FALSE_GREEN` | `THRESHOLD_FLOOD_FALSE_GREEN`, `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |
| **2026-06-27 (new)** | PASS | 37 | 24.3% | GREEN | 0.438 | 0.541 | 0.405 | 0.101 | HEALTHY | No (SR just above baseline) | — | — |
| **2026-06-28 (new)** | PASS | 29 | 13.8% | GREEN | 0.435 | 0.552 | 0.379 | 0.075 | **WEAK** | **Yes** | **`UNRESOLVED_FALSE_GREEN`** | `THRESHOLD_FLOOD_FALSE_GREEN`, `MARKET_ENVIRONMENT_FALSE_GREEN` |
| **2026-06-29 (new)** | PASS | 33 | 36.4% | UNCLASSIFIED | 0.338 | 0.242 | 0.242 | 0.000 | COMPRESSED | No | — | — |
| **2026-06-30** | PASS | 46 | 23.9% | GREEN | 0.398 | 0.457 | 0.304 | -0.050 | INVERTED | **Yes** | `GAP_COLLAPSE_FALSE_GREEN` | `MARKET_ENVIRONMENT_INSUFFICIENT_EVIDENCE` |
| **2026-07-04 (new)** | PASS | 51 | 29.4% | GREEN | 0.355 | 0.412 | 0.314 | 0.079 | WEAK | No | — | — |
| **2026-07-05 (new)** | PASS | 22 | 18.2% | GREEN | 0.402 | 0.364 | 0.273 | -0.023 | INVERTED | **Yes** | `GAP_COLLAPSE_FALSE_GREEN` | `MARKET_ENVIRONMENT_FALSE_GREEN` |

`sigma_status: PARTIAL` = `PARTIAL_RESULTS_DIAGNOSTIC_ONLY` (abbreviated for table
width). Sample/capture-quality subtype: still 0/10 among confirmed false-green days —
all remain clean `PASS` captures (2026-06-28, the one new-subtype day, is also
`PASS`). 2026-06-27's day SR (24.32%) sits just above the 24.3% baseline threshold —
a near-miss, correctly *not* classified false-green, but close enough to flag as a
borderline case for future evidence rounds.

## 6. New finding: a third gap-band bucket appears in a false-green day

Every prior false-green day (VFU-24, n=6) fell cleanly into either `COMPRESSED`/
`INVERTED` (gap-collapse) or `HEALTHY` (healthy-gap). **2026-06-28 has `gap_band =
WEAK`** (0.0754, just under the 0.08 HEALTHY cutoff) — the first false-green day that
doesn't fit either primary subtype from VFU-24's classifier. It is correctly labelled
`UNRESOLVED_FALSE_GREEN` as primary, though it does carry two evidenced secondary
signals (`THRESHOLD_FLOOD_FALSE_GREEN` and a genuine `MARKET_ENVIRONMENT_FALSE_GREEN`
outlier, winner SP median 1.865, below the true-green cohort's range). **This is
exactly the kind of new information more evidence was supposed to surface**: the
two-variant taxonomy from VFU-24 was built on 6 examples and, predictably, a 7th+
example lands on the boundary between the two. This does not invalidate VFU-24's
split — it shows the boundary needs a WEAK-band handling rule, which this mission
does not design (out of scope — VFU-26 is evidence expansion only).

## 7. Why guard precision looks worse now than in VFU-24/25

With only 10 true-green reference days (VFU-24/25), the Threshold-Flood Guard showed
**zero** false positives. With 13 true-green days now available, it shows **4** false
positives (2026-06-04, 06-20, 06-22, 06-27 — all GREEN days where the field ran hot on
VP thresholds but the day still beat baseline SR). This is not a bug in the guard — it
is exactly the "n=10 is too small to bound a real-world false-positive rate" warning
VFU-25 itself gave in its own §8 promotion criteria. The expanded sample confirms that
warning was warranted: **a 30.8% false-positive rate on the Threshold-Flood Guard is a
real, now-measured number, not a hypothetical risk.** This is evidence the finding
survived, but evidence the *cure candidates* did not get stronger — if anything, the
Threshold-Flood Guard specifically looks weaker under more scrutiny.

## 8. Evidence verdict

**`EVIDENCE_EXPANDED_MIXED_RESULT`**

- The core disease finding (`CONFIDENCE_FLOOD_FALSE_GREEN`, false-green rate ~37-44%
  of GREEN days) **held and slightly strengthened** with more evidence (37.5% → 43.5%).
  All 6 originally confirmed false-green days remain confirmed; 4 new ones appeared.
  This is a `EVIDENCE_EXPANDED_CONFIDENCE_INCREASED`-shaped result at the disease level.
- The two-variant split (gap-collapse vs. healthy-gap-threshold-flood) **mostly held**
  but is now known to be incomplete — a third case (`UNRESOLVED_FALSE_GREEN`, WEAK gap
  band) appeared that neither variant cleanly covers. This is a
  `EVIDENCE_EXPANDED_CONFIDENCE_WEAKENED`-shaped result for the taxonomy's completeness.
- The candidate guards from VFU-25 **show materially worse measured false-positive
  behaviour** with a larger true-green reference cohort (Threshold-Flood Guard: 0% →
  30.8% FP rate). This is also a weakening signal, specifically about cure readiness,
  not about the underlying disease.

Because the disease-level evidence strengthened while the cure-readiness evidence
weakened, the honest overall verdict is **mixed**, not a clean "confidence increased."

## 9. Cure promotion status (per VFU-25 candidate, updated)

| Candidate | Prior status (VFU-25) | Status after VFU-26 | Why |
|---|---|---|---|
| Gap-Collapse Guard | `DESIGN_ONLY` | `DESIGN_ONLY` (unchanged) | Still purely retrospective; no pre-race path exists regardless of corpus size |
| Threshold-Flood Guard | `NEEDS_MORE_EVIDENCE` | **`NEEDS_MORE_EVIDENCE`** (confidence *lower*, not higher) | Measured false-positive rate (30.8%) is now known and is worse than the small sample suggested — moving this toward shadow testing now would be premature |
| Green-Day Risk Overlay | `SHADOW_TEST_NEXT` (reporting-only) | `NEEDS_MORE_EVIDENCE` for any decision-relevant use; **`SHADOW_TEST_NEXT` still stands strictly as a reporting label** | Perfect recall (0 FN) is good news, but a 38.5% false-positive rate on true-green days means this label would be wrong more than a third of the time it fires — acceptable for a shadow *report*, not for anything that could influence engagement decisions |
| Same-Day Post-Sigma Reporting Enhancement | `SHADOW_TEST_NEXT` | `SHADOW_TEST_NEXT` (unchanged) | Still the lowest-risk candidate — it reports numbers, it does not decide anything. Nothing in this expansion changes that risk profile |
| Promotion/Rejection Criteria | `DESIGN_ONLY` | `DESIGN_ONLY` (unchanged, and validated) | This expansion is itself a live demonstration of why criterion #1 ("more dates") in VFU-25 §8 mattered — the guard's FP rate estimate changed materially with more data, exactly the failure mode the criteria were written to catch |

**No candidate is promoted to `SHADOW_TEST_READY` or beyond.** Per the dispatch's own
default, the status remains `NEEDS_MORE_EVIDENCE` for anything that would inform a
gate-adjacent decision.

## 10. What this does not do

No cure implemented. No VP Gatekeeper criteria change. No pre-race gate change. No
live scoring change. No Supabase write. No Telegram send. No model promotion. This
mission only expanded and recomputed evidence.

## Final classifications

- `CONFIDENCE_FLOOD_EVIDENCE_EXPANSION_COMPLETE`
- `SIGMA_CORPUS_EXPANSION_ATTEMPTED` — succeeded, 31 → 42 dates
- `BASELINE_FALSE_GREEN_SET_REPRODUCED` — 6/6, zero removed
- `GUARD_COVERAGE_RECOMPUTED` — Threshold-Flood Guard FP rate revised upward materially (0% → 30.8%)
- `MARKET_OUTLIER_BEHAVIOUR_REPORTED` — 4 of 10 confirmed false-green days show a genuine market-SP outlier; all 4 also caught by an existing guard in this sample, narrowing but not eliminating the concern
- `CURE_PROMOTION_STATUS_REPORTED` — all candidates remain at `DESIGN_ONLY`/`NEEDS_MORE_EVIDENCE`/reporting-only `SHADOW_TEST_NEXT`; none promoted
- `NO_CURE_IMPLEMENTED`
- `NO_PRE_RACE_GATE_CHANGE`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_TELEGRAM_SEND`
- `NO_MODEL_PROMOTION`

# VFU-23 — Confidence Flood Retrospective Diagnostic

**Status:** DRY_RUN / REPORT_ONLY / RETROSPECTIVE_ONLY. No pre-race VP Gatekeeper change,
no live scoring change, no Supabase write, no Telegram send, no model promotion.
**Instrument, not a cure:** VFU-22 found the disease (`CONFIDENCE_FLOOD_FALSE_GREEN`).
VFU-23 builds the thermometer — a post-Sigma diagnostic that measures it every time
Sigma closes. It changes nothing about how or when a day is gated pre-race.
**Script:** `scripts/ops/build_confidence_flood_diagnostic.py`
**Tests:** `tests/test_confidence_flood_diagnostic.py` (21 tests, all pass)
**Raw output:** `data/current/confidence_flood_diagnostic_latest.json`

## 1. Reproduction of the known VFU-22 false-green set — REQUIRED CHECK

The diagnostic's `false_green_confirmed` field (post-results only: `vp_gate_class == GREEN`
AND `day_sr < 0.243`) was run against all 31 `sigma_results_*.json` artifacts on disk.

**Result: fully reproduced, 6 of 6, with zero extras beyond the known set.**

```json
{
  "expected":  ["2026-06-09","2026-06-16","2026-06-18","2026-06-19","2026-06-23","2026-06-30"],
  "confirmed": ["2026-06-09","2026-06-16","2026-06-18","2026-06-19","2026-06-23","2026-06-30"],
  "missing": [],
  "extra_beyond_vfu22_set": [],
  "fully_reproduced": true
}
```

This is a direct re-implementation of the VFU-22 definition (GREEN gate + SR below the
24.3% baseline), so exact reproduction is expected by construction — it confirms the
diagnostic's gate-classification and SR-comparison logic match VFU-22's manual scan
exactly, with no drift or off-by-one errors introduced while automating it.

## 2. Full per-date diagnostic (all 31 available dates)

| Date | Gate | VP gap | Gap band | Flood flag | False-green confirmed | Day SR |
|---|---|---|---|---|---|---|
| 2026-05-21 | UNCLASSIFIED | — | UNKNOWN | No | No | 29.6% |
| 2026-05-22 | UNCLASSIFIED | — | UNKNOWN | No | No | 25.0% |
| 2026-05-23 | RED | 0.032 | COMPRESSED | No | No | 28.9% |
| 2026-05-24 | RED | -0.011 | INVERTED | No | No | 28.6% |
| 2026-05-25 | RED | 0.029 | COMPRESSED | No | No | 20.6% |
| 2026-05-26 | UNCLASSIFIED | -0.005 | INVERTED | No | No | 18.2% |
| 2026-05-27 | UNCLASSIFIED | 0.138 | HEALTHY | No | No | 31.3% |
| 2026-05-29 | RED | -0.020 | INVERTED | No | No | 22.2% |
| 2026-05-30 | RED | 0.096 | HEALTHY | No | No | 11.4% |
| 2026-05-31 | RED | 0.180 | HEALTHY | No | No | 9.5% |
| 2026-06-01 | RED | 0.162 | HEALTHY | No | No | 28.6% |
| 2026-06-02 | AMBER | -0.002 | INVERTED | No | No | 37.0% |
| 2026-06-03 | GREEN | 0.197 | HEALTHY | No | No | 26.3% |
| 2026-06-04 | GREEN | 0.182 | HEALTHY | No | No | 38.2% |
| 2026-06-05 | GREEN | 0.122 | HEALTHY | No | No | 33.3% |
| 2026-06-06 | GREEN | 0.119 | HEALTHY | No | No | 26.1% |
| 2026-06-07 | UNCLASSIFIED | 0.068 | WEAK | No | No | 21.4% |
| 2026-06-08 | GREEN | 0.086 | HEALTHY | No | No | 38.7% |
| **2026-06-09** | **GREEN** | **0.047** | **COMPRESSED** | **Yes** | **Yes** | **13.8%** |
| 2026-06-10 | UNCLASSIFIED | 0.119 | HEALTHY | No | No | 20.7% |
| 2026-06-11 | GREEN | 0.045 | COMPRESSED | **Yes** | No | 33.3% |
| 2026-06-12 | GREEN | 0.137 | HEALTHY | No | No | 39.1% |
| 2026-06-13 | GREEN | 0.127 | HEALTHY | No | No | 28.1% |
| 2026-06-14 | GREEN | 0.067 | WEAK | No | No | 27.6% |
| **2026-06-16** | **GREEN** | **0.046** | **COMPRESSED** | **Yes** | **Yes** | **21.2%** |
| 2026-06-17 | RED | -0.008 | INVERTED | No | No | 45.7% |
| **2026-06-18** | **GREEN** | 0.203 | HEALTHY | No | **Yes** | **21.2%** |
| **2026-06-19** | **GREEN** | 0.082 | HEALTHY | No | **Yes** | **19.6%** |
| 2026-06-20 | GREEN | 0.075 | WEAK | No | No | 25.0% |
| **2026-06-23** | **GREEN** | **-0.093** | **INVERTED** | **Yes** | **Yes** | **17.6%** |
| **2026-06-30** | **GREEN** | **-0.050** | **INVERTED** | **Yes** | **Yes** | **23.9%** |

Bold rows are the 6 confirmed false-green days (per VFU-22).

## 3. Honest limitation: `confidence_flood_flag` is a partial leading indicator, not a perfect predictor

This must be stated plainly rather than glossed over. Two different fields answer two
different questions:

- **`false_green_confirmed`** — ground truth. Requires the day's actual SR. Always
  correct by definition, but only knowable after results land.
- **`confidence_flood_flag`** — a same-day-of-Sigma-close *leading* signal, computed only
  from `vp_gate_class == GREEN` AND `gap_band in [INVERTED, COMPRESSED]` (i.e. it does not
  use `day_sr` at all — the closest the diagnostic gets to something available at the
  moment Sigma closes, before a human checks the day's SR).

Comparing the two: the flood flag caught **4 of the 6** confirmed false-green days
(06-09, 06-16, 06-23, 06-30) via a suspicious gap band alone. It **missed 2 of 6**
(06-18: gap +0.203, HEALTHY; 06-19: gap +0.082, just inside HEALTHY at the 0.08 boundary)
— both of these were false-green despite a healthy-looking discrimination gap, meaning
gap band alone is not sufficient evidence in every case. It also produced **1 flag on a
true-green day** (06-11, gap +0.045, COMPRESSED, but SR was a healthy 33.3%) — a false
positive under the flood-flag's own logic.

**Conclusion:** the gap-band flood flag is a useful same-day triage signal (it did
surface 4 of 6 real cases and only 1 false alarm out of 16 GREEN days), but it is not a
substitute for the ground-truth `false_green_confirmed` check, and neither field should
ever be treated as available before results land. Do not read `confidence_flood_flag` as
"solved" — it is a coarser proxy than `false_green_confirmed`, and this diagnostic keeps
both fields separate and separately labelled specifically so that distinction cannot be
lost.

## 4. What this diagnostic does not do

- Does not change `docs/current/VP_GATEKEEPER_PROMOTION_V1.md` criteria.
- Does not touch `run_prime_today.py`, `velo_prime_ensemble.py`, or any live-scoring path.
- Does not write to Supabase.
- Does not send Telegram.
- Does not promote any model.
- Cannot run before Sigma has closed for a given date — it is retrospective by
  construction (it reads `sigma_results_*.json`, which does not exist pre-race).

## 5. How to run it

```bash
PYTHONPATH=. python scripts/ops/build_confidence_flood_diagnostic.py --out data/current/confidence_flood_diagnostic_latest.json
```

Optionally add `--sigma-results-dir <path>` to point at a different corpus. Full
per-field schema and usage: `docs/current/CONFIDENCE_FLOOD_DIAGNOSTIC.md`.

## 6. Coverage / limitations

Same evidence base and same limitations as VFU-22: 31 `sigma_results_*.json` files on
disk in this worktree (2026-05-23 to 2026-06-30), not full system history. Re-run after
more dates accumulate to extend coverage.

## Final classifications

- `CONFIDENCE_FLOOD_DIAGNOSTIC_ACTIVE`
- `RETROSPECTIVE_ONLY_DIAGNOSTIC`
- `VFU_22_FALSE_GREEN_SET_REPRODUCED` — 6/6, zero extras
- `DIAGNOSTIC_ARTIFACTS_CREATED`
- `NO_PRE_RACE_GATE_CHANGE`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_TELEGRAM_SEND`
- `NO_MODEL_PROMOTION`

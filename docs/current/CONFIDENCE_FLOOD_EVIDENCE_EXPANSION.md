# CONFIDENCE_FLOOD_EVIDENCE_EXPANSION.md

**Status:** ACTIVE, EVIDENCE EXPANSION ONLY (VFU-26)
**Script:** `scripts/ops/expand_confidence_flood_evidence.py`
**Tests:** `tests/test_confidence_flood_evidence_expansion.py`
**Evidence report:** `data/reports/vfu_26_confidence_flood_evidence_expansion.md`
**Origin:** Checks whether the VFU-22 (`CONFIDENCE_FLOOD_FALSE_GREEN`), VFU-23
(retrospective diagnostic), VFU-24 (root-cause split), and VFU-25 (cure design
sandbox) findings survive a larger evidence base. No cure implemented here.

## What this is

A script that discovers all local `sigma_results_*.json` artifacts (this repo's
`data/sigma_results/` plus, when passed via `--extra-dir`, any additional local
artifact directory such as a sister worktree of this same project), deduplicates by
date, recomputes the full VFU-22 through VFU-24 diagnostic picture, and compares
against the VFU-22/23/24 baseline (31 dates, 6 confirmed false-green days).

**Expansion result: 31 → 42 dates (+11), sourced from this project's own sister
worktree's `data/sigma_results/` directory** — a pre-existing local artifact, not an
external API or live racecard.

## Headline result

- **All 6 known false-green dates reproduced exactly.** Zero removed.
- **4 new false-green dates found** (2026-06-15, 06-26, 06-28, 07-05).
- **False-green rate held and slightly increased**: 37.5% (6/16) → 43.5% (10/23).
- **A new gap-band case appeared** (2026-06-28, `WEAK` band) that doesn't cleanly fit
  either of VFU-24's two primary subtypes — classified `UNRESOLVED_FALSE_GREEN`.
- **Guard false-positive rates got measurably worse with more true-green reference
  data**: the Threshold-Flood Guard's false-positive rate went from an unmeasurable
  0/10 (VFU-24/25 sample) to a real 30.8% (4/13) now that a larger true-green cohort
  exists. This is exactly the risk VFU-25's own promotion criteria warned about.

## Evidence verdict

**`EVIDENCE_EXPANDED_MIXED_RESULT`** — the underlying disease (confidence-flood
false-green) is confirmed to persist and, if anything, worsen slightly with more data.
The candidate cures from VFU-25 did not get more promotable; the Threshold-Flood
Guard specifically looks weaker under scrutiny than the small sample suggested. Full
detail, tables, and per-date diagnostics: `data/reports/vfu_26_confidence_flood_evidence_expansion.md`.

## Cure promotion status after this expansion

No candidate is promoted. All remain `DESIGN_ONLY` / `NEEDS_MORE_EVIDENCE` / a
reporting-only `SHADOW_TEST_NEXT` (Same-Day Post-Sigma Reporting Enhancement only,
since it changes no decision). The Threshold-Flood Guard and the Green-Day Risk
Overlay's decision-relevant use both moved *further* from promotion, not closer, given
the newly measured false-positive rate.

## How to run

```bash
PYTHONPATH=. python scripts/ops/expand_confidence_flood_evidence.py \
  --extra-dir /path/to/another/local/sigma_results/dir \
  --out data/current/confidence_flood_evidence_expansion_latest.json
```

`--extra-dir` is repeatable and optional; without it, only this repo's own
`data/sigma_results/` is scanned.

## What this explicitly does not do

- Does not implement any cure or guard as running/decision-making code.
- Does not change `docs/current/VP_GATEKEEPER_PROMOTION_V1.md` criteria.
- Does not touch live scoring, Supabase, Telegram, or model promotion.
- Does not call any external API or read any live racecard.
- Does not modify `scripts/ops/build_confidence_flood_diagnostic.py` or
  `scripts/ops/build_confidence_flood_root_cause_split.py` (VFU-23/24) — imports and
  reuses their classification functions read-only.

## Next step

The new `UNRESOLVED_FALSE_GREEN` / `WEAK`-gap-band case (2026-06-28) is a genuine open
question the VFU-24 taxonomy does not yet resolve, and the Threshold-Flood Guard's
newly measured 30.8% false-positive rate argues against any shadow-test promotion for
now. Any future mission to address either would need its own operator-approved
dispatch — this mission does not recommend one unprompted, per the established pattern
in this project's session history.

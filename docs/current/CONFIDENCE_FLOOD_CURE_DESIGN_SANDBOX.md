# CONFIDENCE_FLOOD_CURE_DESIGN_SANDBOX.md

**Status:** DESIGN SANDBOX ONLY (VFU-25). Nothing on this page is implemented.
**Evidence report:** `data/reports/vfu_25_confidence_flood_cure_design_sandbox.md`
**Origin:** VFU-22 found `CONFIDENCE_FLOOD_FALSE_GREEN`; VFU-23 built a retrospective
diagnostic; VFU-24 split it into `GAP_COLLAPSE_FALSE_GREEN` (4 days) and
`HEALTHY_GAP_FALSE_GREEN` + `THRESHOLD_FLOOD_FALSE_GREEN` (2 days). VFU-25 designs —
but does not build or ship — candidate mitigations for both variants.

## The architecture boardroom, not the operating theatre

Everything below is a design proposal for future evaluation. **No cure is
implemented. No VP Gatekeeper criteria change. No live scoring path changes. No
Supabase write, no Telegram send, no model promotion occurs as part of this
document or the mission that produced it.**

## Five candidates designed

| # | Candidate | Targets | Pre-race available | Recommended status |
|---|---|---|---|---|
| 1 | Gap-Collapse Guard | `GAP_COLLAPSE_FALSE_GREEN` | No | `DESIGN_ONLY` |
| 2 | Threshold-Flood Guard | `HEALTHY_GAP_FALSE_GREEN` + `THRESHOLD_FLOOD_FALSE_GREEN` | Partial | `NEEDS_MORE_EVIDENCE` |
| 3 | Green-Day Risk Overlay | Both (combines 1+2) | No | `SHADOW_TEST_NEXT` (reporting-only) |
| 4 | Same-Day Post-Sigma Reporting Enhancement | Both | No | `SHADOW_TEST_NEXT` |
| 5 | Promotion/Rejection Criteria | Both (the evidence bar itself) | N/A | `DESIGN_ONLY` |

Full design detail, candidate-by-subtype mapping, false-positive/false-negative risk
disclosure, and the required candidate table are in
`data/reports/vfu_25_confidence_flood_cure_design_sandbox.md` — this page is the
pointer/summary, not a duplicate of the full analysis.

## Key finding: no single guard covers both variants

`GAP_COLLAPSE_FALSE_GREEN` and `HEALTHY_GAP_FALSE_GREEN` are different pathologies
(VFU-24). A guard tuned only to discrimination-gap collapse would still miss
2026-06-18/2026-06-19-type days; a guard tuned only to threshold flood would still
miss 2026-06-09/2026-06-16-type days. The Green-Day Risk Overlay (candidate 3) is
designed specifically to combine both guards into one label, plus an honest
`GREEN_UNRESOLVED_RISK` bucket for false-green days neither guard can explain (a
real, disclosed possibility — VFU-24 found 2 of the 6 known days had a genuine
market-environment outlier as their strongest secondary signal, which neither guard
detects).

## Why nothing here is ready to leave the sandbox

The entire evidence base is 31 `sigma_results_*.json` dates, 16 GREEN days, 6 confirmed
false-green days, and a 10-day true-green reference cohort. That is too small to bound
any real-world false-positive or false-negative rate. Section 8 of the evidence report
defines the minimum standard (more dates, no true-green regression, bounded
false-positive rate, disclosed false-negative rate, works separately for both
variants, dry-run burn-in mirroring the existing VCP-03 protocol, operator tribunal
approval mirroring the VFU-12 Sigma Pattern Tribunal, and a rollback plan mirroring
the existing `VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE` pattern) that any candidate
here would need to clear before a live gate conversation could even start.

## What this explicitly does not do

- Does not implement any cure, guard, or overlay as running code.
- Does not change `docs/current/VP_GATEKEEPER_PROMOTION_V1.md` criteria.
- Does not touch live scoring, Supabase, Telegram, or model promotion.
- Does not modify `scripts/ops/build_confidence_flood_diagnostic.py` or
  `scripts/ops/build_confidence_flood_root_cause_split.py` (VFU-23/VFU-24) — read only.

## Next step

Two independent follow-ups are recommended (neither started): **VFU-26 — Confidence
Flood Evidence Expansion** (grow the corpus, especially the true-green reference
cohort past n=10) and **VFU-27 — Same-Day Post-Sigma Reporting Enhancement (shadow
build)** (candidate 4 above, the lowest-risk item on the candidate table since it
changes no decision, only visibility). Both require their own formal operator
dispatch before starting.

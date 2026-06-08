# Council Sigma Artifact Recheck

**Trigger:** Sigma local artifact gap fixed — STEP 9 added to `run_results_sigma.py`

## Before vs After

| Date | Before | After |
|---|---|---|
| 2026-05-20 | QUARANTINE_DAY | **QUARANTINE_DAY** (unchanged) |
| 2026-05-21 | WATCH_ONLY | **PASS_TO_LEARNING** |
| 2026-05-22 | WATCH_ONLY | **PASS_TO_LEARNING** |

## What Changed

**May 21 and May 22 now correctly pass** because:
- `data/sigma_results/sigma_results_{date}.json` now exists for each clean day
- `SigmaCoverageAgent` can read actual SR (29.5% May 21, 25.0% May 22) — both above baseline
- `data/mission_control/2026-05-21_mission_control.json` created — DataAuditor reads source_truth=RP_MERGED_CLEAN

**May 20 remains QUARANTINE_DAY** because:
- Contamination is real — run_ids 32cc27f9/847964a6 and 6 flatline races
- No artifact fix changes that

## Governance Note

`PASS_TO_LEARNING` means the council sees no blocking conditions on these days. It does **not** mean learning consume is automatic. Operator decision required before any consumption.

`sigma_audits` truth rows were preserved on all 3 days regardless of council verdict.

## Fix Applied

`run_results_sigma.py` now writes `data/sigma_results/sigma_results_{date}.json` after every sigma close. This is a mirror artifact — it does not affect sigma_audits writes to Supabase.

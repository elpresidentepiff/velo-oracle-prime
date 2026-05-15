# VELO Mission Control V1

## Purpose
Mission Control is the read-only operator cockpit. It summarizes the current day, the safety state, and the next safe command without mutating predictions or learning state.

## Command
```powershell
python scripts/velo_mission_control.py --date YYYY-MM-DD
```

## Outputs
- `data/mission_control/latest.json`
- `data/mission_control/YYYY-MM-DD_mission_control.json`
- readable CLI summary

## Inputs
- `data/velo_prime_verdicts_YYYY_MM_DD.json`
- `data/velo_daily_run_truth_YYYY_MM_DD.json`
- `data/racecard_merged/racecard_*_YYYY-MM-DD.json`
- `data/cashrun_report_YYYY_MM_DD.md`
- `data/reports/rp_velo_convergence_YYYY-MM-DD.json` if present
- `data/phase4_daily_reports/YYYY-MM-DD_daily_eod_report.json` if present
- read-only Supabase tables:
  - `velo_job_runs`
  - `sigma_audits`
  - `velo_learning_events`
  - `learned_patterns`

## Current Fields
- prediction status and count
- VP30 count
- MDS-high count
- improvement-high count
- Racing Post race and horse coverage
- CASHRUN bucket summary
- convergence status
- Sigma status
- learning readiness
- approved shadow target
- shadow race count
- live state hash
- cloud backup timestamp
- consumed_live count
- repo dirty yes/no
- forbidden file drift yes/no
- next safe command
- blocked reason

## Thresholds
- `VP30`: `velo_prime_prob >= 0.30`
- `MDS_HIGH`: `market_deception_score > 0.50`
- `IMPROVEMENT_HIGH`: `improvement_score >= 0.20`

## Read-Only Contract
Mission Control must never:
- write predictions
- write learning events
- write live state
- mutate cloud backup
- run EOD

It may only write its own local status artifacts.

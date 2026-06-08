# VÉLØ Race-Day Button Layout

This is the operator path for turning race-day prep into one repeatable action.

## Command

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONPATH='.'; python scripts/ops/velo_race_day_button.py --date 2026-06-05
```

## Sequence

1. Parse the Racing Post account capture and write the standard cache.
2. Build `data/racecard_merged/racecard_*_{date}.json` for Old VÉLØ.
3. Run Old VÉLØ from RP merged files with Telegram suppressed.
4. Refresh New Build current-card Passport feed.
5. Run New Build two-lane scorer.
6. Write one operator report.

## Reports

- `data/reports/race_day_button_YYYY_MM_DD_latest.md`
- `data/reports/race_day_button_YYYY_MM_DD_latest.json`
- `data/reports/racecard_cache_gate_latest.md`
- `data/new_build/reports/two_lane_readiness_YYYY_MM_DD.md`

## Safety Rules

- Old VÉLØ safety gates remain authoritative.
- Telegram is suppressed by default.
- New Build remains paper-only.
- No staking.
- No RPR/SP leakage override.
- If Old VÉLØ blocks on metadata coverage, do not force scoring. Repair the data source.

## June 5 Known State

Old VÉLØ card loading is exact, but the metadata gate blocks because RP runners only have jockey data on about one third of runners. New Build is ready through `LANE_A_CORE_PASSPORT` with 100% Passport coverage.

# New Build VELO Archive Pipeline

- Classification: `NEW_BUILD_ARCHIVE_PIPELINE_READY`
- Mode: `RUN`
- Date range: `2026-05-26` to `2026-05-27`
- Trust policy: `ARCHIVE_CONTEXT_ONLY_NOT_SCORING`
- RPR policy: `RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`
- Live VELO touched: `false`
- Shadow VELO touched: `false`

## Totals

- races: `15`
- runners: `161`
- horse_profiles: `161`
- horse_dossiers: `161`
- race_dossiers: `15`

## Planned Steps

- `horse-dossiers-2026-05-26`: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python scripts/ops/build_rp_horse_dossiers.py --date 2026-05-26 --execute`
- `race-dossiers-2026-05-26`: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python scripts/ops/build_rp_race_dossiers.py --date 2026-05-26 --execute`
- `horse-dossiers-2026-05-27`: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python scripts/ops/build_rp_horse_dossiers.py --date 2026-05-27 --execute`
- `race-dossiers-2026-05-27`: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python scripts/ops/build_rp_race_dossiers.py --date 2026-05-27 --execute`
- `identity-bridge`: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python scripts/ops/build_horse_identity_bridge.py --start-date 2026-05-26 --end-date 2026-05-27 --execute`
- `source-value-matrix`: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python scripts/ops/build_source_value_matrix.py --all-built --execute`
- `outcome-bridge`: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python scripts/ops/build_rp_archive_outcome_bridge.py --execute`
- `rpr-boundary-audit`: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python scripts/audit_rpr_scoring_boundary.py`
- `archive-advantage-analysis`: `/mnt/c/Users/puror/velo-oracle-prime/venv/bin/python scripts/analysis/analyze_rp_archive_advantage.py --from-date 2026-05-26 --to-date 2026-05-27`

## Results

- `horse-dossiers-2026-05-26`: `PASS`
- `race-dossiers-2026-05-26`: `PASS`
- `horse-dossiers-2026-05-27`: `PASS`
- `race-dossiers-2026-05-27`: `PASS`
- `identity-bridge`: `PASS`
- `source-value-matrix`: `PASS`
- `outcome-bridge`: `PASS`
- `rpr-boundary-audit`: `PASS`
- `archive-advantage-analysis`: `PASS`

# New Build Result Gap Plan

- Bridge dates: 2026-05-24, 2026-05-25, 2026-05-26, 2026-05-27, 2026-05-28, 2026-05-29
- Result date range: 2026-03-15 to 2026-05-25
- Missing result dates: 2026-05-26, 2026-05-27, 2026-05-28, 2026-05-29
- Recommended next step: CAPTURE_OR_IMPORT_MISSING_RESULT_FILES

## Commands After Raw Result Files Exist
- `python scripts/ops/new_build_sources.py ingest-results --date 2026-05-26 --execute`
- `python scripts/ops/new_build_sources.py ingest-results --date 2026-05-27 --execute`
- `python scripts/ops/new_build_sources.py ingest-results --date 2026-05-28 --execute`
- `python scripts/ops/new_build_sources.py ingest-results --date 2026-05-29 --execute`

Then rerun:
- `python scripts/ops/new_build_database.py build-normalized --execute`
- `python scripts/ops/new_build_outcome_bridge.py --execute`
- `python scripts/ops/new_build_database.py sandbox-learn --execute`
- `python scripts/ops/new_build_evaluate.py --execute`

Live VELO untouched. Shadow VELO untouched.

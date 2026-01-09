# Prefect Daily Pipeline

## Overview

The `daily_meeting_pipeline` orchestrates the complete daily racing data pipeline with enforced logging. Every step emits log markers (`BOOT`, `STEP X`, `DONE`) to ensure visibility and auditability.

**No silent runs allowed.** All failures include stacktraces.

## Architecture

The pipeline consists of 6 steps:

1. **Ingest PDFs** - Download and register racing PDFs
2. **Parse & Validate** - Parse meeting data and run validation gates
3. **Insert to Supabase** - Write validated data to database
4. **Build Feature Mart** - Compute deterministic trainer/jockey stats
5. **Run Phase 2A Analysis** - Generate predictions using analytical engine
6. **Persist Outputs** - Save predictions and reports

## Local Testing

### Quick smoke test
```bash
bash scripts/smoke_prefect_daily.sh
```

### Direct Python execution
```bash
python flows/daily_pipeline.py 2026-01-09
```

Or with default date:
```bash
python flows/daily_pipeline.py
```

### Expected log output
```
BOOT flow start as_of_date=2026-01-09
STEP 1 ingest start
STEP 1 ingest done batch_id=...
STEP 2 parse_validate start
STEP 2 parse_validate done status=VALID
STEP 3 supabase_insert start
STEP 3 supabase_insert done
STEP 4 build_feature_mart start
STEP 4 build_feature_mart done
STEP 5 phase2a start
STEP 5 phase2a done
STEP 6 persist_outputs start
STEP 6 persist_outputs done
DONE flow complete
```

## Debugging

If flow runs silently (no logs):

1. Check `PREFECT_LOGGING_LEVEL=INFO` is set
2. Verify `log_prints=True` in `@flow()` decorator
3. Run smoke test: `bash scripts/smoke_prefect_daily.sh`

Logs are written to `/tmp/velo_prefect_run.log`

## CI Integration

The pipeline includes a CI smoke test (`.github/workflows/prefect-smoke.yml`) that:

- Runs on PR changes to `flows/`, `workers/ingestion_spine/`, `app/engine/`
- Executes the flow locally (no Prefect Cloud required)
- Validates that `BOOT` and `DONE` log markers are present
- Uploads logs as artifacts on failure

## Task Functions

All tasks include entry/exit logging:

- `ingest_pdfs(as_of_date)` - Ingest PDFs for date
- `parse_and_validate(batch_id, as_of_date)` - Parse and validate meeting
- `insert_to_supabase(batch_id, meeting)` - Insert to database
- `build_feature_mart(as_of_date)` - Build feature mart
- `run_phase2a_analysis(as_of_date)` - Run analytical engine
- `persist_outputs(batch_id, analysis_result)` - Persist predictions

## Error Handling

Every step is wrapped in try/except blocks with `logger.exception()` to ensure:

- Errors are logged with full stacktrace
- Flow fails fast on any error
- Validation failures trigger rejection workflow

## Configuration

Required environment variables:

- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key for database access
- `PREFECT_LOGGING_LEVEL` - Set to `INFO` for full visibility (optional)

## Smoke Test Validation

The smoke test verifies:

✅ Flow boots (`BOOT flow start` in logs)  
✅ Flow completes (`DONE` in logs)  
✅ No silent failures

If any marker is missing, the smoke test fails and CI blocks the PR.

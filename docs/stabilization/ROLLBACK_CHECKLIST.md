# ROLLBACK VERIFICATION CHECKLIST

Use this checklist after performing a rollback to ensure the system has returned to a healthy baseline.

## 1. Core API Health
*   [ ] `GET /health` returns `200 OK` with status `"healthy"`.
*   [ ] `GET /api/runtime-truth` returns consistent metadata (commit SHA, active paths).

## 2. Safety Enforcement
*   [ ] `GET /api/runtime-truth` shows `forbidden_import_check: PASS`.
*   [ ] Startup logs do NOT contain `CRITICAL` or `RuntimeError` related to live modes.
*   [ ] Verify `VELO_EXECUTION_MODE` is set to `PAPER` or `ARCHIVE`.

## 3. Pipeline Readiness
*   [ ] `python app/pipelines/score_daily_runner.py --date 2026-06-02` (dry-run if possible) starts correctly.
*   [ ] `python app/pipelines/sigma_runner.py --date 2026-06-02` starts correctly.
*   [ ] Latest `PASS` run is visible in the `pipeline_runs` table in Supabase.

## 4. Model Integrity
*   [ ] SQPE v17 model artifact is loadable (check `/health` for `sqpe_model: LOADED`).
*   [ ] G state is loaded (`G state loaded at startup` in logs).

## 5. Dashboard Data
*   [ ] `http://localhost:8080/dashboard?date=2026-06-02` loads and displays racecards.
*   [ ] Stacks are populated and aligned.

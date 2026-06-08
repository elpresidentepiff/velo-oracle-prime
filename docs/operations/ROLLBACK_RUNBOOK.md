# ROLLBACK RUNBOOK

Procedures for emergency system restoration after a failed stabilization or model deploy.

## 1. Triggering a Rollback
A rollback is mandatory if:
*   `/health` returns `FAIL` for > 15 minutes.
*   Scoring produces `NaN` or `0.000` probabilities for an entire card.
*   Execution mode defaults to `LIVE` in a restricted environment.
*   The `smoke_test.py` suite fails in CI/CD.

## 2. Fast Code Rollback (Git)
```powershell
# Revert to last known good commit
git checkout main
# Or hard reset if on a broken branch
git reset --hard HEAD~1
```

## 3. Configuration Rollback (Environment)
Restore these defaults if experimental flags were enabled:
*   `VELO_ENABLE_CANONICAL_PIPELINE_WRAPPERS=0`
*   `VELO_STRICT_SCRIPT_PATH_VALIDATION=0`
*   `VELO_ENSEMBLE_PROFILE=LEGACY_FULL`

## 4. Post-Rollback Verification
Follow the `docs/stabilization/ROLLBACK_CHECKLIST.md`:
1.  Verify `/health` is `healthy`.
2.  Verify `/api/runtime-truth` returns consistent metadata.
3.  Run a scoring dry-run: `python app/pipelines/score_daily_runner.py --date 2026-06-02`.

## 5. Escalation
If a software rollback fails to restore health, the issue is likely **Infrastructure (Railway)** or **Data Truth (Supabase)**.
*   Check Supabase for schema drift.
*   Check Railway logs for OOM or network timeouts.

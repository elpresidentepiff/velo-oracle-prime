# OPERATOR RECOVERY NOTES

Step-by-step instructions for resolving common stabilization failures.

## 1. Trigger Path Failure
**Symptoms:** FastAPI returns 500 error: `Scoring script not found`.
**Fix:**
1. Check `docs/stabilization/RUNTIME_TRUTH_MAP.md` for canonical paths.
2. Verify the script exists at `app/pipelines/<runner_name>.py`.
3. If missing, restore from `docs/stabilization/snapshots/` or re-checkout the branch.

## 2. Unsafe Mode Failure
**Symptoms:** App fails to start with `RuntimeError: [startup] BLOCKED: ...=LIVE is forbidden`.
**Fix:**
1. Check Railway/Local environment variables.
2. Ensure `VELO_EXECUTION_MODE`, `BETFAIR_MODE`, and `VELO_G_SHADOW_MODE` are all set to `PAPER` or `shadow`.
3. Restart the service.

## 3. Duplicate Pipeline Lock
**Symptoms:** Trigger returns 409 `already_running`.
**Fix:**
1. Check the `pipeline_runs` table in Supabase.
2. If a run is stuck in `running` state but no process exists, manually patch the row to `FAIL` or `CANCELLED`.
3. Retry the trigger.

## 4. Forbidden Import Failure
**Symptoms:** App fails to start with `RuntimeError: [startup] BLOCKED: Safety violation detected...`.
**Fix:**
1. Run `python app/core/safety_guards.py` to identify the offending file and import.
2. Remove the `import` of `betfair_execution_agent` or `betfair_trading_agents` from the live path.
3. Live paths must use `execution_bridge.py` for all simulator/trading interactions.

## 5. Rollback to Previous Commit
**Command:**
```powershell
git checkout main
# or
git reset --hard <commit_sha>
```
Follow the `ROLLBACK_MANIFEST.md` for environment restoration.

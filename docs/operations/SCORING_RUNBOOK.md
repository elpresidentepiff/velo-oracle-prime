# SCORING RUNBOOK

Guidelines for executing and verifying daily race scoring.

## 1. When to Run
*   **Target:** Daily between 08:30 and 10:30 UTC.
*   **Trigger:** Automated via GitHub Actions, or manual via FastAPI.

## 2. Manual Execution (Emergency/Retry)
```powershell
# Using the canonical pipeline wrapper
python app/pipelines/score_daily_runner.py --date 2026-06-02
```

## 3. Verification Steps
1.  **Console Output:** Check for `[PASS]` on all preflight gates.
2.  **API Health:** `GET /health` should return `healthy`.
3.  **Database:** Verify new rows in the `velo_verdicts` table for today's date.
4.  **Dashboard:** `http://localhost:8080/dashboard` should display populated racecards and stacks.
5.  **Summary:** Check `data/new_build/summaries/score_daily_YYYY_MM_DD.json`.

## 4. Failure Conditions
*   **`BLOCKED_NO_DATA`**: Racecard capture for today is missing or invalid.
*   **`RUNTIME_ERROR`**: Model failed to load or database is unreachable.
*   **`GATE_FLATLINE`**: Input features are degraded; scoring proceeds in `VISION_ONLY` mode.

## 5. Recovery
1.  If data is missing, re-run `scripts/ops/parse_racing_post_racecard_capture.py --date YYYY-MM-DD --execute`.
2.  If database is down, check `data/velo_prime_verdicts_YYYY_MM_DD.json` for local backup.

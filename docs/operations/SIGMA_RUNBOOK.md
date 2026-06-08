# SIGMA RUNBOOK

Guidelines for post-race reconciliation and performance audit.

## 1. When to Run
*   **Target:** Daily after 22:00 UTC (once all results are declared).
*   **Trigger:** Automated nightly cron, or manual via FastAPI.

## 2. Manual Execution (Emergency/Retry)
```powershell
# Using the canonical pipeline wrapper
python app/pipelines/sigma_runner.py --date 2026-06-02
```

## 3. Verification Steps
1.  **Console Output:** Check for `[NR]` (Non-Runners) and `WIN/MISS` outcomes.
2.  **Database:** Verify new rows in the `sigma_audits` table.
3.  **Provenance:** Ensure `reconciliation_provenance` shows `MATCH_EXACT_ID` where possible.
4.  **Summary:** Check `data/new_build/summaries/sigma_YYYY_MM_DD.json`.

## 4. Failure Conditions
*   **`NO_RESULTS`**: Scraped results from ATR/SL are not yet available.
*   **`UNRESOLVED_MATCH`**: High-confidence ID match failed; fallback to name match required manual review.
*   **`SUPABASE_ERROR`**: Outcome persistence failed.

## 5. Recovery
1.  If results are missing, run `scripts/ops/scrape_results_atr.py --date YYYY-MM-DD`.
2.  If matching is brittle, review `docs/stabilization/RECONCILIATION_PROVENANCE_MAP.md`.

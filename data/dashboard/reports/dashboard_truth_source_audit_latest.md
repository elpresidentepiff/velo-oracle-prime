# Dashboard Truth Source Audit

Generated: 2026-06-03 | Status: DRAFT | Author: Codex

## 1. Entrypoints
The dashboard is served via FastAPI from `app/main.py` at `/dashboard`. It serves a large static HTML file `app/static/dashboard/index.html`.

## 2. API Endpoints & Data Sources
| Endpoint | Type | Read Source | Stale Risk |
| :--- | :--- | :--- | :--- |
| `sidecar_stack_latest.json` | Static JSON | Local File | **HIGH** (Manual script needed) |
| `window.__SSC_INLINE` | Injected | Hardcoded HTML | **CRITICAL** (Fixed 2026-05-29) |
| `/api/governed-card` | Dynamic | Local Verdicts + Supabase | LOW |
| `/api/v1/system/diagnostics` | Dynamic | ModelManager + Stubs | MEDIUM |

## 3. Panel Audit
- **DAILY_STATUS_CARDS:** Mixed. Most values are hardcoded in the HTML structure.
- **DAILY_LEARNING_LOOP:** **STALE**. Hardcoded labels and "OK" indicators.
- **VÉLØ SIGNAL STACK:** **STALE**. Dependent on `sidecar_stack_latest.json`.
- **SIGNAL HEATMAP:** **STALE**. Dependent on `sidecar_stack_latest.json`.

## 4. Safest Read-Only Truth Sources
To restore truth to the dashboard, the following sources should be used via a new Truth Summary API:
- **Live Run State:** `data/velo_run_observability_{date}.json`
- **Races/Runners Scored:** `data/velo_prime_verdicts_{date}.json`
- **Persistence:** Real-time query to Supabase `pipeline_runs` table.
- **New Build State:** `data/new_build/reports/two_lane_readiness_{date}.json`
- **Sigma Accuracy:** `data/sigma_results/sigma_results_{latest}.json`

## 5. Conclusion
The current dashboard is primarily "decorative" or dependent on manual sync scripts. It poses a risk of surfacing stale data from 2026-05-29. Phase 1 will implement a direct truth-summary API to bypass these stale layers.

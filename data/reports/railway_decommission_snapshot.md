# Railway Decommission Snapshot — 2026-06-11
Access: Railway API token DEAD (403); no CLI session. Snapshot from env-topology, repo config, probes. **Service-level disable/delete is OPERATOR_DASHBOARD work — exact steps below.**

| Target | Known state | Volume | Supabase cred class | Writes? | Rollback |
|---|---|---|---|---|---|
| hermes-agent | service exists (env URL: RAILWAY_SERVICE_HERMES_AGENT_URL); purpose not in this repo (media/podcast agent per name + OpenRouter TTS keys) | **YES** (RAILWAY_VOLUME_* in its env) | **SERVICE_ROLE** | unknown — no recent writers traceable to it in audited tables (all recent writes account to operator box) | redeploy + volume restore — **export volume before delete** |
| velo-oracle | public domain 502-DEAD; start `uvicorn app.main:app`; required-for-June-11: **NO** (manual chain) | no | service key, TRIGGER_SCORE_SECRET | dormant (dead) | redeploy from repo (railway.toml) |
| GH smoke-prod schedule | **DISABLED 2026-06-11 (disabled_manually)** — was 48 fails/day | — | none | no | `gh workflow enable smoke-prod.yml` |
| GH score-daily schedule | **DISABLED 2026-06-11 (disabled_manually)** — was 2 fails/day into 502 | — | none (HTTP trigger only) | no | `gh workflow enable score-daily.yml` |

## Operator dashboard sequence (hermes-agent): 
1) open service → Metrics/Logs: note last activity timestamp → screenshot 2) Settings → copy service ID + env var NAMES 3) Volume → download/export contents 4) Remove cron/sleep the service (scale to zero / pause) → status HERMES_AGENT_DISABLED_PENDING_DELETE 5) wait 48h across June 11–12 race days; if nothing breaks → delete after explicit approval.
## velo-oracle: pause/park (it serves 502 anyway) → VELO_ORACLE_PARKED_PENDING_DELETE → same 48h soak → delete or revive per topology decision.
## PACKET_ITEM_3 (enchanting-exploration): **OPERATOR_HOLD — untouched** per instruction.

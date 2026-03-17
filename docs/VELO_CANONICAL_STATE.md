# VÉLØ Oracle Prime — Canonical State Document
> Written 2026-03-17. This file is law. Do not improvise around it.

---

## 1. Canonical Repo

```
elpresidentepiff/velo-oracle-prime
```

**NOT** `elpresidentepiff/velo-oracle` — that is the old renamed repo. Any Railway service, trigger, or reference pointing at `velo-oracle` is STALE and must be corrected.

---

## 2. Canonical Branch

```
feature/v10-launch
```

This is the branch Railway currently tracks via deployment trigger. `main` is in sync with it. If/when you switch the canonical tracking branch, update this file and the Railway trigger simultaneously.

---

## 3. Canonical Production Railway Service

```
Service name: velo-oracle
Service ID:   0992976e-a59d-4cc8-a51f-76e330057493
Project:      sincere-empathy (37d7f632-b248-4d7a-91ba-e860d1151c90)
Environment:  production (4d829a93-1cea-4211-8e62-e229288fefb1)
Domain:       https://velo-oracle-production.up.railway.app
```

**Post-incident state (resolved 2026-03-17T14:25 UTC):**
- Deployment trigger: `elpresidentepiff/velo-oracle-prime` ✓ (was wrong repo, fixed)
- Tracked branch: `feature/v10-launch` ✓
- startCommand: `bash start.sh` ✓ (was `$PORT` literal, fixed)
- `start.sh` in repo root: `exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"` ✓
- STATUS: **LIVE** — all 3 proof checks passing as of 2026-03-17T14:25 UTC

---

## 4. Canonical Ingestion Service

```
Service name: ingestion-spine
Service ID:   b9a52e75-6d98-4077-98d0-d9e68b16033e
Project:      sincere-empathy
Repo:         elpresidentepiff/velo-oracle-prime (CORRECT)
rootDirectory: workers/ingestion_spine
startCommand: python -u -m uvicorn ingestion_spine.main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level info
Health:       /healthz
Status as of 2026-03-17: CRASHED — believed to be Railway EU West platform incident
```

Do not attempt to fix ingestion-spine during Railway EU West incidents. Check incident banner first.

---

## 5. Canonical Prediction Endpoint

```
POST https://velo-oracle-production.up.railway.app/api/v1/predict/race
```

This route is defined in `app/main.py` at commit `cf782c9` and later. It requires `runners` list in the request body and returns `velo_prime_prob` for each runner.

Quick-check: `GET /openapi.json` must include `/api/v1/predict/race` in `paths`. If it does not, the correct code is NOT running regardless of build status.

---

## 6. Canonical Start Command

```bash
bash start.sh
```

Where `start.sh` (repo root) contains:
```bash
#!/bin/bash
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
```

This is the only way to correctly expand `$PORT` in RAILPACK. The server-side `startCommand` in Railway is set to `bash start.sh`. Do not change it back to an inline uvicorn command with `$PORT`.

---

## 7. 10am Race Workflow

```
FETCH   → workers/racing_api_fetcher.py  (Standard API, Basic Auth)
NORMALIZE → workers/racing_api_normalizer.py  (canonical schema)
SCORE   → app/services/velo_prime_service.py  (SQPE v17 + specialists + macro)
SUGGEST → send via Telegram (scripts/run_todays_races.py)
STOP    ← do not continue into results reconciliation at this time
```

**Hard rules:**
- Do not mix deploy surgery with race-day operations.
- Run `--smoke` flag first on a single race before full card.
- No Telegram until smoke test passes cleanly.

---

## 8. Results Reconciliation Workflow

```
WAIT    → after all races complete
RESULTS → fetch via Racing API results endpoint
RECONCILE → compare predictions vs actuals
SIGMA   → update sigma loop (scripts/sigma_loop_closer.py)
LEARN   → update learned_patterns in Supabase if pattern confirmed
```

This is a separate workflow. Never triggered automatically. Never mixed with 10am.

---

## 9. Deploy Proof Rule

**STATUS = DEPLOYED only when ALL of the following are true:**

| Check | Must Be |
|---|---|
| local SHA | == remote SHA == Railway deployed SHA |
| Railway repo target | `elpresidentepiff/velo-oracle-prime` |
| Railway tracked branch | explicitly known (currently `feature/v10-launch`) |
| `/health` | `{"status": "ok"}` |
| `/openapi.json` contains `/api/v1/predict/race` | `true` |
| `POST /api/v1/predict/race` | returns `velo_prime_prob` in response |

If **any one** fails: **STATUS = NOT DEPLOYED**.

A build saying `SUCCESS` means nothing without route proof.

---

## 10. Railway Services — Labels

| Service | ID | Repo | Status | Label |
|---|---|---|---|---|
| `velo-oracle` | `0992976e` | `velo-oracle-prime` (fixed 2026-03-17) | LIVE — velo_prime_v1 proven @ 14:25 UTC | **LIVE — PRIMARY — USE THIS** |
| `velo-oracle-prime` | `e48d14ce` | `velo-oracle-prime` | SKIPPED | **LEGACY — DO NOT USE (duplicate, never had clean deploy)** |
| `enchanting-exploration` | `cfd844fb` | `velo-oracle` (WRONG REPO) | SUCCESS | **LEGACY — DO NOT USE (wrong repo, orphaned)** |
| `ingestion-spine` | `b9a52e75` | `velo-oracle-prime` | CRASHED | **LIVE — INGESTION — PLATFORM INCIDENT** |

---

## 11. Known Failure Causes (never forget these)

1. **Wrong Railway repo target** — trigger pointed at `velo-oracle` not `velo-oracle-prime`. Fixed 2026-03-17.
2. **Stale Railway webhook/commit index** — Railway does not know about pushes unless webhook fires. After rename from `velo-oracle` → `velo-oracle-prime`, webhook was broken for months.
3. **Stale server-side startCommand** — Railway API ignores `null` to clear startCommand. Must set to explicit working value.
4. **RAILPACK does not shell-expand `$PORT`** — must use `bash start.sh` wrapper.
5. **`feature/v10-launch` is GitHub default branch** — Railway always deploys from GitHub default, not `main`, unless trigger is explicitly configured.
6. **"Build SUCCESS" is not proof** — only `/openapi.json` route presence + endpoint response is proof.
7. **Supabase key alias** — `.env` has `SUPABASE_SERVICE_KEY`; code expects `SUPABASE_SERVICE_ROLE_KEY`. Both must exist in `.env`.
8. **Railway EU West incidents** — check incident banner before attributing deploy failures to code.

---

## 12. Canonical Env Keys (must exist in .env)

```
SUPABASE_URL
SUPABASE_SERVICE_KEY         # primary
SUPABASE_SERVICE_ROLE_KEY    # alias — same value
RACING_API_USERNAME
RACING_API_PASSWORD
RAILWAY_TOKEN
RAILWAY_PROJECT_ID=37d7f632-b248-4d7a-91ba-e860d1151c90
ANTHROPIC_API_KEY            # MISSING — add before using Claude chain
```

---

---

## 13. Rollback Anchor

```
Last proven-good deployment ID: a340bf86-2df0-42d2-b16f-8ed0ef76346f
Deployment timestamp:           2026-03-17T11:36:46 UTC
Railway branch at time:         feature/v10-launch
Proof confirmed:                2026-03-17T14:25 UTC (post-EU-West-incident)
```

**Rollback rule:** If any newer deploy fails the 6-point proof check, immediately rollback to the anchor using:
```
deploymentRedeploy(id: "a340bf86-2df0-42d2-b16f-8ed0ef76346f")
```

SHA parity is secondary to live proof. A deployment is LIVE only if `scripts/deploy_proof_check.py` passes.

**10am rule:** Do NOT mix deploy surgery with race-day operations. Run `scripts/preflight_10am_check.py` before 10am workflow. If it fails, fix the problem — do not run predictions against a broken endpoint.

---

*Last updated: 2026-03-17T14:30 UTC — STATUS: LIVE. Rollback anchor set. All 3 proof checks passing. Stale text removed. VELO_WORKFLOW_LOCK.md and VELO_INCIDENT_LOG.md created.*

# VÉLØ Incident Log
> Append new incidents at the bottom. Never delete entries.

---

## Incident Format

```
## INC-NNNN — YYYY-MM-DD — <one-line title>
**Status:** RESOLVED / ONGOING
**Detected:** YYYY-MM-DDTHH:MM UTC
**Resolved:** YYYY-MM-DDTHH:MM UTC (or ONGOING)
**Impact:** <what was broken>
**Root cause:** <why>
**Fix:** <what was done>
**Prevention:** <what doc/check now prevents recurrence>
```

---

## INC-0001 — 2026-03-17 — Railway deployment trigger pointed at wrong repo

**Status:** RESOLVED
**Detected:** 2026-03-17T09:00 UTC (approximate — 404 on /api/v1/predict/race)
**Resolved:** 2026-03-17T11:36 UTC (rollback anchor deployment confirmed live)
**Impact:** `/api/v1/predict/race` returned 404. Production was serving stale code from before VeloPrimeEnsemble wiring. All predictions during this window were from old code.
**Root cause (multi-factor):**
1. GitHub repo renamed from `velo-oracle` → `velo-oracle-prime` long ago. Railway deployment trigger was never updated — remained pointing at `velo-oracle`. GitHub webhook silently stopped delivering to Railway.
2. Railway's internal commit index frozen at stale code. `serviceInstanceDeploy(latestCommit: true)` deployed from frozen stale snapshot.
3. GitHub default branch is `feature/v10-launch` not `main`. All new commits on `main` were invisible to Railway even after trigger was eventually fixed.
4. RAILPACK does not shell-expand `$PORT` in `startCommand`. Inline uvicorn command crashed with "not a valid integer".
5. `serviceInstanceUpdate startCommand: null` is silently ignored by Railway API.
**Fix:**
- Updated deployment trigger repo: `velo-oracle` → `velo-oracle-prime`
- Updated deployment trigger branch: `feature/v10-launch`
- Created `start.sh` with `exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"`
- Set Railway server-side `startCommand = bash start.sh`
- Pushed new commit to fire fresh webhook
- After new deploy crashed (stale snapshot race condition), rolled back to: `a340bf86-2df0-42d2-b16f-8ed0ef76346f`
- Proof confirmed at 2026-03-17T14:25 UTC: all 3 checks passing
**Prevention:**
- `docs/VELO_CANONICAL_STATE.md` — canonical infrastructure truth document
- `docs/VELO_DEPLOY_PROOF_RULE.md` — 6-point deploy proof rule
- `scripts/deploy_proof_check.py` — automated proof check script
- `scripts/preflight_10am_check.py` — pre-race preflight gate
- Rollback anchor documented in canonical state doc

---

## INC-0002 — 2026-03-17 — Railway EU West platform incident

**Status:** RESOLVED
**Detected:** 2026-03-17 (during INC-0001 investigation)
**Resolved:** 2026-03-17T~14:00 UTC (approximate — Railway incident cleared)
**Impact:** `ingestion-spine` service CRASHED. Deploy operations unstable.
**Root cause:** Railway EU West platform incident (external — not VÉLØ code).
**Fix:** Waited for Railway incident to clear. Did not attempt code fixes during incident.
**Prevention:** `docs/VELO_DEPLOY_PROOF_RULE.md` — Railway Incident Rule section: check incident banner before attributing failures to code.

---

## INC-0003 — 2026-03-17 — ingestion-spine crashing on startup (SyncBucket bug)

**Status:** RESOLVED
**Detected:** 2026-03-17T15:00 UTC (log analysis after EU West incident cleared)
**Resolved:** 2026-03-17T15:10 UTC (/healthz confirmed ok)
**Impact:** `ingestion-spine` failed to start on every boot. Was misattributed to Railway EU West platform incident in INC-0002. Actual cause was a code bug.
**Root cause:** `workers/ingestion_spine/storage.py` line 45:
```python
bucket_names = [b['name'] for b in buckets]
```
`supabase-py` v2+ returns `SyncBucket` objects from `list_buckets()`, not plain dicts. Subscripting with `['name']` raises `TypeError: 'SyncBucket' object is not subscriptable`. The app crashed during lifespan startup before serving any requests.
**Fix:** Changed to `b.name if hasattr(b, 'name') else b['name']` — handles both object and dict return types.
- Commit: `9459110` on `feature/v10-launch`
- Deployed: Railway build `36c3dc27`
- Proof: `/healthz` → `{"status":"ok","service":"velo-ingestion-spine"}` @ 2026-03-17T15:10 UTC
**Prevention:**
- This bug existed since ingestion-spine was first written. It was previously masked because Railway EU West incident caused the service to appear down for platform reasons.
- Lesson: always read startup logs to completion before attributing crashes to platform incidents.

---

*Last updated: 2026-03-17T15:10 UTC*

# RAILWAY DASHBOARD DECOMMISSION — OPERATOR STEPS

**Date:** 2026-06-11 · API token dead → these are click-by-click dashboard steps. Order matters.

## A. hermes-agent (service-role key holder, has volume)
1. railway.app → project `sincere-empathy` → **hermes-agent** → Logs: note last activity timestamp (screenshot).
2. Settings: copy Service ID; record env var **names** (values stay where they are).
3. **Volume tab → download/export contents BEFORE anything else.** Unknown data = manifest first.
4. Settings → **pause/remove deploy (scale to zero)**. Status: `HERMES_AGENT_DISABLED_PENDING_DELETE`.
5. **Soak 48h across June 11–12 race days.** If sigma/Telegram/podcast/anything breaks, it tells us what hermes did.
6. After clean soak → Delete service. (Volume export is your rollback.)

## B. velo-oracle (502-dead)
1. Service → Settings → Networking: **remove the public domain** (nothing healthy answers it anyway; GH triggers already disabled).
2. Pause/scale to zero. Status: `VELO_ORACLE_PARKED_PENDING_DELETE`.
3. Same 48h soak → delete, **or** keep parked if you choose the Railway-orchestrator option later (it would be a fresh service anyway — parking ≠ keeping).

## C. enchanting-exploration (duplicate — your "likely delete after confirmation")
1. Logs: confirm no recent activity beyond crash/idle. 2. Pause. 3. Delete after the same soak — it shares velo-oracle's code and DB; nothing references it by name in the repo.

## D. velo-prime-scoring (dormant) + ingestion-spine (legacy, HOLD)
- velo-prime-scoring: pause; delete OR fold into the future clean orchestrator decision — don't rebuild on it.
- ingestion-spine: **HOLD** until provenance check (it's the only thing CI tests; PDF parsing now happens locally). Pause is safe; no delete yet.

## E. Verify the quiet
GH schedules `smoke-prod` + `score-daily`: **already disabled (verified `disabled_manually`)** — Actions tab should show zero scheduled fires from tonight. After pausing services, Railway usage graph should flatline → your next invoice shows what the zombies were costing.

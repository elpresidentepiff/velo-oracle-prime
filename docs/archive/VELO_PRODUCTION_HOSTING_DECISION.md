# PRODUCTION HOSTING DECISION

**Date:** 2026-06-11 · Operator law: current Railway topology REJECTED. Never five services again.

## The lean stack (decided)
| Layer | Choice | Why |
|---|---|---|
| Scheduled compute | **GitHub Actions first** | free-tier scheduled runners, zero always-on cost, secrets vault built in, run history = audit log |
| Database | **Supabase** (unchanged) | system of record, proven by the persistence loop |
| Always-on (only if needed) | **ONE Railway service later** (`velo-orchestrator`) | only for dashboard/API/Telegram-approval webhook — things that must listen 24/7 |
| Emergency/manual engine | **Local WSL** | stays the operator engine; June 11 runs here |

## Option A — GitHub Actions first (RECOMMENDED, adopt after June 11 proves clean)
Workflows (all proof-gated, all artifact-uploading): morning preflight + attach preflight (~07:30) · dry-run scoring + feature health report (~08:30) · **operator approval gate** (manual `workflow_dispatch` with the real run) · evening closeout (capture→sigma→ingest→MC→proofs, ~21:30) · nightly loop-health report. Each job ends by writing its proof artifact; a failed proof fails the job loudly. Needs: repo secrets (post-rotation keys), Playwright session strategy for capture (the one open question — RP login state on a runner; fallback = capture stays local, everything else automates).
## Option B — Railway one-orchestrator
Spec: `RAILWAY_CLEAN_ORCHESTRATOR_SPEC.md`. Adopt only when an always-on surface is actually wanted (dashboard, Telegram approval bot, webhooks).
**Sequence: June 11 local → adopt A incrementally (closeout first, capture last) → B only when the product needs a 24/7 face.**

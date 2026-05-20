# VÉLØ Infrastructure, CI, and Rollback Audit V1

**Date:** 2026-05-05

## 1. Current State Classification

| Component | Status | Details |
|---|---|---|
| Infrastructure as Code | **PRESENT_ACTIVE** | `Dockerfile`, `docker-compose.yml`, `railway.toml` exist and are used. |
| CI/CD Pipeline | **PRESENT_ACTIVE** | GitHub Actions (`.github/workflows/`) run CI, smoke tests, and daily jobs. |
| Database Migrations | **PRESENT_ACTIVE** | `alembic/` is configured for PostgreSQL schema management. |
| App Rollback | **PRESENT_ACTIVE** | Railway allows UI-based point-in-time deployment rollbacks. |
| DB Rollback | **PRESENT_PARTIAL** | `alembic downgrade` exists, but Supabase data rollback is complex. |
| Backups | **UNKNOWN** | Supabase managed backups assumed, but no explicit scripts found. |

## 2. Core Audit Questions Answered

**A. Do we have infrastructure as code?**
Yes. Environment definition is handled via `railway.toml` (Nixpacks builder) and standard `Dockerfile`.

**B. Do we have CI/CD?**
Yes. GitHub Actions automatically run checks (`ci.yml`, `smoke-prod.yml`). Merges to `main` trigger Railway deployments.

**C. What tests run before deploy?**
Unit tests, structural checks, and smoke tests against non-production data.

**D. Can we rollback app deploys?**
Yes. Reverting a commit in GitHub triggers a redeploy of the old code. Railway also has a built-in UI rollback feature.

**E. Can we rollback DB migrations?**
Partially. Alembic provides `alembic downgrade`, but rolling back populated data in Supabase requires manual intervention or Point-in-Time Recovery (PITR) via the Supabase console.

**F. Are Supabase backups configured?**
Not verified in code. Relies entirely on Supabase platform default settings.

**G. What happens if an agent breaks production?**
1. Stop the agent.
2. Revert the offending Git commit.
3. Allow GitHub Actions to pass.
4. Railway auto-deploys the clean state.

**H. What exact rollback commands/process exist?**
- Code: `git revert HEAD && git push origin main`
- DB Schema: `alembic downgrade -1`
- Fast App Revert: Railway Dashboard -> Deployments -> Rollback.

**I. What must be created next?**
A formal `VELO_PRODUCTION_ROLLBACK_RUNBOOK.md` that explicitly maps out Alembic downgrade steps vs Supabase PITR to prevent data loss during an emergency.

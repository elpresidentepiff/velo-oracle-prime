# VELO Main Branch Consolidation - 2026-06-20

## Decision

`main` is the only active house.

All race-day, Sigma, learning, dashboard, Shadow VELO, and hardening work must run from:

`C:\Users\puror\velo-oracle-prime`

Branch:

`main`

Remote:

`origin/main`

## Confusion Found

GitHub remote default branch is `main`, but local `origin/HEAD` was stale and pointed at:

`origin/feature/v10-launch`

This has been corrected locally with:

`git remote set-head origin main`

## Worktrees Found

- `C:\Users\puror\velo-oracle-prime` -> `main` -> canonical.
- `C:\Users\puror\OneDrive\Documents\New project\prime-audit-main` -> `codex/prime-mot-20260607` -> reference only, not race-day work.
- `C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix` -> `feature/v10-launch` -> quarantined stale branch.
- `C:\Users\puror\velo-oracle-prime\.claude\worktrees\agent-a4cfb9a6` -> stale/prunable worktree metadata.

## feature/v10-launch Audit

Local `feature/v10-launch` is five commits ahead of `origin/feature/v10-launch`.

Unique commits:

- `d0f8d53` docs: add live sidecar risk register
- `6b0ceb2` docs: lock runtime-proven VELO live weight contract
- `efee4c6` feat: connect Racing API stats as shadow operator enrichment
- `d1f7ecc` feat: add canonical racing api client limiter skeleton
- `d6c3673` security: redact racing api archive credentials and add api control-plane audits

## Salvage Result

No code was cherry-picked from `feature/v10-launch`.

Reason:

- `main` already contains the useful audit assets:
  - `scripts/audit/audit_live_weight_contract.py`
  - `scripts/backtest/live_sidecar_ablation_audit.py`
  - `docs/engineering/VELO_PROCESS_WIRING_MAP_V1.md`
- The `main` versions are newer and carry the canonical-main lock.
- The remaining unique branch work is Racing API-era control plane/enrichment and must not enter live VELO.

## Quarantine

Do not merge `feature/v10-launch` wholesale.

Do not import:

- `app/api/racing_api_client.py`
- `app/integrations/racing_api_client.py`
- `scripts/racing_api_enrichment_operator_card.py`
- `src/velo/racing_api_stat_adapter.py`
- `src/integrations/racing_api.py`
- `workers/racing_api_fetcher.py`
- `tests/test_racing_api_fetcher.py`
- Racing API credential/client limiter docs or data artifacts

## Law

Racing API is dead for live VELO.

Racing Post HTML/RP scraper artifacts are the live source of truth.

If a future agent finds useful logic in a quarantined branch, it must be manually rewritten into an RP-only form on `main`; no direct cherry-pick without review.


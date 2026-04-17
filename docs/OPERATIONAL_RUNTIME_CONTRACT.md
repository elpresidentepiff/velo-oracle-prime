# Operational Runtime Contract

This document defines the runtime rules for the active VELØ operational spine.

## Scope

The active operational spine is:

- `app/main.py`
- `app/services/velo_prime_service.py`
- `scripts/run_prime_today.py`
- `scripts/run_results_sigma.py`
- `scripts/shadow_lab.py`
- `workers/daily_pipeline.py`
- `app/core/runtime_env.py`

These paths are production- or shadow-critical. Regressions here are blocking.

## Runtime Rules

1. Environment and runtime resolution

- Only `app/core/runtime_env.py` may resolve runtime environment, env-file loading, Supabase keys, and Telegram settings for the active spine.
- Do not add `load_dotenv()` directly inside operational-path files.
- Do not reintroduce per-script secret resolution logic when a shared runtime helper exists.

2. Time handling

- Do not use `datetime.utcnow()` in the operational spine.
- Use timezone-aware UTC helpers from `app/core/runtime_env.py`.
- Persist UTC timestamps in a consistent ISO format.

3. Secrets

- Do not embed fallback secrets, publishable keys, service keys, API tokens, or JWT-like values in operational code.
- Canonical Supabase runtime contract is:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
- Legacy env names may be supported temporarily only through shared runtime/config helpers, never by new ad hoc script code.

4. Side effects

- Operational scripts must support controlled execution without hidden side effects where practical.
- Dry-run and notification controls should be explicit, not implied by local state.
- Core orchestration should remain callable without forcing process exit from deep inside the workflow.

5. Testing and merge policy

- Policy tests covering the operational spine must pass before merge.
- Hardening tests for security validation, persistence retry behavior, runtime bootstrap, and operational policy must remain green.
- New operational-path files should be added to the operational policy allowlist when they become part of the active spine.

## Legacy Paths

Scripts outside the active spine are not yet blocking under this contract.

They are considered a monitored legacy pool until they are either:

- migrated onto the shared runtime contract,
- explicitly quarantined from operational use, or
- retired.

## Quarantine Direction

Legacy scripts should move through one of three states:

1. `active`
2. `monitored legacy`
3. `retired/quarantined`

Do not promote a legacy script back into operational use without:

- shared runtime/env handling,
- timezone-aware UTC handling,
- secret review,
- and policy-test coverage.

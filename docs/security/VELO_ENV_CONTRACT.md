# VELO Environment Contract

## Purpose

This document defines the environment-variable contract for the canonical `velo-oracle-prime` runtime.

It is intentionally operational, not aspirational:

- what variable exists
- whether it is required
- who uses it
- where it should live
- what happens if it is missing

## Location Rules

### Production

- Railway environment variables
- GitHub Actions encrypted secrets where CI or workflow execution requires them

### Local development

- Untracked `.env`
- Secure local shell/session environment

### Forbidden

- Tracked `.env`
- Markdown docs with real values
- JSON operator artifacts
- Committed scripts with inline credentials

## Core Platform

| Variable | Required | Used by | Production location | Local dev | Safe default | Failure mode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `SUPABASE_URL` | Yes | `app/main.py`, `app/core/config.py`, Supabase clients, audits | Railway env | untracked `.env` | empty string | Supabase reads/writes fail |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes for write paths | `app/main.py`, scoring persistence, sigma, audits, workers | Railway env | untracked `.env` | empty string | write paths fail or disable |
| `SUPABASE_SERVICE_KEY` | Optional legacy alias | legacy and compatibility paths | Railway env only if still needed | untracked `.env` | empty string | legacy scripts may fail |
| `SUPABASE_KEY` | Optional legacy alias | older app and archive paths | avoid in production if possible | untracked `.env` | empty string | legacy read/write ambiguity |
| `SUPABASE_ANON_KEY` | Optional | public or limited client flows | Railway env if used | untracked `.env` | empty string | anon client paths fail |
| `SUPABASE_ACCESS_TOKEN` | Optional admin tooling | ops and CLI tooling | secure admin env | local secure env | empty string | admin tooling fails |
| `SUPABASE_PROJECT_REF` | Optional tooling metadata | MCP and admin references | secure admin env | local secure env | empty string | tooling convenience only |
| `SUPABASE_DB_URL` | Required for direct DB scripts only | `app/config/supabase_config.py`, HFS/backfill scripts | Railway env if direct DB use is approved | untracked `.env` | empty string | direct psycopg2 jobs fail |

## Racing API

| Variable | Required | Used by | Production location | Local dev | Safe default | Failure mode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `RACING_API_USERNAME` | Yes for live fetch | `app/integrations/racing_api_client.py`, `app/api/racing_api_client.py`, `scripts/run_prime_today.py`, `scripts/run_results_sigma.py`, workers | Railway env | untracked `.env` | empty string | racecard/results fetch fails |
| `RACING_API_PASSWORD` | Yes for live fetch | same as above | Railway env | untracked `.env` | empty string | auth fails |
| `RACING_API_BASE_URL` | Optional | racing clients and workers | Railway env | untracked `.env` | provider default URL | endpoint base defaults |
| `RACING_API_KEY` | Optional legacy path only | `src/integrations/racing_api.py`, `src/pipelines/*` | avoid unless legacy path is still used | untracked `.env` | empty string | legacy `src/` integrations fail |

## Telegram and Notification Layer

| Variable | Required | Used by | Production location | Local dev | Safe default | Failure mode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Required for Telegram output | `app/main.py`, `scripts/run_prime_today.py`, `scripts/run_results_sigma.py`, workers | Railway env | untracked `.env` | empty string | no Telegram notifications |
| `TELEGRAM_CHAT_ID` | Required for direct sends | scripts and workers | Railway env | untracked `.env` | empty string | notifications cannot target a chat |
| `TELEGRAM_WEBHOOK_URL` | Optional | webhook tooling | Railway env | untracked `.env` | empty string | webhook convenience only |
| `TELEGRAM_WEBHOOK_SECRET` | Optional but recommended | webhook security | Railway env | untracked `.env` | empty string | weaker webhook trust model |
| `TELEGRAM_VOX_TOKEN` | Optional alternate bot | `workers/velo_vox/telegram_bot.py` | Railway env | untracked `.env` | empty string | Vox bot falls back or fails |
| `HERMES_BOT_TOKEN` | Optional alternate bot | `workers/hermes_bridge/hermes_bridge.py` | Railway env | untracked `.env` | empty string | Hermes bot falls back or fails |

## API and Trigger Control Plane

| Variable | Required | Used by | Production location | Local dev | Safe default | Failure mode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `API_KEY` | Yes | `app/main.py` ingress auth | Railway env | untracked `.env` | empty string | protected endpoints reject |
| `TRIGGER_SCORE_SECRET` | Yes for trigger routes | `app/main.py` trigger and upload routes, GitHub workflow calls | Railway env + GitHub secret | untracked `.env` | empty string | trigger endpoints disabled |
| `OPS_API_KEY` | Optional ops smoke path | production smoke workflows | GitHub secret / Railway env | secure local env | empty string | ops smoke calls fail |
| `TRIGGER_SOURCE` | Optional provenance | subprocess and run metadata | Railway env | untracked `.env` | empty string | weaker audit provenance |
| `PIPELINE_RUN_ID` | Optional provenance | pipeline tracking | Railway env / runtime injection | local shell | empty string | weaker run traceability |
| `PIPELINE_SERVICE_NAME` | Optional provenance | pipeline tracking | Railway env | local shell | empty string | weaker run traceability |
| `RAILWAY_SERVICE_VELO_ORACLE_URL` | Optional but needed for webhook registration | `app/main.py` Telegram startup path | Railway env | local shell | empty string | webhook registration skipped |
| `RAILWAY_ENVIRONMENT` | Optional | environment labeling | Railway env | local shell | empty string | logs lose environment tag |
| `VELO_ORACLE_URL` | Optional | smoke and operator tooling | Railway env | local shell | empty string | some tooling may not resolve service URL |

## Betfair and Execution Infrastructure

| Variable | Required | Used by | Production location | Local dev | Safe default | Failure mode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `BETFAIR_MODE` | Required for explicit execution context | `app/integrations/betfair_client.py`, `src/velo/execution_bridge.py` | Railway env if ever enabled | untracked `.env` | `SIM` | live mode blocked or runtime error |
| `BETFAIR_APP_KEY_DELAYED` | Optional now | delayed client mode | secure env only | untracked `.env` | empty string | delayed client unavailable |
| `BETFAIR_APP_KEY_LIVE` | Optional now | live client mode | secure env only | untracked `.env` | empty string | live client unavailable |
| `BETFAIR_USERNAME` | Optional now | Betfair clients | secure env only | untracked `.env` | empty string | auth fails |
| `BETFAIR_PASSWORD` | Optional now | Betfair clients | secure env only | untracked `.env` | empty string | auth fails |
| `BETFAIR_CERT_FILE` | Optional now | app-side client plan | secure env only | secure local path | empty string | cert auth unavailable |
| `BETFAIR_KEY_FILE` | Optional now | app-side client plan | secure env only | secure local path | empty string | cert auth unavailable |
| `BETFAIR_APP_KEY` | Optional legacy `src/` path | `src/integrations/betfair_api.py`, `src/integrations/betfair_client.py` | secure env only | untracked `.env` | empty string | legacy auth fails |
| `BETFAIR_CERT_PATH` | Optional legacy `src/` path | `src/core/settings.py` consumers | secure env only | secure local path | empty string | legacy cert auth fails |
| `BETFAIR_KEY_PATH` | Optional legacy `src/` path | `src/core/settings.py` consumers | secure env only | secure local path | empty string | legacy cert auth fails |

## Feature Flags and Lane Control

| Variable | Required | Used by | Production location | Local dev | Safe default | Failure mode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `VELO_G_SHADOW_MODE` | Optional but safety-critical | `app/main.py`, `src/intelligence/velo_prime_ensemble.py` | Railway env | untracked `.env` | `shadow` | `live` mode blocked at startup |
| `VELO_G_FEED_ENABLED` | Optional but safety-critical | `scripts/run_results_sigma.py`, `scripts/audit_sentient_feed_safety.py` | Railway env | untracked `.env` | `OFF` | unsafe feed remains disabled |
| `VELO_EXECUTION_MODE` | Optional | `src/velo/execution_bridge.py`, `scripts/run_execution_bridge_shadow.py` | Railway env | untracked `.env` | `SIM` | invalid values raise runtime error |
| `VELO_ENSEMBLE_POLICY` | Optional | `src/intelligence/velo_prime_ensemble.py` | Railway env | untracked `.env` | current policy | policy selection defaults |

## Adjacent Provider Variables

| Variable | Required | Used by | Production location | Local dev | Safe default | Failure mode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `OPENROUTER_API_KEY` | Optional | Hermes/OpenRouter provider paths | Railway env | untracked `.env` | empty string | provider path unavailable |
| `ANTHROPIC_API_KEY` | Optional | test and OpenRouter fallback paths | Railway env | untracked `.env` | empty string | provider path unavailable |
| `ZEP_API_KEY` | Optional | `src/intelligence/zep_memory/zep_client.py` | Railway env | untracked `.env` | empty string | memory client disabled |
| `RAILWAY_TOKEN` | Optional admin tooling | deployment/admin scripts | GitHub secret / secure env | local secure env | empty string | deploy tooling fails |
| `CLOUDFLARE_API_TOKEN` | Optional infra tooling | template and infra paths | GitHub secret / secure env | local secure env | empty string | infra tooling fails |

## Current Risk Notes

- `TRIGGER_SCORE_SECRET` is the current trigger secret name in `app/main.py`.
- Current tree still contains hardcoded Telegram chat ID fallbacks in some worker and script paths. Those are configuration smells and should be removed in a later safety pass.
- Current tree contains public Supabase project references and temp metadata files. Those are not secrets, but they should be treated as control-plane metadata.
- Legacy `src/` paths still reference `RACING_API_KEY` and older Betfair variable names. They are not the canonical live scoring path.

## Enforced Contract

- If a variable is required and missing, the code should fail closed or disable the protected path.
- No operator-facing or scoring artifact may serialize real secret values.
- If a new secret is introduced, this file must be updated in the same change set.

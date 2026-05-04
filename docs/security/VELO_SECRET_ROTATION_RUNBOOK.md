# VELO Secret Rotation Runbook

## Purpose

This runbook defines how VELØ handles credential exposure, rotation, validation, and post-incident cleanup.

This document is a release-control artifact. It does not authorize feature work, live betting, or execution changes.

## Secret Inventory

### Core platform secrets

- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_SERVICE_KEY` if still used in legacy paths
- `SUPABASE_ANON_KEY`
- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_DB_URL`

### Racing API secrets

- `RACING_API_USERNAME`
- `RACING_API_PASSWORD`

### Telegram secrets

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_VOX_TOKEN`

### Trigger and API secrets

- `API_KEY`
- `TRIGGER_SCORE_SECRET`
- `OPS_API_KEY`

### Betfair secrets

- `BETFAIR_APP_KEY_DELAYED`
- `BETFAIR_APP_KEY_LIVE`
- `BETFAIR_USERNAME`
- `BETFAIR_PASSWORD`
- `BETFAIR_CERT_FILE`
- `BETFAIR_KEY_FILE`
- `BETFAIR_APP_KEY`
- `BETFAIR_CERT_PATH`
- `BETFAIR_KEY_PATH`

### Adjacent provider secrets

- `OPENROUTER_API_KEY`
- `ANTHROPIC_API_KEY`
- `ZEP_API_KEY`
- `RAILWAY_TOKEN`
- `CLOUDFLARE_API_TOKEN`

## Where Secrets Should Live

- Railway environment variables for production runtime
- GitHub Actions encrypted secrets for CI and automation
- Local untracked `.env` for developer machines
- Secure password manager / team vault for source-of-truth custody

## Where Secrets Must Never Live

- Tracked repo files
- Markdown docs
- Generated artifacts in `data/`
- Dashboard JSON or operator cards
- Terminal screenshots shared publicly
- Chat transcripts pasted into external tools
- Inline examples that use real values

## Current Audit Truth

### Confirmed

- Current HEAD reads Racing API credentials from environment variables only.
- No tracked `.env` file was found.
- Templates exist only as placeholders:
  - `.env.template`
  - `.env.example`
  - `workers/ingestion_spine/.env.example`

### Confirmed historical exposure

- `app/integrations/racing_api_client.py` history contains:
  - `53ec195` `security: replace hardcoded credentials with env var references`
- This is sufficient to treat historical Racing API credentials as exposed.

### Immediate policy outcome

- Racing API credential rotation is required.
- Review and rotation of other production secrets is also recommended after any public-history exposure event.
- History rewrite is recommended later, but rotation comes first.

## Rotation Procedures

### 1. Racing API credentials

1. Generate or request new Racing API credentials from the provider.
2. Update Railway production environment variables:
   - `RACING_API_USERNAME`
   - `RACING_API_PASSWORD`
   - `RACING_API_BASE_URL` if changed by provider
3. Update GitHub Actions secrets if any workflow uses provider access.
4. Update local untracked `.env` files for active operators.
5. Restart or redeploy the service if required.
6. Run smoke tests:
   - prime-day fetch path
   - results fetch path
   - preflight checks
7. Revoke old credentials.

### 2. Supabase anon key

1. Rotate in Supabase dashboard.
2. Update:
   - Railway env
   - GitHub secrets if used
   - local untracked `.env`
3. Verify read-only client flows still function.

### 3. Supabase service role key

1. Rotate in Supabase dashboard immediately after any suspected exposure.
2. Update:
   - Railway env
   - GitHub Actions secrets
   - local untracked `.env`
   - any MCP or admin integration that depends on the service role
3. Validate:
   - write access for governed-card persistence
   - sigma/result closure writes
   - shadow audit scripts
4. Revoke the old key.

### 4. Telegram bot token

1. Regenerate token via BotFather.
2. Update:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_VOX_TOKEN` if separate
   - webhook secret if used
3. Re-register webhook if needed.
4. Validate:
   - startup webhook registration
   - non-betting notification path only

### 5. Betfair credentials, app keys, certs

1. Treat as high-sensitivity execution secrets.
2. Rotate:
   - `BETFAIR_APP_KEY_DELAYED`
   - `BETFAIR_APP_KEY_LIVE`
   - `BETFAIR_USERNAME`
   - `BETFAIR_PASSWORD`
   - certificate and key material
3. Update only in secure vault, Railway, and local untracked secure paths.
4. Confirm `BETFAIR_MODE` remains non-live after rotation.
5. Do not use rotation as permission to activate execution.

### 6. Railway environment variables

1. Export current env inventory safely from Railway admin.
2. Rotate affected secrets in the provider first.
3. Replace values in Railway.
4. Redeploy.
5. Verify startup and operator-grade read paths.

### 7. Local `.env`

1. Replace old values locally.
2. Confirm `.env` remains ignored by git.
3. Never copy production service-role keys into example files.

## Post-Rotation Smoke Tests

- `app/main.py` starts without secret-related exceptions
- `/api/governed-card` returns valid same-date payloads
- `scripts/run_prime_today.py` can authenticate to Racing API
- `scripts/run_results_sigma.py` can authenticate to Racing API and Supabase
- Telegram notification path can authenticate if enabled
- Betfair remains blocked by default

## Emergency Response When a Secret Was Committed

1. Assume the secret is compromised.
2. Rotate the secret before any refactor or cleanup debate.
3. Audit all downstream systems that used the secret.
4. Search tracked tree and recent untracked working files for repeats.
5. Record the incident and rotation completion date.
6. Schedule history rewrite or repository cleanup later if needed.
7. Invalidate any derived tokens or sessions when supported by the provider.

## GitHub and Repo Protection Checklist

- Enable GitHub secret scanning
- Enable push protection if available
- Add pre-commit or CI secret scanning
- Keep `.env` ignored
- Keep templates placeholder-only
- Block commits that contain provider tokens, DSNs with passwords, or cert material

## Redaction Rules

- Never print full secrets in reports
- If a value must be referenced, use first 4 and last 4 characters only
- Public project refs and public URLs should still be treated as metadata, not as proof that a secret is safe to share

## Chat / LLM Safety Rule

- Never paste credentials into ChatGPT, Gemini, Codex, or similar logs
- Never include secrets in screenshots
- Never embed secrets into bug reports or markdown evidence packs

## Status

- Rotation required: `YES`
- History rewrite required immediately: `NO`
- History rewrite recommended later: `YES`

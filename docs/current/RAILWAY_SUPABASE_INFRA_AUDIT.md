# RAILWAY → SUPABASE INFRASTRUCTURE AUDIT

**Date:** 2026-06-10 (late) · Read-only. No services stopped, no env touched, no secrets printed.
**Access caveat:** the local `RAILWAY_TOKEN` is **dead (403 on the GraphQL API)** — service-level facts come from env-dump topology, repo config, endpoint probes, and GitHub run history. Items needing the dashboard are marked **OPERATOR_DASHBOARD**.

## The headline
**The production endpoint is dead and the schedulers are zombies.** `velo-oracle-production.up.railway.app` returns **502** on `/` and `/healthz`. GitHub Actions (the declared scheduler — "Railway cron is intentionally NOT configured, this file IS the schedule") fires triggers into that 502 twice a day, and `smoke-prod` probes it **every 30 minutes — 48 failures/day**, every day. Today's only successful pipeline run was the operator's manual one. Railway currently provides **zero production value** while presumably accruing cost.

## Phase 1 — Service inventory (from Railway-injected env names + repo config + memory)

| Service | Evidence | Classification | Waste 0–5 |
|---|---|---|---|
| `velo-oracle` | railway.toml (uvicorn app.main:app), public domain → **502 dead** | Was PRODUCTION; currently **DORMANT/CRASHED** | 4 — dead but referenced by the schedulers |
| `velo-prime-scoring` | service URL env + pipeline_runs history | RACE_DAY_REQUIRED *intent* — but every recent run is manual from WSL | 3 — dormant; revive or remove with cron decision |
| `ingestion-spine` | service URL env; PDF parser worker (fixed Mar 15) | LEGACY-leaning (Racing-API-era; the only thing CI tests) | 3 |
| `hermes-agent` | env dump exists for it; holds **SUPABASE_SERVICE_ROLE_KEY**, Telegram token, OpenRouter keys, DATABASE_URL, a **volume** | **UNKNOWN + DANGEROUS_WRITE_CAPABLE** — a service with service-role Supabase power whose purpose is undocumented in this repo (media/podcast agent per name) | **5 — top review priority** |
| `enchanting-exploration` | service URL env; CLAUDE.md: "duplicate of velo-oracle, both running against same DB, not decommissioned" | **DUPLICATE** | 5 |

## Phase 2 — Env vars (names only — full list in `data/reports/railway_env_var_names_redacted.md`)
- hermes-agent: 32 names — incl. `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `RACING_API_*` (dead source), OpenRouter/Moltbook keys, a volume mount.
- velo-oracle: 36 names — incl. `SUPABASE_SERVICE_KEY`, `TRIGGER_SCORE_SECRET`, `API_KEY`, `TELEGRAM_*`, `RACING_API_*` (dead), `ACTIVE_MODEL_NAME/VERSION`.
- Dead vars to remove after approval: all `RACING_API_*` (decommissioned source).
- **Local `RAILWAY_TOKEN` invalid** — replace if API control is wanted.

## Phase 3 — Supabase connection map (who can write)

| Writer | Path | Tables | Verdict |
|---|---|---|---|
| Operator WSL box (manual chain) | scripts via `.env` service key | velo_verdicts, pipeline_runs, runner_release_candidates, racing_horse_runs, sigma_audits, learned_patterns | **The only живой production writer** — all writes accounted for by the daily chain |
| `velo-oracle` (Railway) | app/main.py service — currently 502 | same set when alive | Dormant writer |
| `hermes-agent` (Railway) | **service_role key present** | unknown — no code for it in this repo | **UNKNOWN WRITER — operator must confirm in dashboard what it runs** |
| `enchanting-exploration` | duplicate of velo-oracle | same | Dormant duplicate writer |
| GitHub Actions | HTTP trigger only (no direct Supabase secrets in workflows) | none directly | Safe by construction; currently failing anyway |

## Phase 4 — Supabase census (full JSON: `data/current/supabase_schema_inventory.json`)
**35 populated / 25 empty (never written) / 0 absent.** Notables: `horse_profiles` **183,699 rows** (another vault asset — huge profile bank), `runner_results` 33,430 + `race_results` 3,227 (historical results layer), **`betting_ledger` 1,050 rows — "no live staking" is law, so the operator must confirm these are SIM-era rows** (likely the old paper framework). Empty schema junk (25 tables incl. betfair_markets/odds, market_snapshots, sectional_data, plot_memory_spine, rpd_tags) — CANDIDATE_FOR_ARCHIVE after approval; keep `market_snapshots`/`odds_snapshots` (future BSP capture target).

## Phase 5 — Automation audit

| Trigger | Schedule | What it does | Status | Recommendation |
|---|---|---|---|---|
| GH `score-daily.yml` (main) | 09:00 + 21:00 UTC Mon–Sat | HTTP trigger → Railway score/sigma | **FAILING daily (502)** | KEEP file as the future scheduler design; **DISABLE schedule until Railway revived or replaced** — every fire is noise |
| GH `smoke-prod.yml` (main) | **every 30 min** | health probe → 502 | **48 failures/day** | **DISABLE_AFTER_APPROVAL immediately** — pure noise+minutes |
| GH `velo-nightly-eod-learning.yml` | 23:15 daily | learning enforcer | **NOT ON GITHUB (branch-only, 404)** — never fires | Decide before merging this branch: gate it on LEARNING_READY artifact or strip the schedule |
| GH `backfill-sigma.yml`, `benchmark`, `gx-validate`, `prefect-smoke`, `agent-dry-run`, `ci` | various/PR | checks | active | Review batch — `ci` only tests ingestion_spine (known gap) |
| Railway crons | — | railway.toml documents intent only ("Railway stores config server-side") | UNPROVEN — token dead | OPERATOR_DASHBOARD check |
| Local cron.txt / Makefile | — | dead-era references | inert | Archive (already classified) |

## Phase 6 — Cost/waste summary
Without API access exact costs are OPERATOR_DASHBOARD, but the structure is clear: **5 services where at most 1–2 are justified**, one volume, a dead public endpoint, and a 30-minute probe loop. Waste-5 items: `enchanting-exploration` (duplicate), `hermes-agent` (unknown, service-role armed). Waste-4: dead `velo-oracle` in its current state. The honest target is in `MINIMAL_PRODUCTION_TOPOLOGY.md`.

## Phase 9 — Secret exposure status (no values)
`railway_hermes_env.txt` + `railway_velo_oracle_env.txt`: **exist locally · NOT git-tracked · NOT in git history · properly gitignored.** Exposure is local-disk only — the nightmare scenario (public repo history) did **not** happen. Because the dumps contain `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `OPENROUTER_*`, `RACING_API_*`: **rotation recommended as hygiene** (provider list above, names only), priority on the service-role key. Operator checklist: 1) rotate Supabase service-role + DB password, 2) rotate Telegram bot token, 3) rotate OpenRouter keys, 4) let dead Racing API creds die unrotated, 5) delete the two dump files from disk after rotation, 6) issue a fresh scoped Railway token if API control wanted.

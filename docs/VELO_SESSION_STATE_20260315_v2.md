# VÉLØ Session State — 2026-03-15 (v2, post-ingestion-spine fix)

## Commits This Session (chronological)
| Commit | Description |
|---|---|
| `4d95072` | SQPE v16 trained on 172k real UK/IRE runners, AUC 0.9428 |
| `e01343a` | Wire SQPE v16 into /quick endpoint + validation framework |
| `5485997` | Ingestion spine — 6 schema bugs fixed (db.py/storage.py) |
| `05f4536` | **ROOT CAUSE FIX: CRLF line endings in start.sh** + .gitattributes |

---

## Railway Topology (sincere-empathy project)
Three services, one project:
- **velo-oracle** — main FastAPI prediction engine. URL: `velo-oracle-production.up.railway.app`. Deployed from `app/`.
- **ingestion-spine** — PDF parser worker. URL: `ingestion-spine-production.up.railway.app`. Deployed from `workers/ingestion_spine/Dockerfile`.
- **enchanting-exploration** — live FastAPI API. URL: `enchanting-exploration-production-4544.up.railway.app`. Routes: `/api/v1/predict/quick`, `/api/v1/predict/full`, `/api/v1/intel/*`, `/api/v1/system/models`, `/features/*`, `/monitoring/*`.

---

## Ingestion Spine — What Was Fixed

### Bug that was causing 502 (ROOT CAUSE)
`start.sh` had Windows CRLF line endings. Linux container bash read the shebang as `#!/bin/bash\r` — interpreter not found. Container exited immediately on every deploy. Every request returned 502 "Application failed to respond". This was the reason the service has NEVER started successfully.

Fix: Stripped CRLF from `start.sh`. Added `.gitattributes` to enforce LF for all .sh/.py/Dockerfile files going forward.

### Additional bugs fixed (commit 5485997)
- `db.py`/`storage.py`: read `SUPABASE_SERVICE_ROLE_KEY` — Railway has it set, but added fallback to `SUPABASE_SERVICE_KEY` for safety
- `races` table: 8 column mismatches (`off_time`→`time`, `import_date`→`date`, `distance`→`distance_f`, `class_band`→`class`, `field_size`→`runners_count`). Added `batch_id`, `race_name`, `join_key`, `raw` columns via migration.
- `races.race_id`: no default. Added `DEFAULT gen_random_uuid()::text`.
- `runners` table: `ts`→`ts_rating`, `form_figures`→`form`, added `cloth_no`/`raw` columns.
- `import_files` table: did not exist. Created.
- `runner_form_lines` table: did not exist. Created.

### Local test result (after fixes)
`/healthz` → 200 OK, `/health` → 200 OK. DB connection verified. Boot time ~3 seconds.

---

## SQPE v16
- **AUC: 0.9428** | Log Loss: 0.2052 | 172,789 real runners
- Top feature: `rpr_vs_field` (40.9%) — RPR relative to race field average
- Wired into `/quick` prediction endpoint via `app/engine/v16_predictor.py`
- Model at: `models/sqpe_v16/sqpe_v16.pkl`
- Trainer at: `scripts/train_sqpe_v16.py`

## Validation result (Kempton 4:40 vs CHAREX)
- 45% agreement — v16 ranks by RPR supremacy, CHAREX ranked by course/going/distance fit
- Divergence is a feature gap, not a model flaw
- SQPE v17 needs: course_fit_score, going_fit_score, distance_fit_score + 14 more features (see v17 plan)

---

## SQPE v17 Features (to build next)
`runs_since_win`, `runs_since_place`, `runs_since_market_support`,
`current_or_minus_last_win_or`, `current_or_minus_best_condition_or`,
`course_fit_score`, `going_fit_score`, `distance_fit_score`,
`mark_compression_score`, `release_window_score`, `quiet_run_score`,
`trainer_timing_score`, `jockey_switch_intent_score`,
`odds_resilience_score`, `odds_contraction_after_losses`,
`setup_run_flag`, `cash_run_flag`, `decoy_support_flag`

---

## Live Race Protocol
Source: Racing API only.

Signal priority:
1. release-window / handicap plot
2. mark compression vs last winning/placed mark
3. return to ideal conditions (course/going/distance/field shape)
4. market behaviour after repeated defeats
5. jockey switch / trainer timing / intent anomalies
6. RPR, TS, OR relative to field
7. current odds vs true chance

Output per race: Top Strike | Best Value | Best Longshot | Fade horses
Each with 3-line reason + run-type: Setup Run / Cash Run / Trap Run / Genuine Decline / Release Day

---

## Remaining Priorities
1. **Verify ingestion-spine redeploy** — check `https://ingestion-spine-production.up.railway.app/healthz` after build completes (~5-10 min from push `05f4536`)
2. **Understand enchanting-exploration** — it's serving a full prediction API already. What code is it running? What's the diff from velo-oracle?
3. **Create rp_imports bucket** in Supabase Storage (ingestion spine needs it for PDF uploads)
4. **Build SQPE v17** with 17 new features
5. **Wire v17 into verdict generation**
6. **Fix Railway cron** for daily pipeline: change `0 10 *` to `0 6 * * *`
7. **Verify race_results / runner_results populate** after races finish

---

## Key Credentials (never hardcode)
- Supabase project: `ltbsxbvfsxtnharjvqcm` (eu-west-2)
- Railway project: `sincere-empathy` (ID: 37d7f632-b248-4d7a-91ba-e860d1151c90)
- Railway ingestion-spine service ID: `b9a52e75-6d98-4077-98d0-d9e68b16033e`
- All creds in `.env` — gitignored

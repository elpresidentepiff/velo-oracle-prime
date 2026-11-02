# RACE DAY RUNBOOK — VÉLØ ORACLE PRIME

**Effective:** 2026-11-02. All commands from repo root with `PYTHONPATH=.` and `PYTHONIOENCODING=utf-8`.
`{D}` = `YYYY-MM-DD`, `{D_}` = `YYYY_MM_DD`. `FINAL_CAPTURE_LABEL` is chosen ONCE after Stage 2 and reused everywhere.
**Rule:** stop at the first failed gate, announce the obstacle, fix the source, rerun the stage. No stage may rediscover its own inputs.

**Primary executor (verified 2026-10-20):** Railway service `velo-rp-capture` runs
`scripts/ops/rp_cloud_raceday.py` from `Dockerfile.rpcapture` at 07:00 UTC. It performs
FormFav readiness first, logs into Racing Post with the Railway RP credentials, captures
RP HTML, builds the URL list, and hands the dated capture to the canonical runner. The
Windows `run_full_raceday.py` flow remains a supported local fallback only. Do not point
the scheduled worker at `scripts/ops/run_cloud_raceday.py`; that is the retired Racing
API path.

**Primary EOD executor (cloud contract prepared 2026-11-02):** Railway service
`velo-results-sigma` must use `/railway.eod.toml`, which runs
`scripts/ops/rp_cloud_eod.py --execute --no-notify` at 21:00 UTC. Morning and
evening Railway jobs have separate ephemeral filesystems. The EOD wrapper therefore
reconstructs the exact scored race universe from Supabase `races` + `velo_verdicts`,
requires an identity-matching Racing Post racecard URL for every scored race, converts
only those URLs to RP results URLs, hydrates the persisted morning report artifacts,
and then invokes the existing EOD orchestrator. It does not use Racing API or another
results source. Deployment is not proved by this document: verify the Railway service's
config file, deployed `main` SHA, next cron time, and the resulting `pipeline_runs` row.

| # | Stage | Command | Expected output | Failure condition | Fallback | Operator approval |
|---|---|---|---|---|---|---|
| 1 | Pre-flight | `python scripts/ops/velo_session_start_check.py` | All checks OK | Any CRITICAL | Fix and rerun; do not proceed | No |
| 2 | Racecard ingestion | Steps 1–4 of `THE_ONE_TRUTH.md`: capture index → build URL list → capture race pages (batch 15) → `parse_racing_post_racecard_capture.py --write-standard-cache` | `racecard_injection.json` + `data/racecards_{D_}_standard.json`; zero null off_times | HTML <100KB (index) / <500KB (race) = expired session; null off_times | `racing_post_account_collector.py init-login` then re-capture missing URLs only | No |
| 3 | Source validation | `python scripts/ops/validate_rp_injection.py --injection-path data/racing_post_account_parsed/FINAL_CAPTURE_LABEL/racecard_injection.json` | Exit 0; ≥3 courses; unique race IDs | Non-zero exit | None — hard gate. Fix data, re-parse | No |
| 4 | RPDC check | `python scripts/ops/build_rpdc_daily.py --date {D} --injection-path <same as stage 3>` | One row per runner in `runner_release_candidates`; real numeric RP horse IDs | `RPDC zero-runner warning` = ID-chain regression in `racecard_loader.py` / `parse_rp_results_capture.py` / `build_rpdc_daily.py` | None — fix the ID chain | No |
| 5 | Ratings source check | Build merged files: `python scripts/ops/build_racecard_merged_from_injection.py --date {D} --injection-path <same>` then inspect `pdf_intel` coverage | Every runner has OR/TS/form; >50% have `postdata_score` or `or_compression_score` → day will be CLEAN | >50% missing PDF intel → day will score DEGRADED and learning is pre-blocked | Proceed degraded ONLY with operator acknowledgment | **Yes if degraded** |
| 6 | Scoring | `PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/ops/run_prime_today.py --date {D} --source rp --no-notify` | N/N verdicts, 0 score errors, observability JSON written, `next_safe_command` populated | Any score error; coverage <100%; `SOURCE_UNKNOWN_BLOCK` | Rerun after fixing inputs; never hand-edit verdicts | No |
| 7 | Persistence | Automatic in stage 6 | `persist_ok == races`, `persist_fail: 0`, local backup `data/velo_prime_verdicts_{D_}.json` | Supabase write failures | `velo_daily_run_truth_{D_}.json` records archive repair status; investigate before evening | No |
| 8 | Dashboard publish | `python scripts/ops/parse_industry_selections.py` → `python scripts/ops/publish_daily_predictions_to_dashboard.py` → `python scripts/ops/build_industry_comparison.py` | Dashboard JSON refreshed under `app/static/dashboard/` | Missing RP F_0010 PDFs / verdicts JSON | Skip comparison, publish verdicts only | No |
| 9 | Telegram publish | Currently DISABLED (`--no-notify`). When enabled: scoring alerts from `run_prime_today.py`; degraded notice via `scripts/ops/send_degraded_run_notice.py` | `telegram_delivery_truth_{D_}.json` shows sent/failed counts | Silent non-delivery (events>0, sent=0, notify_enabled=true) | Manual send via `send_final_tg_report.py` | **Yes to re-enable** |
| 10 | Results collection (~21:00 UTC cloud; local fallback otherwise) | Cloud: `python scripts/ops/rp_cloud_eod.py --date {D} --execute --no-notify`. Local fallback: `build_rp_results_url_list.py --date {D} --capture-label FINAL_CAPTURE_LABEL --execute` → collector → parser | Cloud preparation reports equal `scored_races` and `results_urls`; `data/results/rp_results_{D_}.json`; parse_errors 0; all starters `sp_dec>0`; real numeric IDs | Missing Supabase morning truth; any scored race lacks an identity-matching RP URL; RP login/capture failure; partial parse | Stop. Repair the durable morning evidence or RP session; never substitute a source or shrink the race universe | No |
| 11 | Sigma reconciliation | `python scripts/ops/run_results_sigma.py --date {D} --source cache` | `data/sigma_results/sigma_results_{D_}.json`; zero identity failures; locked-format Telegram report | Identity failures; missing predictions unexplained | NEVER `--source api`; NEVER `close_sigma_loops.py` | No |
| 12 | horse_runs ingest | `python scripts/ops/ingest_results_to_horse_runs.py --date {D}` | `INGEST COMPLETE`; runners written = all parsed runners → Supabase `racing_horse_runs` | Count mismatch | Re-parse results first; never partial-ingest | No |
| 13 | RPDC build for tomorrow | Happens tomorrow at stage 4 — it reads tonight's `racing_horse_runs`. Tonight: `python scripts/ops/build_sigma_retrieval_corpus.py --require-through-date {D}` | Corpus `date_max` includes {D} | Corpus missing today | Rerun after stage 12 | No |
| 14 | Mission Control update | `python scripts/ops/update_mission_control.py --date {D}` | `data/mission_control/{D}_mission_control.json` + `latest.json`; gates with reasons | KNOWN DEFECT: source_truth defaults CLEAN — cross-check observability JSON | Treat observability as authoritative | No |
| 15 | Learning eligibility | `vp30_operator_card.py --date {D}` → `run_velo_council.py --date {D}` → if `PASS_TO_LEARNING`: `nightly_eod_learning_runner.py --date {D}` → bridge/router Steps 17–19 → final Council + MC refresh | Council `READY` + `PASS_TO_LEARNING`; Playbook G `SHADOW_ONLY_OK`, `live_sentient_state_touched: false` | `WATCH_ONLY` / `EVIDENCE_INCOMPLETE` / `QUARANTINE_DAY` → learning does NOT run | None — gates are non-negotiable | **Yes for any gate override (never granted to date)** |

**`DAY COMPLETE`** only when stages 10–15 all pass and the final Council/Mission Control refresh passes. Otherwise state **`DAY INCOMPLETE`** and the exact failed stage.

For the cloud path, `rp_cloud_eod.py` additionally requires every mandatory step in the
dated `run_full_raceday_eod` report to be `ok=true` and requires the latest durable
`pipeline_runs` record for service `velo-results-sigma` and `{D}` to be
`PASS/completed`. A Railway container exit code or successful deployment alone is not
proof of EOD completion.

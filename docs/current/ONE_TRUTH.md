# ONE TRUTH — VÉLØ ORACLE PRIME

> **IF THIS FILE CONFLICTS WITH ANY OTHER DOC, THIS FILE WINS UNTIL OPERATOR SAYS OTHERWISE.**

**Effective:** 2026-06-29 (updated from 2026-06-26 baseline) · **Branch:** `main` · **HEAD:** `8753b4f` · **Verified against code, not docs.**

**This file supersedes:** `THE_NEW_TRUTH.md`, `CURRENT_RUNTIME_TRUTH.md`, root `CLAUDE.md` state claims, all numbered docs in `docs/` flat directory.
**This file defers to:** root `THE_ONE_TRUTH.md` for step-by-step command detail (Steps 1–20), `docs/current/RACE_DAY_RUNBOOK.md` for the lifecycle.

## Law (operator-decided, permanent unless stated otherwise)
1. VÉLØ is a behavioural prediction engine for racing. Live weights are **frozen**.
2. **Racing API is not live.** It may exist only as archived legacy, deleted dependency, sidecar reference, documented history, or non-live experimental adapter. Any live-path import of Racing API is a BLOCKER. No document may claim Racing API is connected.
3. The RP (Racing Post HTML) path is the live source path.
4. **RPDC is horse-career memory and deployment context. PDF intelligence is a separate feature and must never overwrite RPDC fields.** (Hijack `fda78d4` fixed 2026-06-10; PDF plot data lives in `full_analysis.plot_intel`.)
5. Mission Control derives source truth from the observability packet — never by default, never by inference. Missing/malformed packet = `UNKNOWN` = learning blocked.
6. Supabase is connected and is the system of record — verify it with `prove_supabase_persistence.py`, never assume it.
7. Learning is blocked on degraded days. No exceptions without operator approval.
8. No live staking. Not a tips service. Execution bridge is SIM/PAPER only with hard runtime guards.

---

## What is VÉLØ?
An auditable UK/IRE horse-racing prediction system. It captures Racing Post HTML, scores every race with a governed ML ensemble, persists verdicts to Supabase, reconciles against results nightly (Sigma), and accumulates evidence under hard learning gates. **No live staking. Not a tips service.**

## What is LIVE
| Thing | Truth |
|---|---|
| Scoring entrypoint | `scripts/ops/run_prime_today.py --date YYYY-MM-DD --source rp --no-notify` (manual; Railway cron is FAIL_OR_UNPROVEN) |
| Live formula | Profile `SQPE_IMPROVEMENT_MDS_V1`: `VP = (0.45·sqpe_v17 + 0.12·improvement_score + 0.10·market_deception_score) / 0.67` (`src/intelligence/velo_prime_ensemble.py:175-235`) |
| Live model files | `models/sqpe_v17/sqpe_v17.pkl` (retrained as v17.1 on 1.54M rows, 2025 holdout AUC=0.9296, promoted 2026-06-19), `models/specialist/improvement_model/`, `models/specialist/market_deception_model/` |
| Stored but NOT weighted | `place_prob` (badge), `longshot_score` (frozen), `release_window_score`, `comment_intel_score` (stored-only) |
| Data source | Racing Post HTML via logged-in Playwright capture (`racing_post_account_collector.py`). UK/IRE only. |
| System of record | Supabase `velo_verdicts`; local backup `data/velo_prime_verdicts_YYYY_MM_DD.json` |
| Rollback | `VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE` |
| SP inference | Fixed 2026-06-18 (`b672f0e`): `_resolve_decimal_odds()` reads `best_odds_decimal` correctly; `sp_rank` and `is_fav` pre-injected across full field |

## What is SHADOW (no scoring effect)
New Build / Passport two-lane scorer · No-RPR model (parallel shadow — no RPR feature; promoted 2026-06-19 alongside sqpe_v17.1) · Playbook G sentient loopback (`sentient_state_shadow.json`) · Execution bridge paper ledger (SIM-only, hard LIVE guard) · Router lanes V1/V2/V6 · Shadow Model C · Race Shape v1 · BHA OR-diff and surface-trajectory badges (evidence only) · BHA form momentum sidecar (paper_scorer.py, 11,817 horses, slope/flag) · Claiming race OWNERSHIP_CHANGE badge (inline run_prime_today.py) · RPDC RS≥1.5 advisory gate (SR=44.7%, n=38).

## Paper Intelligence (dashboard/research overlays only — added 2026-06-21)
These do **not** alter live scoring, tiers, model weights, Supabase verdicts, router execution, Telegram, or staking.

| Layer | Entrypoint | Truth |
|---|---|---|
| Radical Shadow VELO | `scripts/ops/run_radical_shadow_today.py` | No-RPR/radical challenge lane; paper only |
| Tri-Lane V2 | `scripts/ops/run_tri_lane_stress_test.py` | Old/New/Shadow comparison; stress test only |
| Tri-Lane Agent Review | `scripts/ops/build_tri_lane_agent_review.py` | Race review instructions; paper only |
| Deep Race Agent V1 | `scripts/ops/build_deep_race_agent_v1.py` | Analyst gate and why-wrong notes; paper only |
| Course Master | `scripts/ops/build_course_master.py` | Course-level support/warning context; context only |
| Old VELO Three-Option Card | `scripts/ops/build_old_velo_three_option_card.py` | WIN / PLACE / LONGSHOT role card; operator only |

Daily order: run root `THE_ONE_TRUTH.md` Steps 1-9 first, then Steps 9.1-9.6, then dashboard review. Evening learning remains Steps 10-20.

## Multi-Model Tracking (added 2026-06-19)
Three models tracked independently via `run_multimodel_sigma.py` after sigma:

| Model | Entrypoint | Notes |
|---|---|---|
| Old VELO (live) | `run_prime_today.py` → `velo_prime_verdicts_YYYY_MM_DD.json` | Live scoring model — `SQPE_IMPROVEMENT_MDS_V1` |
| No-RPR shadow | `run_radical_shadow_today.py` | Radical challenge lane — no RPR feature |
| New Build | `new_build_two_lane_score.py` | Passport V1 champion — shadow only |

Ledger: `data/model_comparison_ledger.csv` (append-only). Run: `python scripts/ops/run_multimodel_sigma.py --date YYYY-MM-DD --execute`

## EW Tracking (added 2026-06-22)
EW_CANDIDATE flag now tracked in sigma and multimodel ledger. `run_results_sigma.py` emits `ew_outcome` per verdict. `run_multimodel_sigma.py` includes `velo_ew_outcome` column.

## Dashboard Race Cards (added 2026-06-22/23)
- Product badge (WIN/E-W/VISION/PASS) on Old VELO race cards (`DASH-01`)
- Old VELO three-option card (WIN/PLACE/LONGSHOT role assignment) wired into full pipeline (`c33cece`)

## What is DEPRECATED
Racing API as a data source (decommissioned 2026-05-14; client files deleted) · Sporting Life scraper (`scrape_results_sl.py`) · `velo_race_day_button.py` (do not use as authority) · `scrape_results_atr.py` (does not exist — any doc naming it is stale) · root `Makefile` (Benter v10.1 era) · root `cron.txt` (`/home/ubuntu` paths) · `COMMAND.json`.

## What is EXPERIMENTAL
International prerace arenas (`scripts/audit_international_*`) · HK/FR feature builders · Intent Layer V1 (patched, rerun required) · sqpe_v18 (NO_LIFT verdict, not wired) · Race Shape v1 (shadow only, form history parser live).

## VFU Sign-Off Log
- **VFU-20 — OPERATOR SIGN-OFF GRANTED 2026-06-29:** Field-size remediation complete. 1,989 missing → 152 remaining (92.36% recovery accepted). 749 EW label changes accepted. EW profitability = `PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF` — no EW profitability claim authorised. No VP change, no model promotion, no Supabase write. VFU-21 NOT started — awaiting VCP-00 truth lock completion. Output: `data/reports/vfu_20_operator_brief.md`.
- **VFU-01 to VFU-12:** See `docs/current/VELO_VFU_TIMELINE_APPENDIX.md` (archived timeline).
- **VFU-13 to VFU-19:** COMPLETE — contamination catches (Kakirra=CONTAMINATED, MiK=PARTIAL), sigma master ledger, pattern tribunal. No pending operator gates.

## VÉLØ Coherence Protocol (VCP) State (added 2026-06-29)
- **VCP-00 — Truth Lock:** IN PROGRESS (2026-06-29). Stale root docs archived. CLAUDE.md rewritten as pointer-only. docs/current/ thinned to operational spine. ONE_TRUTH HEAD updated.
- **VCP-01 — Living State Packet:** COMPLETE (`ff86674`). `data/current/velo_living_state.json` (gitignored runtime state). Operator signed off 2026-06-29. Builder: `scripts/ops/build_velo_living_state.py`.
- **VCP-02 — Heartbeat V1:** COMPLETE (`5f83fec`). Reads living state only. 25 tests pass. Operator signed off 2026-06-29. Builder: `scripts/ops/build_velo_heartbeat.py`.
- **VCP-03 — Ten-Day Coherence Burn-In:** IN PROGRESS (started 2026-06-29). Day 1: PASS. 1/10 days. Log: `data/reports/vcp_03_burn_in_log.md`. Daily commands: `build_velo_living_state.py` → `build_velo_heartbeat.py` → `build_vcp03_burn_in_log.py`. Protocol: `docs/current/VCP_03_COHERENCE_BURN_IN_PROTOCOL.md`.
- **VCP-04 — Shadow Judgment:** NOT STARTED. Requires 10 passing burn-in days + operator sign-off.
- **Learning doctrine:** VÉLØ learns from every event. Only clean, verified events are allowed to train or promote predictive rules. Dirty events become failure-memory, not model-food. Three lanes: MEMORY_CAPTURE_OPEN (always) · FAILURE_LEARNING_OPEN (always) · PROMOTION_LEARNING_GATED (clean evidence only).

## Phase A–D Audit Corpus (added 2026-06-28)
- **Sigma local corpus:** `scripts/audit/build_sigma_local_corpus.py` → `data/training/sigma_local_corpus_latest.parquet` (1,050 rows, 36 dates, SR=26.7%). Run after any new sigma dates to extend.
- **Top gates (shadow/advisory only):** VP≥0.40+HIGH_CONF SR=54.2% (n=83) · VP+IMP≥0.4 SR=55.6% (n=36) · VP+MDS≥0.3 SR=52.8% (n=53) · RS≥1.5 SR=44.7% (n=38)
- **Going code bug (A-3):** FIXED (`09f3252` + `8753b4f`). Both `paper_scorer.py` and `new_build_two_lane_score.py` now use -1 to 2 scale matching raceform_v17 training (Heavy=-1, Good=1, Firm=2). Median fallback corrected to 1.0. Regression tests in `tests/test_new_build_paper_scorer.py` (6 tests, all pass). Operator approved 2026-06-29.
- **RPDC missing tags:** STABLE_WARM / MARK_READY / MARK_NEAR / COURSE_RETURN absent from all May–Jun 2026 data. Investigate Supabase `runner_release_candidates`.
- **New scrapers/parsers:** `scripts/ops/scrape_bha_going_stick.py` (D-1, shell ready) · `scripts/ops/parse_runner_notes.py` (D-3, verdict intel only)

## What is BLOCKED / KNOWN ISSUES (as of 2026-06-28)
- **Telegram scoring alerts:** DISABLED (`--no-notify`).
- **Railway cron:** FAIL_OR_UNPROVEN — every run is manual.
- **Local test suite:** pytest 6.2.5 incompatible with pytest-asyncio 1.3.0; 3 test modules have import drift. **30/30 governance tests pass** (governance-v1-hardened tag @ `2cc135a`).
- **Learning gate:** Check daily — blocked on DEGRADED/UNKNOWN source or Council verdict not `PASS_TO_LEARNING`.
- **`build_rp_results_url_list.py`:** Requires a manifest in `racing_post_account_raw/live-full-racepages-YYYY-MM-DD*/`. If raw capture directory is absent, build the URL list directly from `racecard_injection.json` source_urls (replace `/racecards/` → `/results/`).

## What must happen BEFORE scoring
1. **Governed Task Runner mandatory:** All session commands must run via `python scripts/ops/governed_task_runner.py`.
2. Hardening log verification (`python scripts/ops/verify_hardening_state.py`) passes.
3. Branch protection readiness verification (`python scripts/ops/verify_branch_protection_readiness.py`) passes.
4. `worktree_safety_runner.py` (chained) passes.
5. `task_contract_runner.py` (chained) preflight passes.
6. `side_effect_sentinel.py` (chained) audit passes.
7. `python scripts/ops/velo_session_start_check.py` passes.
8. RP index + race pages captured; injection parsed; `validate_rp_injection.py` exits 0.
9. `build_racecard_merged_from_injection.py` and `build_rpdc_daily.py` run from the SAME injection path (`FINAL_CAPTURE_LABEL` chosen once at Step 4).

## What must happen AFTER results (~21:00 BST) — Steps 10-20
```
Step 10A: python scripts/ops/build_rp_results_url_list.py --date YYYY-MM-DD --execute
Step 10B: python scripts/ops/racing_post_account_collector.py capture \
          --url-list data/racing_post_url_lists/rp_results_YYYY-MM-DD.txt \
          --date rp-results-YYYY-MM-DD --execute --headed
Step 11:  python scripts/ops/parse_rp_results_capture.py \
          --date YYYY-MM-DD --capture-date rp-results-YYYY-MM-DD --execute
Step 12:  python scripts/ops/run_results_sigma.py --date YYYY-MM-DD --source cache
Step 12B: python scripts/ops/run_multimodel_sigma.py --date YYYY-MM-DD --execute
Step 13:  python scripts/ops/ingest_results_to_horse_runs.py --date YYYY-MM-DD
Step 14:  python scripts/ops/build_sigma_retrieval_corpus.py
Step 15:  python scripts/ops/update_mission_control.py
Step 16A: python scripts/audit/vp30_operator_card.py
Step 16B: python scripts/audit/run_velo_council.py
Step 17:  python scripts/ops/run_execution_bridge_shadow.py --date YYYY-MM-DD --mode SIM --audit-results
Step 18:  python scripts/ops/build_innovation_protocol.py --date YYYY-MM-DD
Step 19:  python scripts/ops/router_shadow_audit.py --prev-csv data/router_shadow_audit_latest.csv
Step 20:  python scripts/ops/nightly_eod_learning_runner.py
```
`DAY COMPLETE` only when all pass plus final Council + Mission Control refresh.

**Note on Step 10A fallback:** If `build_rp_results_url_list.py` fails (no manifest), generate URL list directly from `racecard_injection.json` (replace `/racecards/` → `/results/`) and write to `data/racing_post_url_lists/rp_results_YYYY-MM-DD.txt`.

## What makes a day CLEAN vs DEGRADED
- **CLEAN:** observability `source_truth: RP_MERGED_CLEAN`, `flatline_count: 0`, `identity_failure_count: 0`, 100% races persisted.
- **DEGRADED:** >50% of runners missing `pdf_intel.postdata_score`/`or_compression_score` (`src/velo/source_truth_enforcer.py:98-117`). Scoring proceeds; learning is blocked.
- Mission Control derives `source_truth` from the latest observability packet (`UNKNOWN` when missing/malformed, never CLEAN by default) and blocks learning on DEGRADED/UNKNOWN. Tests: `tests/test_mission_control_source_truth.py`.

## What blocks learning (any one of)
Degraded/unknown source · Council verdict not `PASS_TO_LEARNING` · pipeline truth `MANUAL_RECOVERY_ONLY` · contaminated run IDs (`MC_CONFIG.CONTAMINATED_RUN_IDS`) · flatline/identity failures · Playbook G `live_sentient_state_touched != false`.

## Next safe command
```
python scripts/ops/velo_session_start_check.py
```

## NEVER touch without operator approval
Live weights/profile in `velo_prime_ensemble.py` · `models/sqpe_v17/` and `models/specialist/` · `app/agents/betfair_execution_agent.py` + `betfair_trading_agents.py` (never import into live path) · LIVE guard in `src/velo/execution_bridge.py` · `data/sentient_state.json` · Sigma Telegram format (LOCKED) · old verdicts in Supabase · `MC_CONFIG.CONTAMINATED_RUN_IDS`.

## 2026-07-04 Raceday State — LIVE / SIGMA READY BUT NOT RUN

**Source capture:** THE_ONE_TRUTH live RP scrape Steps 1-6 completed. 51 races, 8 courses, 453 active runners, 0 null off_times. Standard cache: `data/racecards_2026_07_04_standard.json`. RP `horse_id` coverage 453/453 = 100%. Historical passport ID coverage 242/453 = 53.4%. Identity risk: LOW. History depth risk: HIGH. Remaining gap: 211 runners without historical passport depth.

**Scoring:** Local dry scoring completed first — `run_prime_today.py --date 2026-07-04 --source cache --dry-run --no-runner-snapshots --no-notify`, 51/51 races processed, exit 0. Tier count: A=4, B=25, C=13, D=3, X=6.

**Verdict persistence:** Controlled verdicts-only persistence authorised and executed — `run_prime_today.py --date 2026-07-04 --source cache --verdicts-only --no-runner-snapshots --no-notify`. `public.velo_verdicts`: 51 rows / 51 races. `race_type`, `race_type_raw`, `race_type_source`, `race_type_recorded_at`, `predicted_field_size`, `full_analysis`, `top_rank_horse_id` all 51/51. **SIGMA-26 persistence patch: PRODUCTION VERIFIED.**

**RPDC:** Build authorised and executed — `scripts/ops/build_rpdc_daily.py --date 2026-07-04`. `public.runner_release_candidates`: 453 rows. Race coverage 51/51, runner/horse_id coverage 453/453, no duplicates, no null `race_id`/`horse_id`. Verdict refresh executed after RPDC build. RPDC attached to verdicts: 51/51 via `rpdc_primary_tag`, `rpdc_release_score`, `rpdc_tags`.

**Dashboard:** Reports published. Dashboard server started — `scripts/ops/new_build_dashboard_server.py`, local endpoint `http://localhost:8765/dashboard`, route returns HTTP 200. Dashboard truth API: `verdict_count_today = 51`, Supabase status `CONNECTED`. Status: `RPDC_ENRICHED_VERDICTS_ON_DASHBOARD`. `sp`/`odds`/`bsp` still null — pre-existing market-data publisher gap, disclosed, not fabricated.

**Forbidden / untouched:** `sigma_audits` 0 rows for July 4 · `runner_prediction_snapshots` 0 rows for July 4 · local `runner_snapshots_*.jsonl` unchanged (116) · Telegram no real sends (containment/no-op only) · model training not run · model promotion not run · historical backfill not run · VFU-21 not run · COURSE-01 not run.

**Current gate:** `RACEDAY_LIVE_VERDICTS_READY` · `RPDC_ENRICHED_VERDICTS_READY` · `DASHBOARD_LIVE` · `SIGMA_29_READY_BUT_NOT_RUN` · `SIGMA_LEARNING_WAIT_UNTIL_LATER_TONIGHT` · `PROMOTION_LEARNING_GATED` · `FAILURE_LEARNING_OPEN` · `MEMORY_CAPTURE_OPEN`.

**Decision:** Do not run Sigma yet. Do not run model learning yet. Wait until later tonight for Sigma learning / results-based audit. Next authorised decision point: SIGMA-29 controlled Sigma rehearsal, after race results are available and operator signs off.

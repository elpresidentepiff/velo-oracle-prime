# ONE TRUTH — VÉLØ ORACLE PRIME

> **IF THIS FILE CONFLICTS WITH ANY OTHER DOC, THIS FILE WINS UNTIL OPERATOR SAYS OTHERWISE.**

**Effective:** 2026-06-26 (updated from 2026-06-10 baseline) · **Branch:** `main` · **HEAD:** `c33cece` · **Verified against code, not docs.**

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

## Phase A–D Audit Corpus (added 2026-06-28)
- **Sigma local corpus:** `scripts/audit/build_sigma_local_corpus.py` → `data/training/sigma_local_corpus_latest.parquet` (1,050 rows, 36 dates, SR=26.7%). Run after any new sigma dates to extend.
- **Top gates (shadow/advisory only):** VP≥0.40+HIGH_CONF SR=54.2% (n=83) · VP+IMP≥0.4 SR=55.6% (n=36) · VP+MDS≥0.3 SR=52.8% (n=53) · RS≥1.5 SR=44.7% (n=38)
- **Going code bug (A-3):** Both `paper_scorer.py:189` and `new_build_two_lane_score.py:82` use wrong 0–8 scale (training uses -1 to 2). Fix NOT applied — operator decision pending. See `VELO_HARDENING_STATE.md`.
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

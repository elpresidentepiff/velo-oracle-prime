# ONE TRUTH — VÉLØ ORACLE PRIME

> **IF THIS FILE CONFLICTS WITH ANY OTHER DOC, THIS FILE WINS UNTIL OPERATOR SAYS OTHERWISE.**

**Effective:** 2026-07-08 (updated from 2026-06-29 baseline; see STANDARD DAILY OPERATION section below) · **Branch:** `audit/local-01-truth-reconciliation` (working tree; `main` HEAD `8753b4f` is stale — see `data/reports/local_salvage_01_*` and `data/reports/repo_01_*` for reconciliation state) · **Verified against code, not docs.**

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

## CANONICAL MODEL TRUTH SPINE (added 2026-07-06, MODEL-TRUTH-01..04)

- Dirty/local runtime artifacts are evidence, not final truth.
- GitHub stores reviewed code, law, generated proof artifacts, and regression tests.
- Supabase canonical tables (`public.canonical_model_scorecards`, `public.canonical_learning_events`) are the operational truth source for model scorecards and learning events.
- Dashboard must read `canonical_model_scorecards` and `canonical_learning_events` for model/result/learning truth.
- Dashboard must not invent model truth from ad-hoc local JSON, stale sidecar outputs, or prose reports.
- Sigma remains result reconciliation truth, but model-rank and policy learning must join through canonical scorecard rows.
- No model claim is accepted unless backed by: `source_path`, `source_field`, `race_id`, `horse_id`, `rank`, `odds`, `result`, `policy_decision`, `stake_authorised`, `learning_class`.
- **Little Lady Rock 2026-07-05 is the regression anchor**: New Build Lane A/B rank 1, SP 41.0, policy `NO_EDGE`, `stake_authorised=false`, learning `VALUE_DISCOVERY_POLICY_BLOCKED`, no promotion.
- Any future dashboard panel that displays model truth must either read canonical endpoints, or be explicitly labelled runtime/local/non-canonical.

Canonical dashboard consumer endpoints (`scripts/ops/new_build_dashboard_server.py`, read-only, no Supabase writes):
- `GET /api/canonical-scorecard?date=YYYY-MM-DD`
- `GET /api/canonical-learning-events?date=YYYY-MM-DD`
- `GET /api/canonical-race-truth?date=YYYY-MM-DD&race_id=<race_id>`

Builders: `scripts/ops/build_canonical_model_scorecard.py`, `scripts/ops/persist_canonical_model_scorecard.py`, `scripts/ops/build_canonical_learning_events.py`. Law: `docs/current/MODEL_RESULT_REPORTING_LAW.md`. See also `docs/current/VELO_MODEL_SOURCE_MAP.md`.

**Wired into the daily pipeline 2026-07-16.** Before this date, `canonical_model_scorecards` stopped dead at 2026-07-07 (2,511 rows) because the build+persist steps existed but were never called from `run_full_raceday.py` — New Build and Champion Intent were producing genuine daily pre-race scorecards that simply never reached the canonical join, so Multi-Model Sigma reported `n/a` for both every day regardless of real performance (root-caused in the RACE-DAY-15 forensic PR, `SCORECARD_GENERATED_NOT_PERSISTED`). `run_full_raceday.py` now runs `build_canonical_model_scorecard.py --date` then `persist_canonical_model_scorecard.py --date --csv <path> --execute` as its final two steps, every morning, non-critical (won't block the day on failure, but should not silently stay broken either — check `data/reports/canonical_model_scorecard_{date}_audit.json`'s `sources_missing` field daily).

Also fixed the same day: `build_canonical_model_scorecard.py` never had a Champion Intent Shadow block at all (not just "never called" — the model type didn't exist in the builder's source). Added a block reading `data/reports/intent_shadow_scorecard_{date}.csv`, joining results by horse name the same way New Build does, tagged `CHAMPION_INTENT_SHADOW`, `stake_authorised=false`, `dashboard_visible` read from the source CSV's own field, `policy_decision` carrying the row's `trust_policy` (`ARCHIVE_CONTEXT_ONLY_NOT_SCORING`). This does **not** change Champion Intent's promotion eligibility, staking authority, or trust policy — it only means its real daily performance is now measured and visible instead of silently dropped.

## STANDARD DAILY OPERATION (added 2026-07-08 — supersedes ad-hoc manual Steps 1-9.6)

**This is now mandatory, not optional, and not something the operator should have to ask for.** Before 2026-07-08, each of Steps 1-9.6 required a separate manual command, and in practice most days only Step 9 (core scoring) actually ran — New Build, Champion Intent Shadow, and RPDC sat empty for days at a time because nobody ran the rest. This is now one command, and it is scheduled.

### The one command
```
PYTHONPATH=. python scripts/ops/run_full_raceday.py --date YYYY-MM-DD --execute
```
Runs, in order: RP session health check (fails fast with the exact fix command if the
login is dead) → Steps 1-3 (live racecard capture) → Steps 4-5 (parse/validate) → Step 6
(New Build current-card feed) → Step 8.5 (RPDC) → Step 9 (live scoring — **idempotent**,
skips and never overwrites if today's `velo_verdicts` already exist) → Steps 9.1-9.6
(paper intelligence overlays) → New Build two-lane score → Champion Intent Shadow
(features + scorecard). Writes a per-day report to
`data/reports/run_full_raceday_YYYY_MM_DD.json` listing pass/fail per step.
Non-critical step failures do not stop the chain; critical ones (capture, parse,
validate, scoring) do.

### It is scheduled — local cron, not a cloud agent
Installed 2026-07-08 via `crontab` on the operator's own machine (not a Claude cloud
routine — cloud routines run in a fresh sandbox with no access to the local RP browser
session or `.env` secrets, so they cannot run this pipeline). Schedule:
```
CRON_TZ=Europe/London
0 7 * * * cd <repo> && PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py --date $(date +%Y-%m-%d) --execute >> data/reports/run_full_raceday_cron.log 2>&1
```
07:00 UK time, every day (DST-aware via `CRON_TZ`), before racing starts. **This only
fires while the operator's machine/WSL instance is actually running** — same limitation
as any local scheduler, worth knowing.

### The timing constraint is hard, not a preference
Confirmed 2026-07-08: Racing Post's live `/racecards/{date}` index page drops a course
entirely from the listing once that course's whole card has finished racing. Running
live capture late in the day (e.g. mid-afternoon) permanently loses RPDC/New Build/
Champion Intent Shadow coverage for any course that raced before the capture — there is
no way to recover it afterward, the source page itself stops listing the course.
Catterick and Yarmouth were lost this way on 2026-07-08 (12 of 33 races). **This is why
the cron fires at 07:00, before the first UK race of the day.**

### RP session health — checked automatically now
`scripts/ops/check_rp_session_health.py` — a ~2-second live probe of the saved browser
profile's login state (fetches one horse-profile page, checks the real `isLogged` flag).
Wired into `scripts/ops/velo_session_start_check.py` as check #11, and into
`run_full_raceday.py`'s pre-flight. Root cause it exists: on 2026-07-08 a dead session
caused 92% capture failure (146 attempts, only 11 real successes) before anyone noticed
— now caught in 2 seconds instead of after hundreds of wasted requests. If the session
is dead, fix is interactive and cannot be automated (RP login requires a human to type
credentials into a real browser window):
```
python scripts/ops/racing_post_account_collector.py init-login \
  --profile-dir data/browser_profiles/racing_post_account_firefox \
  --execute --wait-seconds 90
```
Use `--wait-seconds` (not the old blocking `input()` prompt) when invoking through a
non-interactive pass-through session (e.g. Claude Code's `!` prefix) — `init-login`
auto-detects a non-TTY stdin and waits a fixed window instead of hanging on `EOFError`.

### Which models need which data source — stop guessing
| Model | Needs live RP capture? | Needs passport bank? | Needs PDF ratings sheets? |
|---|---|---|---|
| MAIN_VELO_PRIME / OLD_VELO_WIN/PLACE/LONGSHOT | Yes (or PDF fallback) | No | Optional, additive context only |
| SQPE_NO_RPR_SHADOW (No-RPR) | Yes (or PDF fallback) | No | No |
| NEW_BUILD_LANE_A/B/C | **Yes, live capture only — PDF fallback does not work** | **Yes** (join by `horse_rp_uid`) | No |
| NEW_BUILD_POLICY_V1 | Yes, live capture | Yes (via New Build lanes) | No |
| CHAMPION_INTENT_SHADOW | **Yes, live capture only** (needs `data/racecards_{date}_standard.json`) | Indirectly — uses `data/race_shape/form_history_*.json`, built from the same horse-profile scrapes as the passport bank | No |
| RPDC (release-signal layer, all lanes read it) | **Yes, live capture only** (`build_rpdc_daily.py` reads the exact injection JSON) | No | No |

**PDF ratings sheets (F_0010/0011/0012/0015/0016/0032) are a supplementary/fallback
source, not a substitute for live capture.** They feed Old VELO and No-RPR fine (via
`ingest_racecard_pdfs.py` → `racecard_merged`), but New Build, Champion Intent Shadow,
and RPDC all structurally require the live browser-injection racecard (real RP
race_ids/horse_uids), and none of them have a PDF-sourced fallback path. A PDF-only day
(like 2026-07-04 and the morning of 2026-07-08) will score Old VELO/No-RPR cleanly and
leave the other three lanes permanently blank for that day.

### Dashboard — one server now, not two
`app/main.py` is now the single canonical dashboard server (port 8000). Until
2026-07-08 there were two FastAPI apps (`app/main.py` and
`scripts/ops/new_build_dashboard_server.py`) serving the identical static
`app/static/dashboard/index.html` but with *different* API route sets — whichever one
happened to be running determined which panels worked. This caused the Champion Intent
Shadow panel to silently show "No Champion Intent data" for a full session, because the
frontend's `/api/model-suggestions` call only existed on the server that wasn't running.
`app/main.py` now has every route `new_build_dashboard_server.py` has (verified via
route-set diff; `new_build_dashboard_server.py` is kept only because `app/main.py`
imports its `fetch_canonical_scorecard`/`fetch_canonical_learning_events`/
`_remap_numeric_race_ids` helpers — do not run it standalone). Launch with:
```
PYTHONPATH=. python -c "from dotenv import load_dotenv; load_dotenv(); import uvicorn; uvicorn.run('app.main:app', host='0.0.0.0', port=8000)"
```
(plain `uvicorn app.main:app` or `python app/main.py` will NOT load `.env` first and
will fail Supabase schema verification at startup — neither the module nor its
`__main__` block calls `load_dotenv()` itself.)

### Bugs fixed 2026-07-08 (worth knowing if similar symptoms recur)
- `run_results_sigma.py` `COURSE_ALIASES` had no `trm`→`tramore` entry — silently failed
  the course+time join for every Tramore race (would have blocked a whole day's Sigma
  under the 95% completeness gate). Check this table first if a specific course's races
  show `NO_RESULT_MATCH` despite results existing.
- `racing_post_account_collector.py`'s capture manifest was written once at the end of a
  batch, not incrementally — a killed/timed-out process lost all resumption progress,
  causing repeated re-attempts of the same URLs across "successful" resumed runs. Fixed:
  manifest now writes after every single capture, and the write itself is atomic
  (temp-file + `os.replace`) so a kill signal mid-write can never truncate it to 0 bytes.
- `app/main.py`'s `/api/dashboard-truth` `a_supabase` block used `pipeline_runs.completed_at`
  (real column is `finished_at`) and `velo_verdicts.date` (no such column — use
  `race_id LIKE '%YYYYMMDD%'`), plus read `SUPABASE_KEY` (anon key, blocked by RLS on
  `velo_verdicts`) instead of `SUPABASE_SERVICE_ROLE_KEY`. All three silently produced
  `SUPABASE_UNAVAILABLE`/wrong counts instead of erroring loudly. Fixed.
- `run_results_sigma.py` had no way to suppress Telegram — added `--no-notify` (mirrors
  `run_prime_today.py`'s existing flag). Use it for any investigative/backfill Sigma run;
  omit it for the real nightly Step 12, which is the one case the locked Telegram format
  is meant to fire for.

## EW Tracking (added 2026-06-22)
EW_CANDIDATE flag now tracked in sigma and multimodel ledger. `run_results_sigma.py` emits `ew_outcome` per verdict. `run_multimodel_sigma.py` includes `velo_ew_outcome` column.

## Dashboard Race Cards (added 2026-06-22/23)
- Product badge (WIN/E-W/VISION/PASS) on Old VELO race cards (`DASH-01`)
- Old VELO three-option card (WIN/PLACE/LONGSHOT role assignment) wired into full pipeline (`c33cece`)
- New Build lane join bug fixed 2026-07-18: `_build_governed_card_from_live_snapshots()`
  in `new_build_dashboard_server.py` was remapping New Build's race_id to the wrong
  scheme before joining live snapshot rows (which use plain numeric race_id already) —
  broke the join 100% of the time, showing "No New Build data" every day. `app/main.py`'s
  production governed-card was never affected (dual-keyed already).
- `/api/plot-conviction` (High-Conviction PDF Picks panel) wired 2026-07-18: reads
  postdata_score/plot_conviction from `racecard_merged`, joined with Deep Race Agent's
  verdict. Frontend panel existed as a dead placeholder before this.

## What is DEPRECATED
Racing API as a data source (decommissioned 2026-05-14; client files deleted) · Sporting Life scraper (`scrape_results_sl.py`) · `velo_race_day_button.py` (do not use as authority) · `scrape_results_atr.py` (does not exist — any doc naming it is stale) · root `Makefile` (Benter v10.1 era) · root `cron.txt` (`/home/ubuntu` paths) · `COMMAND.json`.

## What is EXPERIMENTAL
International prerace arenas (`scripts/audit_international_*`) · HK/FR feature builders · Intent Layer V1 (patched, rerun required) · sqpe_v18 (NO_LIFT verdict, not wired) · Race Shape v1 (shadow only, form history parser live).

## In-Running Comment + Trainer Intent Tags (added 2026-07-10)
RP's per-horse in-running comment (e.g. "Made all, pushed along before 3 out,
ran on well") is now captured and classified — internal rule-based tagging
only, no external NLP/sentiment service.
- **Capture:** `parse_rp_results_capture.py` extracts each horse's sibling
  `.rp-horseTable__commentRow` from the raceday results HTML into
  `runner["in_running_comment"]`.
- **Persistence:** `ingest_results_to_horse_runs.py` (Step 13) writes it to
  Supabase `racing_horse_runs.in_running_comment` (migration
  `supabase/migrations/20260710_001_add_in_running_comment.sql`, applied
  2026-07-10; NULL for runs ingested before that date, not backfilled).
- **Classification:** `parse_runner_notes.py` (Step 13B) runs two independent
  tag families over RP text:
  - `FADE_PATTERNS` (existing) — why a horse ran badly: `BLED`, `LAME`,
    `HAMPERED`, etc., sourced from `comment_intel_score`/`nds_narrative` in
    the verdict JSON.
  - `TRAINER_INTENT_PATTERNS` (new) — why the yard ran it at all:
    `EDUCATIONAL_RUN`, `NEEDED_THE_RUN`, `EXPERIENCE_RUN`, `NOT_FULLY_TRIED`,
    `EASED_WHEN_BEATEN`, `CONNECTIONS_QUOTE_PRESENT` (flags any `(jockey
    said...)`/`(trainer said...)` aside for operator review regardless of
    keyword match) — sourced from the new `in_running_comment` field via
    `data/results/rp_results_YYYY_MM_DD.json`.
  Output: `data/runner_notes_YYYY_MM_DD.json`, `trainer_intent[]` array.
  Validated 2026-07-10 against 489 real comments: 14 `CONNECTIONS_QUOTE_PRESENT`
  hits, 0 false positives on ordinary running-line language.
- **Status:** `trust_policy: ARCHIVE_CONTEXT_ONLY_NOT_SCORING`,
  `velo_scoring_allowed: false` — shadow/context only, not wired into
  `HorsePassport` or live scoring yet.

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
10. **No scoring until passport + RP PDF ingestion confirmed complete (added 2026-07-18).**
    `scripts/ops/check_scoring_readiness_gate.py` hard-wired into both `run_prime_today.py`
    (own entry point, unbypassable) and `run_full_raceday.py` (before Step 9). Checks New
    Build's passport feed exists (never overridable) and every GB/IRE venue has RP PDF
    fields merged into `racecard_merged` (USA/international auto-exempt via region field).
    Override PDF-only check with `--allow-missing-pdfs`. The four core models — Old VELO,
    New Build, No-RPR/SQPE Shadow, Champion Intent Shadow — are `critical=True` in
    `run_full_raceday.py`: a failure in any one fails the whole day, no silent partial pass.
    See THE_ONE_TRUTH.md HARD RULES #8-9 for full rationale.

## What must happen AFTER results (~21:00 BST) — Steps 10-20
```
Step 10A: python scripts/ops/build_rp_results_url_list.py --date YYYY-MM-DD --execute
Step 10B: python scripts/ops/racing_post_account_collector.py capture \
          --url-list data/racing_post_url_lists/rp_results_YYYY-MM-DD.txt \
          --date rp-results-YYYY-MM-DD \
          --profile-dir data/browser_profiles/racing_post_account_firefox \
          --execute --headed
          (--profile-dir is REQUIRED -- omitting it silently falls back to
          DEFAULT_PROFILE_DIR, an uninitialized/non-logged-in Chromium
          profile, and the browser crashes on launch. Root-caused 2026-07-10.)
Step 11:  python scripts/ops/parse_rp_results_capture.py \
          --date YYYY-MM-DD --capture-date rp-results-YYYY-MM-DD --execute
Step 12:  python scripts/ops/run_results_sigma.py --date YYYY-MM-DD --source cache
Step 12B: python scripts/ops/run_multimodel_sigma.py --date YYYY-MM-DD --execute
Step 13:  python scripts/ops/ingest_results_to_horse_runs.py --date YYYY-MM-DD
Step 13B: python scripts/ops/parse_runner_notes.py --date YYYY-MM-DD
          (TRAINER_INTENT tags from RP in-running comments -- see
          "In-Running Comment + Trainer Intent Tags" section below)
Step 14:  python scripts/ops/build_sigma_retrieval_corpus.py
Step 15:  python scripts/ops/update_mission_control.py --date YYYY-MM-DD
Step 16A: python scripts/audit/vp30_operator_card.py
Step 16B: python scripts/audit/run_velo_council.py --date YYYY-MM-DD
Step 17:  python scripts/ops/run_execution_bridge_shadow.py --date YYYY-MM-DD --mode SIM --audit-results
Step 18:  python scripts/ops/build_innovation_protocol.py --date YYYY-MM-DD
Step 19:  python scripts/ops/router_shadow_audit.py --prev-csv data/router_shadow_audit_latest.csv
Step 20:  python scripts/ops/nightly_eod_learning_runner.py --date YYYY-MM-DD
          (--date REQUIRED -- omitting it defaults to yesterday, which will
          FAIL if yesterday has no scored data. Root-caused 2026-07-10.)
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

# ONE TRUTH — VÉLØ ORACLE PRIME

> **IF THIS FILE CONFLICTS WITH ANY OTHER DOC, THIS FILE WINS UNTIL OPERATOR SAYS OTHERWISE.**

**Effective:** 2026-07-29 (post one-truth consolidation PR #155 + branch sweep; prior baseline 2026-07-25) · **Branch:** `main` — THE only branch, local and remote; the sweep deleted 97 remote + 72 local branches, every non-bot unmerged tip preserved at `archive/2026-07-29/*` tags (see `docs/current/BRANCH_SWEEP_2026_07_29.md`) · **Verified against code, not docs.**

**This file supersedes:** `THE_NEW_TRUTH.md`, `CURRENT_RUNTIME_TRUTH.md`, root `CLAUDE.md` state claims, all numbered docs in `docs/` flat directory.
**This file defers to:** root `THE_ONE_TRUTH.md` for step-by-step command detail (Steps 1–20), `docs/current/RACE_DAY_RUNBOOK.md` for the lifecycle.
**Agent wiki (added 2026-07-06, DOCS-01):** `docs/current/SYSTEM_MAP.md` (architecture), `docs/current/AGENTS.md` (roles), `docs/current/VFU_INDEX.md` (VFU-01 to VFU-21 index), `docs/current/CURRENT_STATE.md` (fast orientation), `docs/current/FORBIDDEN_ACTIONS.md` / `docs/current/LIVE_VS_DRY_RUN.md` (safety vocabulary), `docs/current/ARTIFACT_REGISTRY.md` (output index). This file remains the single source of truth for state; the wiki is navigation, not a second truth file.

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
| RPR in the live model | `sqpe_v17.pkl` genuinely uses RPR (`rpr_num`+`rpr_vs_field` ≈ 50% of its real feature importance) — grandfathered by deliberate 2026-06-19 design, not a leak. See `docs/engineering/SOURCE_INCLUSION_POLICY_V1.md` for the full rationale and the empirical mid-price/short-fav band split that justifies it. New Build, Champion Intent Shadow, and No-RPR Shadow genuinely exclude it. |
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

**Ledger join fixed + backfilled 2026-07-29 (`7b9d4f2`):** sigma's switch to raw
numeric race_ids (verdict_loader migration `ed7d4a9`, 2026-07-25) made the
numeric→velo remap corrupt every New Build/Champion join — both models silently
recorded NO_DATA on all dates since 2026-07-14 while their scorecards existed and
matched 53/54. Join now matches raw ids against sigma first (remap is legacy
fallback only), a tripwire hard-fails the run instead of writing a ledger where a
loaded model joins zero races, and 13 dates (May 30 – Jul 27) were backfilled.
First honest cumulative table: Old VELO 25.9% (n=1527) · No-RPR 25.3% (n=1167) ·
New Build 15.8% (n=1152) · Champion 22.2% (n=383).

**Two lanes added 2026-07-29 (operator-approved):** `mp_*` = Mid-Price Specialist
shadow (scorer `run_midprice_shadow_today.py`, Step 9.1b, non-critical, band 3.0-10.0,
market-blind staging model) · `nbc_*` = New Build Lane C soft-label challenger (read
from the same two_lane_readiness report as Lane A). Both backfilled over 39 cached
pre-race racecard dates (retrospective scoring of pre-race data — clean, but labelled:
forward rows begin 2026-07-30). Honest first table (flat-stake top-pick, NO gate):
Old VELO -33.9% ROI · Midprice n=1296 SR=14.4% ROI=-32.8% · Lane C n=661 SR=16.9%
ROI=-15.7% · Champion -14.8%. Specialist v1 catches only 11% of VELO's mid-priced
misses (weak as a cure, genuinely independent: 16% pick overlap). Watch-gate:
**mp_prob>=0.30 → n=27 SR=48.1% ROI=-0.1%** (breakeven, tiny n — accumulate forward).

**Lane C promotion gate (operator-set 2026-07-29):** no promotion talk before
n>=1000 Lane C ledger races AND Lane C win-SR beats Lane A by >=2ppts on the same
races AND flat-stake ROI gap confirmed. Check with the cumulative table in Step 12B
output. Backtest AUC (0.7028) is NOT promotion evidence on its own.

**Midprice lane gate:** mp_prob>=0.30 subset must reach n>=150 before any verdict.
If SR>=40% holds there, escalate to operator for an EW-overlay decision; if it decays
toward base rate, retire the lane and return to feature work (issues #78/#80).

## SUBSYSTEM TRUTH BOARD (audited 2026-07-29, all claims reproduced not assumed)

| Subsystem | Truth |
|---|---|
| Mid-price misses | 170 of 263 classified misses (65%) are `mid_priced_won` (median winner SP 4.8). Snapshot-verified on 152 of them: winner at VELO rank 2-3 in only 38%; **62% ranked 4th or deeper, median VP gap 0.234** — a genuine model blind spot on mid-priced runners, NOT a near-miss selection issue. Fix path is model/feature work (midprice specialist staging model exists at `models/sqpe_v17_midprice_specialist_staging/`, issues #78/#80, Track A module at tag `archive/2026-07-29/feature/issue-78-midprice-hunter-module`), not a pick-2 tweak. |
| LLM Council | **The council contains zero LLM calls** — `src/velo/council/agents.py` is deterministic rules (by design, Block 3 audit). It works when run: Jul 24 PASS_TO_LEARNING, Jul 25/26/27 WATCH_ONLY (SR below baseline those days — honest). Gap found+fixed 2026-07-29: council never ran Jul 19-26 (EOD Step 16b is non-critical and EOD didn't run); Jul 24-27 backfilled. Adding real LLM deliberation = new feature, operator decision (API cost + doctrine). |
| Deep Race Agent | Rule-based (no LLM). WORKING — produced v1+v2 for 2026-07-29 after the `7fc1da2` PDF-dir fix. |
| LLM Intel Briefs | LIVE 2026-07-29 (operator-approved, key installed): `scripts/ops/run_llm_intel_brief.py` via OpenRouter (`sk-or-*` key auto-routes; model `deepseek/deepseek-v4-pro`; `DEEPSEEK_API_KEY`/`DEEPSEEK_MODEL`/`DEEPSEEK_API_URL` in `.env`). Morning `--mode suggestions` (after Sidecar Stack in `run_full_raceday.py`) + night `--mode eod` (Step 16c in `run_full_raceday_eod.py`). Reasoning-model gotcha handled: max_tokens 5000, empty-completion refuses to write. First live brief 2026-07-29 verified evidence-cited. ARCHIVE_CONTEXT_ONLY_NOT_SCORING, no Supabase/Telegram. Output: `data/reports/llm_brief_{mode}_{date}.md/.json`. **Dashboard:** `/api/llm-brief` + LLM INTEL BRIEF panel; `/api/midprice-shadow` + MID-PRICE SPECIALIST SHADOW panel (green border = mp_prob>=0.30 watch-gate picks), both in `app/main.py` + `index.html`. |
| Mission Control | WORKING and honest. 2026-07-27: `source_truth=RP_MERGED_CLEAN`, `learning_gate_status=BLOCKED` (reasons: `GATE_COUNCIL_WATCH_ONLY`, `GATE_PIPELINE_TRUTH_MANUAL_RECOVERY_ONLY`). The field is `learning_gate_status`, not `learning_gate`. |
| Sidecars | Stack builder is `scripts/audit/sidecar_stack_operator_card.py` (Step 9.x, non-critical in `run_full_raceday.py`) — goes stale whenever mornings run manually/partially. Refreshed 2026-07-29 (6 stacks, OPERATOR_VISIBILITY_ONLY). Calibration pipeline blockers unchanged: course_id mapping + dist_f format. |
| Training | Live = sqpe_v17.1 (frozen). Staging, unpromoted: `sqpe_v17_midprice_specialist_staging`, `rpdc_specialist_staging`, `sqpe_v17_staging`. New Build Lane C (soft-label challenger, backtest AUC 0.7028 / SR +3.4ppts) is wired in the two-lane scorer and scoring daily; **promotion = operator decision, still open**. Honest ledger says New Build lane A = 15.8% vs Old VELO 25.9% (n=1152/1527). |
| Learning loop | Fixes 1-5+7 live; Fix 6 (G live flip) blocked until ≥2026-10-28 pending 3 months post-reset sigma. Gate pre-flight (Fix 3) now genuinely blocks: needs sigma PASS + council PASS_TO_LEARNING + MC OPEN. VCP-03 burn-in at 2/10, next append via Step 20B tonight. |

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

### It is scheduled — Windows Task Scheduler, not WSL cron (changed 2026-07-29)
The 2026-07-08 WSL crontab fired ZERO times on 2026-07-28 and 2026-07-29 (WSL not
awake at 07:00; cron never catches up a missed firing) — 2026-07-28 was permanently
lost as a result. Replaced 2026-07-29 with Windows scheduled task `VELO_Raceday_0700`:
daily 07:00, `StartWhenAvailable` (runs as soon as the machine is next on if 07:00 was
missed), `WakeToRun`, 4h execution limit. It launches
`scripts/ops/run_full_raceday_scheduled.sh` via `wsl.exe -d Ubuntu`, which logs to
`data/reports/run_full_raceday_cron.log` as before. The old crontab line is removed
(backup: `~/velo_crontab_backup_2026_07_29.txt`). Backstop: session-start check #12
(`check_todays_raceday_ran`) goes CRITICAL if today has no raceday report/verdicts
after 08:00. (Still not a cloud agent — the pipeline needs the local RP browser
session and `.env`, which no cloud sandbox has.)

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

## THE ONE COMMAND, MORNING AND EVENING (added 2026-07-25 — closes the entrypoint census)

Two canonical scripts now cover the entire race day, chosen after live-testing every
candidate against real 2026-07-24 data (see `data/reports/runtime_entrypoint_census_*`
and project memory for the full comparison):

- **Morning:** `scripts/ops/run_full_raceday.py` — Steps 1-9.6 (capture, RPDC, live
  scoring, paper intelligence overlays). Live-tested: 17/17 steps PASS.
- **Evening:** `scripts/ops/run_full_raceday_eod.py` — Steps 10A-20 (results capture,
  sigma reconciliation, full learning loop). New, built 2026-07-25 as the companion to
  the morning script — codifies the exact sequence already run by hand, successfully,
  twice the same week. Live-tested: 12/12 steps PASS.

`scripts/ops/velo_daily_harness.py` is confirmed **BROKEN — DO NOT USE**: its `ROOT`
path resolves one directory too high, silently pointing `DATA`/`SCRIPTS` at the wrong
location. `velo_race_day_button.py`, `run_velo_closed_loop_daily.py`, and
`new_build_race_day_readiness.py` each cover only a partial slice of the day (morning-only,
EOD-audit-only, and read-only readiness-check respectively) — none of them is a real
alternative to the two scripts above.

**One hard caveat on the morning script, found only by actually running it twice on the
same day**: do not rerun `run_full_raceday.py` after race results already exist. Its
Radical Shadow and Tri-Lane Agent Review steps silently degrade into uniform, wrong
output (an entire day's decisions collapsing into one repeated label) while still
reporting PASS — likely because they depend on live market/odds-band data that's no
longer available once results are in. Caught, reverted, not yet fixed at the source; if
you need to re-verify a day, use `run_full_raceday_eod.py`'s steps (all confirmed
idempotent-safe) or check individual report files by hand, not a second morning-script run.

### The `generated_at` write-date-vs-race-date bug class (fixed everywhere, 2026-07-23/25)

`velo_verdicts.generated_at` is write-time, not race-date. Scoring the evening before
race day (the normal, manual operating pattern — see STANDARD DAILY OPERATION above)
stamps `generated_at` under the wrong calendar day, so any query filtering by
`generated_at` for "today's" date silently returns nothing. `race_id` correlates to the
actual race date instead, via the local RP racecard cache for that date.

This exact bug was independently hand-copied into **12 separate scripts** across this
codebase before anyone noticed the pattern — dashboard endpoints, operator cards, sigma
variants, audit/backtest tools, and the daily truth watchdog whose entire job is proving
whether a day scored (which it couldn't, correctly, until fixed). All 12 are fixed.

**Use `src/velo/verdict_loader.load_verdicts(date_str, select=...)` for any new code that
needs "today's verdicts."** It tries race_id membership first, falls back to
`generated_at` only if the local racecard cache is missing (treat that as a signal
something else is wrong, not a normal path), then a local JSON backup as a last resort.
Returns `(rows, method)` so callers can tell when they hit a degraded path. Tested
(`tests/test_verdict_loader.py`, 9 tests) specifically to catch a regression back to
`generated_at`-first querying before it ships again. If you are about to write
`.gte("generated_at", ...)` or `generated_at.startswith(date_str)` — stop, that is the
bug signature, use the shared module instead.

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

## LEARNING LOOP AUDIT — 2026-07-28 (7-Block Analysis)

Full deep-dive into why the learning loop does not affect predictions. Root causes, current state, and ordered fix queue. **Do not implement fixes out of order** — dependencies run bottom-up (calibration → VCP-03 → gates → council → shadow mode lift).

### Block 1 — Runner Blast Radius
`nightly_eod_learning_runner.py` is called ONLY from `run_full_raceday_eod.py` Step 20 as a non-critical subprocess. Risk of changing it: **LOW**.

### Block 2 — Sentient State → Scoring Path
The path EXISTS and is wired — but gated off by env var.

`velo_prime_ensemble.py` loads `data/sentient_state.json` at module import. `_g_shadow_adjustment()` computes a probability multiplier per runner using `doctrine_strengths`, `appetite_state`, and `emotion_laws`. At line 419: `if not _G_SHADOW_MODE: self.velo_prime_prob *= g_mult` — the live path exists but never fires.

**Gate:** `_G_SHADOW_MODE = os.getenv("VELO_G_SHADOW_MODE", "shadow").lower() != "live"` — defaults to `True` forever. Nothing currently sets `VELO_G_SHADOW_MODE=live`.

**G has been evolving** (3,466 races observed, authorized live state update 2026-07-26):
```
LAY_THE_STORY:  0.080  (hammered down from 1.0)
SHADOW_TRACKING: 0.080
ENGINE_SUPREMACY: 1.000  (never fired — no code path triggers it)
TOP_4_ON_DANGER: 8e-20  (dead)
VETP_ECHO:      0.161
[6 other doctrines at 1e-3 to 1e-13 — effectively dead]
aggression_level: 0.30  (floor — repeated losses)
recent_profit[-5]: [-1,-1,-1,-1,-1]
emotion_laws: 50 pain + 50 anger + 50 triumph rules
```
**Backtest result (Fix 5, 2026-07-28):** 1,746 races analysed. **100% in STRONG_DAMPEN (<0.80)** — zero amplify cases. Root cause: STRONG_DOCTRINES loop fired on EVERY race when strength < 0.5 (no race condition), adding "LAY_THE_STORY"+"SHADOW_TRACKING" to doctrines_fired unconditionally, trapping them in a death spiral to 0.08.

**Doctrine collapse fixed (2026-07-28, commit `de0c2ea`):** `_g_shadow_adjustment()` rewritten with principled firing conditions: LAY_THE_STORY fires only when MDS > 0.55; SHADOW_TRACKING fires only when SP ≥ 10.0. Both state files reset to 0.5 (neutral). Multiplier distribution immediately after fix: 32/35 races at 1.0x, 3/35 at 0.93x (high-MDS favs), avg 0.994x — vs 35/35 at 0.516x before.

**Fix 6 condition:** `VELO_G_SHADOW_MODE=live` requires 3+ months of post-reset sigma data showing doctrinemultiplier variation with positive win-rate signal. Not before 2026-10-28 at earliest. Backtest script: `scripts/analysis/g_shadow_backtest.py`.

### Block 3 — Council Independence
The council (`src/velo/council/agents.py`) is deterministic rule-based — 5 agents checking flatline, contamination, sigma SR, run IDs, mid-price — **with zero LLM calls**. It is genuinely independent of the learning runner. PrimeChair synthesizes to `PASS_TO_LEARNING` / `QUARANTINE_DAY` / `WATCH_ONLY`.

**Bug fixed (Fix 4, 2026-07-28):** `_finalize()` in `nightly_eod_learning_runner.py` previously wrote `"council_verdict": verdict` — copying its own PASS/FAIL into the council audit file. Now reads `data/council_runs/council_run_{self.date_str}.json` and extracts the actual `council_verdict`. Also adds `council_source` field to the audit trail. Combined with Fix 3 (gate pre-flight), the runner now cannot proceed unless the real council file exists and reads `PASS_TO_LEARNING`.

### Block 4 — Gate Enforcement
Zero of 12 gate conditions (LEARNING_ADMISSION_GATE.md) are enforced in runner startup code. The runner opens `run()` with no gate check. `learning_allowed: True` hardcoded on every event. The gate document itself acknowledges this: "Today this gate is procedural."

**Fixed (Fix 3, 2026-07-28):** Pre-flight added at top of `run()` in `nightly_eod_learning_runner.py`. Checks:
1. `data/sigma_results/sigma_results_{date}.json` exists and `sigma_status == "PASS"`
2. `data/council_runs/council_run_{date}.json` exists and `council_verdict == "PASS_TO_LEARNING"`
3. `data/mission_control/{date}_mission_control.json` exists and `learning_gate == "OPEN"`

Any failure returns `FAIL_GATE_BLOCKED` without touching sentient state.

### Block 5 — VCP-03 Burn-In
**FIXED 2026-07-28.** `build_vcp03_burn_in_log.py` was never wired into daily pipeline. Now runs as Step 20B in `run_full_raceday_eod.py`. Days 2–28 (July 2–27) are permanently lost — heartbeat file overwrites daily, no history. Count restarts from July 28 at 0/10.

### Block 6 — Calibration Threshold
`_classify_loss()` in `nightly_eod_learning_runner.py` line 105:
```python
if prob > 0.35: return "CALIBRATION_ERROR"
```
VP ≥ 0.30 is the system's definition of "high confidence". Classifying all VP > 0.35 losses as `CALIBRATION_ERROR` catches 57–85% of all losses — most normal picks, not genuinely overconfident ones. This floods G's pain rules with calibration signals that aren't meaningful.

**Fix: raise threshold to VP > 0.55.** At VP > 0.55 the model is making a genuinely high-conviction claim. Losses there are true calibration errors.

### Block 7 — Idempotency
**NOT BROKEN.** Separate audit files for shadow (`playbook_g_nightly_audit_{date}.json`) and live (`playbook_g_live_nightly_audit_{date}.json`) are intentional. Both adapters correctly block duplicate runs for the same date using date-scoped key files. No action needed.

### Fix Order (dependency-safe)
| Priority | Fix | File | Status |
|---|---|---|---|
| 1 | VCP-03 wire-in | `run_full_raceday_eod.py` Step 20B | **DONE** `1f39fcf` |
| 2 | Calibration threshold 0.35→0.55 | `nightly_eod_learning_runner.py` line 105 | **DONE** `f8fe12f` |
| 3 | Gate pre-flight (sigma + council + MC) | `nightly_eod_learning_runner.py` top of `run()` | **DONE** `38023e6` |
| 4 | Runner reads actual council verdict | `nightly_eod_learning_runner.py` `_finalize()` | **DONE** `6f6b073` |
| 5 | Backtest G shadow multipliers vs sigma | `scripts/analysis/g_shadow_backtest.py` | **DONE** `c57e555` — VERDICT: all 1,746 races in STRONG_DAMPEN, Fix 6 BLOCKED |
| 6 | Flip `VELO_G_SHADOW_MODE=live` + reset doctrine strengths | `.env`, `app/main.py`, doctrine reset | **BLOCKED** — post-reset, needs 3+ months data (earliest 2026-10-28) |
| 7 | Fix doctrine collapse + state reset | `src/intelligence/velo_prime_ensemble.py`, `data/sentient_state*.json` | **DONE** `de0c2ea` — multiplier 0.516→0.994, doctrines fire on principled conditions |

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
- **DOCS-01 — ACCEPTED 2026-07-06** (operator ruling): PR #136 merged (`868dff3`). Agent wiki + system map spine live at `docs/current/`. Numbering ruling issued in the same decision: **VFU-13 is retired and must never be reused** — the next forensic mission is **VFU-22 — False-GREEN Feature Autopsy** (formerly proposed as VFU-13 before DOCS-01 index reconciliation).
- **VFU-22 — COMPLETE 2026-07-06:** PR #137 merged (`4f789b1`). 6 of 16 GREEN-gated days (37.5%) confirmed false-green across 31 available `sigma_results_*.json` dates. Class identified: `CONFIDENCE_FLOOD_FALSE_GREEN` (VP elevated broadly across the field without matching hit/miss discrimination — mean gap 0.039 vs 0.116 on true-green days; 2/6 false-green days show VP inverted, higher on losers than winners). Structural finding, not a fixable oversight — no VP Gatekeeper criteria change made. Output: `data/reports/vfu_22_false_green_feature_autopsy.md`.
- **VFU-23 — COMPLETE 2026-07-06:** PR #138 merged (`797cdef`). Confidence Flood Retrospective Diagnostic. Builds the thermometer, not the cure — a tested, reusable post-Sigma diagnostic (`scripts/ops/build_confidence_flood_diagnostic.py`, 21 tests pass) that reproduces the VFU-22 false-green set 6/6 with zero extras. Retrospective only; no pre-race gate change. See `docs/current/CONFIDENCE_FLOOD_DIAGNOSTIC.md`.
- **VFU-24 — COMPLETE 2026-07-06:** PR #139 merged (`ad1a4aa`). Confidence Flood Root-Cause Split. Splits the six confirmed false-green days into root-cause subtypes: 4 `GAP_COLLAPSE_FALSE_GREEN` (06-09, 06-16, 06-23, 06-30), 2 `HEALTHY_GAP_FALSE_GREEN` (06-18, 06-19) — both of which also carry `THRESHOLD_FLOOD_FALSE_GREEN` as a secondary subtype, explaining why they were false-green despite a healthy discrimination gap. Proposed no cure, no VP Gatekeeper change. See `docs/current/CONFIDENCE_FLOOD_ROOT_CAUSE_SPLIT.md`.
- **VFU-25 — COMPLETE 2026-07-07:** PR #140 merged (`92446ee`). Confidence Flood Cure Design Sandbox. Designed (did not implement) 5 candidate mitigations for the two VFU-24 variants: Gap-Collapse Guard, Threshold-Flood Guard, Green-Day Risk Overlay, Same-Day Post-Sigma Reporting Enhancement, Promotion/Rejection Criteria. All rated `DESIGN_ONLY`/`NEEDS_MORE_EVIDENCE`/`SHADOW_TEST_NEXT` — none left the sandbox. No cure implemented, no VP Gatekeeper change. See `docs/current/CONFIDENCE_FLOOD_CURE_DESIGN_SANDBOX.md`.
- **VFU-26 — IN PROGRESS (opened 2026-07-07):** Confidence Flood Evidence Expansion. Expanded the sigma_results corpus 31→42 dates (11 new, from this project's own sister worktree local artifacts). Reproduced the known 6-date false-green set exactly; found 4 new false-green dates; false-green rate held/increased (37.5%→43.5%); a new `WEAK`-gap-band `UNRESOLVED_FALSE_GREEN` case appeared, not fitting either VFU-24 primary subtype; Threshold-Flood Guard's measured false-positive rate rose from an unmeasurable 0/10 to a real 30.8% (4/13) with a larger true-green cohort. Verdict: `EVIDENCE_EXPANDED_MIXED_RESULT` — disease confirmed/strengthened, cure candidates not promoted (still `DESIGN_ONLY`/`NEEDS_MORE_EVIDENCE`/reporting-only `SHADOW_TEST_NEXT`). No cure implemented, no VP Gatekeeper change. Task contract `ops/task_contracts/VFU-26.json`, branch `vfu-26-confidence-flood-evidence-expansion`. See `docs/current/CONFIDENCE_FLOOD_EVIDENCE_EXPANSION.md`.

## VÉLØ Coherence Protocol (VCP) State (updated 2026-07-28)
- **VCP-00 — Truth Lock:** IN PROGRESS (2026-06-29). Stale root docs archived. CLAUDE.md rewritten as pointer-only. docs/current/ thinned to operational spine. ONE_TRUTH HEAD updated.
- **VCP-01 — Living State Packet:** COMPLETE (`ff86674`). `data/current/velo_living_state.json` (gitignored runtime state). Operator signed off 2026-06-29. Builder: `scripts/ops/build_velo_living_state.py`.
- **VCP-02 — Heartbeat V1:** COMPLETE (`5f83fec`). Reads living state only. 25 tests pass. Operator signed off 2026-06-29. Builder: `scripts/ops/build_velo_heartbeat.py`.
- **VCP-03 — Ten-Day Coherence Burn-In:** IN PROGRESS. 2/10 passing days (June 30 + July 1). Log stuck because `build_vcp03_burn_in_log.py` was never wired into the daily pipeline — **FIXED 2026-07-28**: now runs as Step 20B in `run_full_raceday_eod.py`. Days 3–28 (July 2–27) are permanently lost (heartbeat overwrites daily, no history kept). Count restarts from July 28. Log: `data/reports/vcp_03_burn_in_log.md`. Protocol: `docs/current/VCP_03_COHERENCE_BURN_IN_PROTOCOL.md`.
- **VCP-04 — Shadow Judgment:** NOT STARTED. Requires 10 passing burn-in days + operator sign-off.
- **Learning doctrine:** VÉLØ learns from every event. Only clean, verified events are allowed to train or promote predictive rules. Dirty events become failure-memory, not model-food. Three lanes: MEMORY_CAPTURE_OPEN (always) · FAILURE_LEARNING_OPEN (always) · PROMOTION_LEARNING_GATED (clean evidence only).

## Phase A–D Audit Corpus (added 2026-06-28)
- **Sigma local corpus:** `scripts/audit/build_sigma_local_corpus.py` → `data/training/sigma_local_corpus_latest.parquet` (1,050 rows, 36 dates, SR=26.7%). Run after any new sigma dates to extend.
- **Top gates (shadow/advisory only):** VP≥0.40+HIGH_CONF SR=54.2% (n=83) · VP+IMP≥0.4 SR=55.6% (n=36) · VP+MDS≥0.3 SR=52.8% (n=53) · RS≥1.5 SR=44.7% (n=38, now n=44/SR=38.6% as the corpus has grown — see verification note below)
- **RS≥1.5 gate — verified clean of the RPDC look-ahead leak (2026-07-27):** A real RPDC training-data leak was found and fixed the same day (`_fetch_horse_history`/`_trainer_stats` in `build_rpdc_daily.py` had no `run_date` cutoff, so backfilled/regenerated rows could leak a horse's own result into its own "history" — confirmed via `course_return_flag`: 87.9% win rate in contaminated data vs 16.7% in the genuinely clean same-day subset, base rate 13.0%). Traced whether this figure was affected: `build_sigma_local_corpus.py` reads `rpdc_release_score` only from immutable local verdict JSON snapshots (no Supabase, no live re-query — confirmed by reading its source). Pulled the exact dates behind every RS≥1.5-qualifying race (13 dates, 2026-06-12 to 2026-06-28) and cross-checked against all 40 historical `velo-prime-scoring` runs that scored later than their `source_date` (real rescore/backfill risk, from 266 total pipeline runs). **Zero overlap** — every RS≥1.5 qualifying race was scored same-day. This figure is genuinely clean, not an assumption.
- **Going code bug (A-3):** FIXED (`09f3252` + `8753b4f`). Both `paper_scorer.py` and `new_build_two_lane_score.py` now use -1 to 2 scale matching raceform_v17 training (Heavy=-1, Good=1, Firm=2). Median fallback corrected to 1.0. Regression tests in `tests/test_new_build_paper_scorer.py` (6 tests, all pass). Operator approved 2026-06-29.
- **RPDC missing tags:** STABLE_WARM / MARK_READY / MARK_NEAR / COURSE_RETURN absent from all May–Jun 2026 data. Investigate Supabase `runner_release_candidates`.
- **New scrapers/parsers:** `scripts/ops/scrape_bha_going_stick.py` (D-1, shell ready) · `scripts/ops/parse_runner_notes.py` (D-3, verdict intel only)

## Railway — What It Actually Does (audited 2026-07-28)

Railway (`railway.toml`) runs ONE thing: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` — the FastAPI dashboard server. That's it. Everything else is either dead or never wired.

| Railway service | Status | Verdict |
|---|---|---|
| Dashboard (`app.main:app`) | RUNNING | Only working Railway use. Reads Supabase. Accessible remotely. |
| Scoring cron (`run_prime_today.py @ 09:00 UTC Mon-Sat`) | FAIL_OR_UNPROVEN | Cannot work — needs logged-in local RP browser session (Playwright + Firefox profile). Railway has no access to this. |
| EOD/sigma chain | NOT DEPLOYED | Also cannot work remotely — depends on local result capture files. |

**Cost verdict:** You are paying Railway to host a dashboard that reads Supabase. If remote access to the dashboard matters, keep it. If you only use it locally, shut down Railway and run `app.main:app` locally — saves the subscription entirely. Do NOT attempt to wire the scoring cron on Railway: it structurally requires a local browser session that cannot exist in a cloud container.

## What is BLOCKED / KNOWN ISSUES (updated 2026-07-28)
- **Telegram scoring alerts:** DISABLED (`--no-notify`).
- **Railway cron:** FAIL_OR_UNPROVEN — every scoring run is manual. See Railway section above.
- **Local test suite:** pytest 6.2.5 incompatible with pytest-asyncio 1.3.0; 3 test modules have import drift. **30/30 governance tests pass** (governance-v1-hardened tag @ `2cc135a`).
- **Learning gate:** Check daily — blocked on DEGRADED/UNKNOWN source or Council verdict not `PASS_TO_LEARNING`.
- **Calibration threshold:** `nightly_eod_learning_runner.py` classifies any VP > 0.35 loss as `CALIBRATION_ERROR` — too aggressive (catches ~57-85% of all losses). Fix: raise to VP > 0.55. Queued.
- **Gate enforcement:** 12 learning admission gate conditions (LEARNING_ADMISSION_GATE.md) are procedural only — none enforced in runner startup code. Runner auto-sets `learning_allowed=True`. Queued.
- **Council verdict not read by runner:** Runner writes `council_verdict = runner_verdict` in its own audit (line 389 `_finalize()`), never reads the actual Step 16b council output. Queued.
- **`_G_SHADOW_MODE`:** Playbook G multiplier computed every scoring run but never applied to VP. Env var `VELO_G_SHADOW_MODE` defaults to `shadow`. G has evolved over 3,466 races — most doctrines near 0.0 strength, aggression at floor 0.3. Before flipping to `live`: backtest shadow multipliers against sigma to verify lift. Queued after gate enforcement fix.
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

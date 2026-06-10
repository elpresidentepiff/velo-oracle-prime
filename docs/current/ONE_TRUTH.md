# ONE TRUTH — VÉLØ ORACLE PRIME

> **IF THIS FILE CONFLICTS WITH ANY OTHER DOC, THIS FILE WINS UNTIL OPERATOR SAYS OTHERWISE.**

**Effective:** 2026-06-10 (operator mandate `VELO_ONE_TRUTH_TIME`) · **Branch:** `stabilization/prime-hardening-v1` · **Verified against code, not docs.**

**This file supersedes:** `THE_NEW_TRUTH.md`, `CURRENT_RUNTIME_TRUTH.md`, root `CLAUDE.md` state claims, all numbered docs in `docs/` flat directory.
**This file defers to:** root `THE_ONE_TRUTH.md` for step-by-step command detail (Steps 1–20), `docs/current/RACE_DAY_RUNBOOK.md` for the lifecycle.

## Law (operator-decided 2026-06-10)
1. VÉLØ is a behavioural prediction engine for racing. Live weights are **frozen**.
2. **Racing API is not live.** It may exist only as archived legacy, deleted dependency, sidecar reference, documented history, or non-live experimental adapter. Any live-path import of Racing API is a BLOCKER. No document may claim Racing API is connected.
3. The RP (Racing Post HTML) path is the live source path.
4. **RPDC is horse-career memory and deployment context. PDF intelligence is a separate feature and must never overwrite RPDC fields.** (Hijack `fda78d4` fixed 2026-06-10; PDF plot data lives in `full_analysis.plot_intel`.)
5. Mission Control derives source truth from the observability packet — never by default, never by inference. Missing/malformed packet = `UNKNOWN` = learning blocked.
6. Supabase is connected and is the system of record — verify it with `prove_supabase_persistence.py`, never assume it.
7. Learning is blocked on degraded days. No exceptions without operator approval.
8. **Race Day 11 (2026-06-11) is the production rehearsal** — see `RACE_DAY_11_EXECUTION_PACKET.md` and `LEARNING_ADMISSION_GATE.md`.

---

## What is VÉLØ?
An auditable UK/IRE horse-racing prediction system. It captures Racing Post HTML, scores every race with a governed ML ensemble, persists verdicts to Supabase, reconciles against results nightly (Sigma), and accumulates evidence under hard learning gates. **No live staking. Not a tips service.**

## What is LIVE
| Thing | Truth |
|---|---|
| Scoring entrypoint | `scripts/ops/run_prime_today.py --date YYYY-MM-DD --source rp --no-notify` (manual; Railway cron is FAIL_OR_UNPROVEN) |
| Live formula | Profile `SQPE_IMPROVEMENT_MDS_V1`: `VP = (0.45·sqpe_v17 + 0.12·improvement_score + 0.10·market_deception_score) / 0.67` (`src/intelligence/velo_prime_ensemble.py:175-235`) |
| Live model files | `models/sqpe_v17/sqpe_v17.pkl`, `models/specialist/improvement_model/`, `models/specialist/market_deception_model/` |
| Stored but NOT weighted | `place_prob` (badge), `longshot_score` (frozen), `release_window_score`, `comment_intel_score` (stored-only) |
| Data source | Racing Post HTML via logged-in Playwright capture (`racing_post_account_collector.py`). UK/IRE only. |
| System of record | Supabase `velo_verdicts`; local backup `data/velo_prime_verdicts_YYYY_MM_DD.json` |
| Rollback | `VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE` |

## What is SHADOW (no scoring effect)
New Build / Passport two-lane scorer · Playbook G sentient loopback (`sentient_state_shadow.json`) · Execution bridge paper ledger (SIM-only, hard LIVE guard) · Router lanes V1/V2/V6 · Shadow Model C · Race Shape v1 · BHA OR-diff and surface-trajectory badges (evidence only).

## What is DEPRECATED
Racing API as a data source (decommissioned 2026-05-14; client files deleted) · Sporting Life scraper (`scrape_results_sl.py`) · `velo_race_day_button.py` (do not use as authority) · `scrape_results_atr.py` (does not exist — any doc naming it is stale) · root `Makefile` (Benter v10.1 era) · root `cron.txt` (`/home/ubuntu` paths) · `COMMAND.json`.

## What is EXPERIMENTAL
International prerace arenas (`scripts/audit_international_*`) · HK/FR feature builders · Intent Layer V1 (patched, rerun required) · sqpe_v18 (not promoted).

## What is BLOCKED right now (2026-06-10)
- **Learning:** BLOCKED — June 10 source is `RP_MERGED_DEGRADED`; June 9 council verdict `WATCH_ONLY` + pipeline truth `MANUAL_RECOVERY_ONLY`.
- **Telegram scoring alerts:** DISABLED (`--no-notify`).
- **Railway cron:** FAIL_OR_UNPROVEN — every run is manual.
- **Local test suite:** cannot run — pytest 6.2.5 incompatible with pytest-asyncio 1.3.0; 3 test modules have import drift.

## What must happen BEFORE scoring
1. `python scripts/ops/velo_session_start_check.py` passes.
2. RP index + race pages captured; injection parsed; `validate_rp_injection.py` exits 0.
3. `build_racecard_merged_from_injection.py` and `build_rpdc_daily.py` run from the SAME injection path (`FINAL_CAPTURE_LABEL` chosen once at Step 4).

## What must happen AFTER results (~21:00 BST)
Steps 10–20 in order (see RACE_DAY_RUNBOOK.md). `DAY COMPLETE` only when all pass plus final Council + Mission Control refresh.

## What makes a day CLEAN vs DEGRADED
- **CLEAN:** observability `source_truth: RP_MERGED_CLEAN`, `flatline_count: 0`, `identity_failure_count: 0`, 100% races persisted.
- **DEGRADED:** >50% of runners missing `pdf_intel.postdata_score`/`or_compression_score` (`src/velo/source_truth_enforcer.py:98-117`). Scoring proceeds; learning is blocked.
- **FIXED 2026-06-10:** Mission Control now derives `source_truth` from the latest observability packet (`UNKNOWN` when missing/malformed, never CLEAN by default) and blocks learning on DEGRADED/UNKNOWN. Tests: `tests/test_mission_control_source_truth.py`.

## What blocks learning (any one of)
Degraded/unknown source · Council verdict not `PASS_TO_LEARNING` · pipeline truth `MANUAL_RECOVERY_ONLY` · contaminated run IDs (`MC_CONFIG.CONTAMINATED_RUN_IDS`) · flatline/identity failures · Playbook G `live_sentient_state_touched != false`.

## Next safe command
```
python scripts/ops/velo_session_start_check.py
```

## NEVER touch without operator approval
Live weights/profile in `velo_prime_ensemble.py` · `models/sqpe_v17/` and `models/specialist/` · `app/agents/betfair_execution_agent.py` + `betfair_trading_agents.py` (never import into live path) · LIVE guard in `src/velo/execution_bridge.py` · `data/sentient_state.json` · Sigma Telegram format (LOCKED) · old verdicts in Supabase · `MC_CONFIG.CONTAMINATED_RUN_IDS`.

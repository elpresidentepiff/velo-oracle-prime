# CURRENT_STATE.md — Fast Startup for Any New Agent

Read this first. Then read `docs/current/ONE_TRUTH.md` in full before touching
anything. This file is a pointer/orientation layer — `ONE_TRUTH.md` remains the
single source of truth for state details.

## What is VÉLØ right now?

An auditable UK/IRE horse-racing prediction system, live-scoring via
`run_prime_today.py` on the RP (Racing Post HTML) data path (Racing API is
permanently decommissioned). Live formula is profile `SQPE_IMPROVEMENT_MDS_V1`.
No live staking anywhere in the system — execution bridge is SIM/PAPER only.
Full detail: `docs/current/ONE_TRUTH.md` §"What is VÉLØ?" / §"What is LIVE".

As of 2026-07-06 (`main` @ `4419d2d`): Champion Intent Shadow is now a permanent
per-race-card shadow lane on the dashboard; a read-only "Model Suggestions" API
surfaces all 10 model lanes side-by-side; July 06 raceday was learned via
runtime-artifact Sigma (`SIGMA_RUNTIME_LEARNING_FROM_EXISTING_RACEDAY_ARTIFACTS`,
not an official live-verdict Sigma run, since no live scorer ran that day) and
persisted to `canonical_model_scorecards` / `canonical_learning_events` with
`promotion_eligible=false` throughout.

## What changed most recently?

- PR #131: MODEL-TRUTH-04, dashboard canonical truth consumer.
- PR #132: AW venues included in UK/IRE universe.
- PR #133: July 06 passport recovery + Champion Intent Shadow wiring (shadow only).
- PR #134: `/api/model-suggestions` + `/api/model-suggestions-race` (all 10 lanes).
- PR #135: Champion Intent Shadow dashboard lane, Model Suggestions summary panel,
  report-only legacy scorer, July 06 Sigma runtime-learning artifacts, canonical
  runtime persistence script + report.
- This DOCS-01 mission: the documentation spine you are reading now.

Check `git log --oneline -15` on `main` for anything newer than this snapshot.

## What is safe to work on?

- Documentation under `docs/current/`.
- New shadow/report-only lanes that write to local `data/` artifacts and dashboard
  read-only endpoints, provided they carry `dashboard_visible`/`stake_authorised`/
  `promotion_eligible` flags per `docs/current/MODEL_RESULT_REPORTING_LAW.md`.
- Tests under `tests/`.
- Task contracts under `ops/task_contracts/`.
- Anything explicitly scoped inside a task contract's `allowed_paths`.

## What is not safe to touch?

- `src/intelligence/velo_prime_ensemble.py` live weights/profile.
- `models/sqpe_v17/`, `models/specialist/` model files.
- `app/agents/betfair_execution_agent.py`, `betfair_trading_agents.py` — never
  import into the live path.
- The LIVE guard in `src/velo/execution_bridge.py`.
- `data/sentient_state.json`.
- Sigma Telegram format (locked — always use `run_results_sigma.py` unmodified).
- Old verdicts already persisted in Supabase.
- `MC_CONFIG.CONTAMINATED_RUN_IDS`.

Full list: `docs/current/ONE_TRUTH.md` §"NEVER touch without operator approval" and
`docs/current/FORBIDDEN_ACTIONS.md`.

## What is VFU-22 / VFU-23 / VFU-24 / VFU-25?

The numbering conflict flagged by DOCS-01 is resolved. Operator ruling
2026-07-06: `ONE_TRUTH.md` already records VFU-13 to VFU-19 as COMPLETE
(contamination catches, Sigma master ledger, pattern tribunal — see
`docs/current/VFU_INDEX.md`). VFU-13 is retired and must never be reused.
**VFU-22 — False-GREEN Feature Autopsy is COMPLETE** (merged PR #137, `4f789b1`):
6 of 16 GREEN days (37.5%) confirmed false-green; `CONFIDENCE_FLOOD_FALSE_GREEN`
class identified. **VFU-23 — Confidence Flood Retrospective Diagnostic is
COMPLETE** (merged PR #138, `797cdef`): tested post-Sigma diagnostic that
reproduces the VFU-22 false-green set 6/6. **VFU-24 — Confidence Flood
Root-Cause Split is COMPLETE** (merged PR #139, `ad1a4aa`): splits the six
false-green days into subtypes (4 gap-collapse, 2 healthy-gap-with-threshold-
flood). **VFU-25 — Confidence Flood Cure Design Sandbox** is IN PROGRESS as of
2026-07-07 — designs (does not implement) 5 candidate mitigations, all rated
`DESIGN_ONLY`/`NEEDS_MORE_EVIDENCE`/`SHADOW_TEST_NEXT`. See
`docs/current/NEXT_ACTIONS.md`, `ops/task_contracts/VFU-25.json`, and
`docs/current/CONFIDENCE_FLOOD_CURE_DESIGN_SANDBOX.md`.

Also outstanding: VCP-00 Truth Lock was IN PROGRESS as of 2026-06-29 per
`ONE_TRUTH.md`; VCP-03 Ten-Day Coherence Burn-In was at 1/10 days. Check current
burn-in day count in `data/reports/vcp_03_burn_in_log.md` before assuming VCP-04
readiness.

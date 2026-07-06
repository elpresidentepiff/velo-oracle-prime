# Model Truth 04 — Dashboard Canonical Truth Consumer Operator Brief
Generated: 2026-07-06 | Mission: MODEL-TRUTH-04-DASHBOARD-CANONICAL-CONSUMER

## 1. What did the dashboard use before this mission?
Existing endpoints (`/api/governed-card`, `/api/dashboard-truth`, `/api/old-velo-verdicts`, `/api/doctrine-scorecard`) read local dirty-repo runtime artifacts directly: `two_lane_readiness_{date}.json` (New Build), `velo_prime_verdicts_{date}.json` (Main VELO / Old VELO), `doctrine_scorecard_latest.json`, `sidecar_stack_latest.json`. None of these were the canonical, machine-checked, cross-model-comparable source built in MODEL-TRUTH-01/02/03. This is exactly the gap that produced the PR #127 incident (the `passport_strength_score` proxy being mistaken for a real model output).

## 2. What does the dashboard use now (in addition, not instead)?
Three new read-only endpoints were added, all sourced ONLY from Supabase:
- `GET /api/canonical-scorecard?date=YYYY-MM-DD` → all rows from `public.canonical_model_scorecards` for that date.
- `GET /api/canonical-learning-events?date=YYYY-MM-DD` → all rows from `public.canonical_learning_events` for that date.
- `GET /api/canonical-race-truth?date=YYYY-MM-DD&race_id=...` → both tables filtered to one race, joined by `race_id`.

Each response includes `"no_supabase_write": true` and `source_table`/`source_tables` fields, per `MODEL_RESULT_REPORTING_LAW`. No existing endpoint was removed or modified — this mission is additive only.

## 3. What remains local/runtime-only (not yet converted)?
`/api/governed-card`, `/api/dashboard-truth`, `/api/old-velo-verdicts`, `/api/doctrine-scorecard`, and the main `/dashboard` HTML/static panel still read local JSON artifacts, not the canonical tables. Per MODEL-TRUTH-02's dashboard consumer audit, converting those panels is future work, deliberately out of scope here — this mission only proves the canonical read path works end-to-end and is safe to build on.

## 4. How does Little Lady Rock (race 922118, 2026-07-05) appear now?
Verified live via `GET /api/canonical-race-truth?date=2026-07-05&race_id=922118`:
- `NEW_BUILD_LANE_A_MODEL`: rank 1, SP 41.0, `policy_decision=NO_EDGE`, `stake_authorised=false`.
- `NEW_BUILD_LANE_B_MODEL`: rank 1, SP 41.0, `policy_decision=NO_EDGE`, `stake_authorised=false`.
- `NEW_BUILD_LANE_C_MODEL`: rank 2, SP 41.0, policy N/A (Lane C not policy-anchored).
- `PASSPORT_STRENGTH_SCORE_PROXY`: rank 2, SP 41.0, explicitly labeled a proxy, not a model decision.
- Learning events for the same horse: Lane A/B → `event_type=VALUE_DISCOVERY_POLICY_BLOCKED`, `promotion_eligible=false`; proxy → `event_type=PROXY_CONTEXT_ONLY`.
- `MAIN_VELO_PRIME` row for the same race: horse "Way Maker", `win=false` — confirms Main VELO backed the favourite and lost, matching the MODEL-TRUTH-01/03 findings.
No row anywhere calls Little Lady Rock a "near-miss." This is enforced by a regression test (`test_little_lady_rock_cannot_appear_as_near_miss`), not just manual review.

## 5. Which panels/paths are safe to trust right now?
The three new `/api/canonical-*` endpoints are safe: read-only, Supabase-sourced, tested against live data (10/10 new tests + 24 existing MODEL-TRUTH-01/02/03 tests all pass = 34/34 total). They are additive and do not change anything the live dashboard currently renders.

## 6. Which panels still need later conversion?
The visible dashboard UI (`/dashboard` static HTML) and its existing `/api/governed-card`/`/api/dashboard-truth` data sources — these still show local-artifact-derived New Build/Old VELO/No-RPR panels. Wiring the actual dashboard UI to call the new canonical endpoints (and visually separating rank / policy / stake / result per `MODEL_RESULT_REPORTING_LAW`) is the next mission, not done here.

## Verification performed
- `fetch_canonical_scorecard("2026-07-05")` and `fetch_canonical_learning_events("2026-07-05")` called directly against live Supabase: 374/374 rows each, confirmed.
- Dashboard server started on a local test port, all three endpoints hit over real HTTP, responses manually inspected.
- `tests/test_dashboard_canonical_truth_api.py`: 10/10 passed against live Supabase data (no mocks).
- Full canonical-truth suite (`test_canonical_model_scorecard_july05.py`, `test_persist_canonical_model_scorecard.py`, `test_canonical_learning_events_july05.py`, `test_dashboard_canonical_truth_api.py`): 34/34 passed.

## Classifications
MODEL_TRUTH_04_OPENED · DASHBOARD_CANONICAL_READ_ONLY_ENDPOINTS_ADDED · LITTLE_LADY_ROCK_REGRESSION_LOCKED · NO_SUPABASE_WRITE · NO_SCORING · NO_SIGMA_RERUN · NO_RESULT_INGEST · NO_TELEGRAM · NO_MODEL_TRAINING · NO_PROMOTION · NO_STAKING · EXISTING_PANELS_UNCHANGED · REPORT_ONLY

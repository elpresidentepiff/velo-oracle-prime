# Model Truth Reset 01 — Operator Brief
Generated: 2026-07-05 | Mission: MODEL-TRUTH-RESET-01-CANONICAL-SCORECARD-CONTRACT

## 1. Why PR #127 is not canonical
Its correction history stacked three amendments on top of each other and left contradictory language in the PR body/commits (a retracted "ranked 2nd / near-miss" claim survived alongside a later commit proving rank 1). Frozen as draft, held, not merged — see the PR comment for the full reason.

## 2. What truth layers were confused
Model rank, policy decision, dashboard display, staking outcome, Supabase-persisted verdict, and local artifact were all repeatedly collapsed into the single word "result."

## 3. What July 05 Little Lady Rock proves
`data/reports/canonical_model_scorecard_2026_07_05.csv`, race 922118: New Build Lane A model ranked Little Lady Rock (SP 41.0, actual winner) **rank 1** (score 0.217898). Lane B also ranked it rank 1 (0.167947). Lane C ranked it rank 2 (Way Maker rank 1 there). Main VELO, Old VELO WIN, both picked Way Maker — lost, 3rd. `policy_v1` classified the Lane A/B pick `NO_EDGE`.

## 4. What it does not prove
Not a staking or paper-execution win (`stake_authorised=False` — policy never cleared it). Not multi-day validated. Not evidence Lane C should be trusted (it missed the winner). Not evidence the policy thresholds are wrong — a single narrow miss (0.168 vs 0.17 gate) is a data point, not proof of miscalibration.

## 5. How learning should classify it
`MODEL_HIT_POLICY_BLOCKED` (the label used in the canonical CSV) — New Build's raw model signal found real value; its own governance layer independently declined to act on it. Both facts recorded, neither erasing the other.

## 6. How future reports are protected
`docs/current/MODEL_RESULT_REPORTING_LAW.md` (9 numbered rules) + `scripts/ops/build_canonical_model_scorecard.py` (machine-generates the 23-column row schema, no hand-authored claims) + `tests/test_canonical_model_scorecard_july05.py` (9 regression tests, all passing against real data, hard-blocking any future "near-miss"/rank-2 mislabeling of this specific case).

## 7. What remains gated
Everything: `promotion_gate: BLOCKED`, no live staking anywhere in the system, no model training, no Telegram, no Sigma re-run in this mission.

## 8. What must be persisted to Supabase later (not done here)
New Build Lane A/B/C ranks and `policy_v1` decisions currently exist only in local files (`two_lane_readiness_{date}.json`). If New Build's scorecard is to become as auditable as Main VELO's, it needs its own persisted Supabase table — flagged as a real gap, not fixed in this report-only mission.

## Data quality note
Way Maker's SP differs between rows (1.83 in canonical-builder rows, sourced from the final results file; 1.1 in the Old VELO row, sourced from the pre-race snapshot's forecast odds) — both are real, correctly-labeled values from their respective source files, not an error; the canonical builder's SP is the more accurate final price.

## Classifications
PR_127_HELD_NOT_CANONICAL · MODEL_RESULT_REPORTING_LAW_ADDED · CANONICAL_MODEL_SCORECARD_BUILDER_ADDED · LITTLE_LADY_ROCK_REGRESSION_TEST_ADDED · NEW_BUILD_LANE_A_HIT_POLICY_NO_EDGE_PROVEN · ODDS_REQUIRED · TIE_POLICY_REQUIRED · NO_SUPABASE_WRITES · NO_SCORING_RUN · NO_SIGMA_RUN · NO_TELEGRAM_SEND · NO_MODEL_TRAINING · NO_PROMOTION

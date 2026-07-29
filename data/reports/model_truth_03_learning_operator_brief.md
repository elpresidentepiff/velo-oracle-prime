# Model Truth 03 — Learning Operator Brief
Generated: 2026-07-05 | Mission: MODEL-TRUTH-03-CANONICAL-LEARNING-EVENTS

## 1. What did July 05 teach?
That model rank, policy decision, and staking outcome are three separate facts, and the day's headline finding only exists because they were finally kept separate: New Build's Lane A/B model found the actual 41.0 winner (Little Lady Rock, race 922118) as its own top-ranked pick.

## 2. What did New Build learn?
Its raw model signal (Lane A `predict_proba`, Lane B `predict_proba`) can find real long-priced value in a compressed market where every other model converges on the same short-priced favourite. This is now a machine-checkable event (`VALUE_DISCOVERY_POLICY_BLOCKED`) in `canonical_learning_events`, not a one-off claim.

## 3. What did Main VELO miss?
Way Maker at SP 1.1 — the same short-priced favourite Old VELO's WIN role and Radical Shadow also converged on. All three lost together.

## 4. What did policy_v1 block?
The Lane A/B rank-1 pick on Little Lady Rock — its Lane B probability (0.168) missed the `FRAME_TRUST_VP_MIN` threshold (0.17) by roughly 0.002, and missed `WIN_TRUST_VP_MIN` (0.22) more clearly. The policy layer classified it `NO_EDGE` and did not clear it for any authorised action.

## 5. Why Little Lady Rock is model evidence but not staking profit
`stake_authorised=False` for every row on this pick — nothing was ever staked, paper or live, because the policy layer never cleared it. The win is a real, persisted, queryable fact about the model's raw ranking ability; it is not a realized P&L event of any kind.

## 6. Why promotion remains blocked
Every 2026-07-05 event in `canonical_learning_events` has `promotion_eligible=false` by construction (enforced in the builder, tested in the regression suite). Little Lady Rock's specific block reason: `POLICY_NO_EDGE_AND_SINGLE_DAY_EVIDENCE` — a single day's data point, however striking, is not multi-day validation, and the policy layer's own conservatism already withheld action.

## 7. What must be validated over more days
Whether New Build's Lane A/B model consistently finds value the policy layer's thresholds are too conservative to act on — this requires the same canonical-scorecard-then-learning-events pipeline run daily, accumulating `VALUE_DISCOVERY_POLICY_BLOCKED` events over time, before any threshold change or promotion discussion is warranted.

## 8. What dashboard/Sigma/learning should consume next
Per the MODEL-TRUTH-02 consumer audits: the dashboard's New Build and No-RPR panels should eventually query `canonical_model_scorecards` directly (not `two_lane_readiness_{date}.json`/`passport_strength_score`); nightly learning should add a pass reading `canonical_learning_events` to track `VALUE_DISCOVERY_POLICY_BLOCKED` accumulation over time, separate from Main VELO's own Sigma reconciliation, which remains untouched as result truth.

## Required wording (verbatim, as instructed)
New Build Lane A/B found Little Lady Rock at 41.0. policy_v1 blocked action with NO_EDGE. Main VELO selected Way Maker at 1.1 and lost. This is shadow learning only. No promotion.

## Classifications
MODEL_TRUTH_03_OPENED · LEARNING_FROM_CANONICAL_SCORECARDS · JULY05_MODEL_HIT_POLICY_BLOCKED_CAPTURED · LITTLE_LADY_ROCK_LEARNING_EVENT_LOCKED · PROMOTION_GATED · DRY_RUN_ONLY · NO_SUPABASE_WRITE_EXECUTED · NO_MODEL_TRAINING · NO_MODEL_PROMOTION · NO_SIGMA_RERUN · NO_TELEGRAM · REPORT_ONLY

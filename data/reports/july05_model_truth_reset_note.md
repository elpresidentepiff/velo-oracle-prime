# July 5 2026 — Model Truth Reset
Generated: 2026-07-05 | Mission: PR127-HARD-RESET-MODEL-TRUTH-AUDIT

## Part A — prior reports declared invalid where they collapsed layers

Earlier versions of the July 05 model-by-model report (and its first two amendments) repeatedly
collapsed six genuinely distinct things into one word, "result":

1. **Model rank** — what a calibrated model (`.pkl`, `predict_proba`) actually output.
2. **Policy decision** — whether `policy_v1.py` classified that pick as executable-confidence.
3. **Dashboard display** — which field the operator's browser actually renders.
4. **Staking/governance outcome** — whether any stake was authorized (never, under current law).
5. **Supabase persisted verdict** — what `velo_verdicts` actually stores.
6. **Local dashboard artifact** — what a local JSON file contains, which may or may not be what the
   dashboard reads.

A horse can simultaneously be rank #1 by model, `NO_EDGE` by policy, not staked, the actual race
winner, absent from any Supabase New Build table, and visible on the dashboard — all six statements
true at once, none of them contradicting another. Treating any one of these as "the" New Build
result is the root cause of every correction in this thread. **PR #127 remains HELD** until every
claim in it names which of the six layers it is describing.

## Part B — the Little Lady Rock forensic row

See `data/reports/july05_little_lady_rock_rank_policy_forensic.csv` for the full 14-row table
(every model/lane/policy/proxy/result row, with source path, field, sort direction, rank, score,
SP, and policy decision named explicitly for each). Summary:

- **New Build Lane A model** (`two_lane_readiness_2026_07_05.json`, `lane_a_top3[].prob`, descending):
  rank 1 = **Little Lady Rock**, prob 0.217898. **This is the real, calibrated model's own ranking.**
- **New Build Lane B model** (same file, `lane_b_top3[].prob`): also rank 1 = Little Lady Rock, prob
  0.167947.
- **New Build policy_v1** (`new_build_velo/policy_v1.py::apply_policy_v1()`, anchored to Lane B's
  prob): classified **`NO_EDGE`** — Little Lady Rock's Lane B probability (0.167947) falls just
  short of the `FRAME_TRUST_VP_MIN` threshold (0.17) and well short of `WIN_TRUST_VP_MIN` (0.22), so
  the policy layer's own math did not authorize treating this as a high-conviction pick, despite its
  raw rank being first.
- **Dashboard display**: the exact row a browser sees (`new_build_dashboard_server.py`,
  `_build_governed_card_from_two_lane_readiness()`) reads `lane_a_top3` directly — Little Lady Rock,
  rank 1, is what is shown.
- **`passport_strength_score`** (the field mistakenly used in the first amendment): a feature INPUT
  to the Lane A/B/C models, not their output. Under this field alone, Little Lady Rock ranks 2nd
  (2.90 vs Way Maker's 2.95) — this row is kept in the forensic CSV explicitly labeled as a
  **superseded proxy**, not a valid "New Build result."
- **Main VELO / Old VELO WIN**: both picked Way Maker (prob 0.5313, SP 1.1) — lost, finished 3rd.
- **Old VELO LONGSHOT**: picked Brosna Town (SP 10.0) — placed 2nd.
- **No-RPR shadow**: race 922118 has **no tie** in `sqpe_no_rpr_shadow_prob` (unlike race 922122) —
  this is a clean, reliable read: Brosna Town, prob 0.1528 — placed 2nd, not won.
- **Actual result**: Little Lady Rock, horse_id 7618350, SP 41.0, finished 1st.

## Part C — corrected language

- `NEW_BUILD_LANE_A_MODEL_HIT_41_TO_1` — confirmed. The Lane A model's own probability ranking put
  the actual winner first.
- `NEW_BUILD_POLICY_NO_EDGE_BLOCKED_STAKE` — confirmed. The decision-policy layer did not clear this
  pick for any authorized action, regardless of its rank.
- All prior "ranked 2nd" / "near-miss" language is retracted **except** where it explicitly refers to
  the superseded `passport_strength_score` proxy field, which is not New Build's model output and is
  now labeled as such everywhere it appears.

## Part D — learning impact (corrected)

1. New Build's Lane A model detected the 41.0 winner as its own top-ranked pick.
2. The decision policy (`policy_v1`, anchored to Lane B) suppressed it as `NO_EDGE` — a conservative
   classification, not an error; the pick did not clear the policy's own confidence thresholds.
3. Main VELO Prime, Old VELO WIN, and Radical Shadow all missed it, converging on the same beaten
   short-priced favourite (Way Maker, SP 1.1) instead.
4. **This is not a realized profit event** — the policy blocked any stake, so no paper or live P&L
   attaches to this pick. It is model-level evidence, not a governed outcome.
5. It is strong shadow evidence for New Build's Lane A value-discovery capability in a compressed
   market where every other model converged on the same favourite.
6. It is simultaneously evidence that `policy_v1`'s thresholds (`FRAME_TRUST_VP_MIN=0.17`,
   `WIN_TRUST_VP_MIN=0.22`) may be too conservative for genuine longshot/value cases — Little Lady
   Rock's Lane B probability (0.168) missed the frame-trust bar by roughly 0.002, a very narrow miss
   worth further study, not a threshold change made here.
7. No promotion is authorized by this finding. `promotion_gate: BLOCKED` remains unchanged.
8. This is a single race on a single day — it requires multi-day validation before being treated as
   a repeatable signal, not a one-off anecdote.
9. New Build needs a permanent, dated scorecard script that reconciles `lane_a_top3` (and separately
   reports the policy decision) against results every day, rather than being rediscovered under
   pressure each time a discrepancy is raised.
10. Every future model-comparison report must separate model rank, policy decision, dashboard
    display, and staking outcome as four distinct columns — never collapsed into one "result" word.

## Part E — permanent rule added

See `docs/current/VELO_MODEL_SOURCE_MAP.md`, new section `MODEL_RESULT_REPORTING_LAW`.

## Classifications
PR_127_HARD_HOLD · PREVIOUS_MODEL_REPORTS_NOT_TRUSTED · LITTLE_LADY_ROCK_MODEL_RANK_PROVEN · NEW_BUILD_LANE_A_MODEL_HIT_41_TO_1 · NEW_BUILD_POLICY_DECISION_PROVEN · MODEL_RANK_POLICY_STAKING_SEPARATED · ODDS_INCLUDED · SOURCE_PATHS_INCLUDED · NO_SUPABASE_WRITES · NO_SCORING_RUN · NO_SIGMA_RUN · NO_TELEGRAM_SEND · NO_MODEL_TRAINING · NO_PROMOTION

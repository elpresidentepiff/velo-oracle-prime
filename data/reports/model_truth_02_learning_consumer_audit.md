# MODEL-TRUTH-02 — Learning Consumer Audit

## 1. Which learning scripts currently read ad-hoc verdict/dashboard/local artifacts
- `scripts/ops/nightly_eod_learning_runner.py` reads `velo_verdicts` + `data/results/rp_results_{date}.json` directly for Main VELO only — never touches New Build's Lane A/B/C ranks or `policy_v1` decisions at all today.
- `scripts/ops/build_old_velo_three_option_card.py`, `run_radical_shadow_today.py`, `run_tri_lane_stress_test.py`, `build_deep_race_agent_v1.py`, `build_course_master.py` each read their own local artifacts independently — no shared row schema between them (this fragmentation is exactly what produced the July 05 reconciliation errors).
- `scripts/ops/update_mission_control.py` / `scripts/audit/run_velo_council.py` read Sigma + observability artifacts, not New Build's model-level rank/policy split.

## 2. Where `canonical_model_scorecards` should replace those reads
- Any future "did model X get the winner" question should query `canonical_model_scorecards` by `(run_date, race_id, model_name)` instead of re-deriving from `two_lane_readiness_{date}.json` or `passport_strength_score` each time — this is the entire point of the contract: one row, one join key, no re-derivation.
- Nightly learning could add a New Build-specific study pass reading `canonical_model_scorecards WHERE model_name LIKE 'NEW_BUILD_%'` to track Lane A/B hit rate and policy-blocked-hit rate over time, separately from Main VELO's own Sigma reconciliation. **Not implemented in this mission** — audit only, per scope.

## 3. How learning should classify each `learning_class` value
- **`MODEL_HIT_POLICY_BLOCKED`** — the model's raw rank found the winner; the policy layer did not clear it for any action. Treated as shadow evidence for model quality, explicitly NOT evidence of realized value (no stake was ever possible). Accumulates toward "should this model's policy thresholds be revisited," not toward promotion.
- **`MODEL_HIT_POLICY_ALLOWED`** — the model found the winner AND its own policy would have authorized a paper-execution-lane action. This is the strongest category of shadow evidence and the one that should accumulate toward any future promotion discussion (still gated by all standing hard laws).
- **`MODEL_MISS_POLICY_ALLOWED`** — policy cleared a pick that didn't win. Standard shadow-tracking miss, no special flag.
- **`PROXY_NOT_A_MODEL_CLAIM`** — never counted in any model's hit/miss tally. Kept in the scorecard purely for audit-trail visibility into what a naive/incorrect report might have mistakenly cited.
- **`TIE_UNRESOLVED`** — never counted in any strike-rate calculation. A race where the field's tie_status is not `CLEAN` for a given model contributes zero evidence either way until the underlying tie-break bug (see `docs/current/VELO_MODEL_SOURCE_MAP.md`) is fixed.

## 4. Why promotion remains gated
Every hard law from `docs/current/ONE_TRUTH.md` is untouched by this mission: live model weights frozen, no staking, Council/Mission Control gates unchanged, no Supabase write executed (dry-run only). A single day's `MODEL_HIT_POLICY_BLOCKED` row — however striking (a 41.0 winner) — is one data point. Promotion requires multi-day accumulated evidence through the existing Council/Mission Control gates, which this mission does not touch, run, or bypass.

# MODEL-TRUTH-02 — Dashboard Consumer Audit

## 1. Current dashboard source paths
`scripts/ops/new_build_dashboard_server.py`:
- `_build_governed_card_from_two_lane_readiness()` reads `data/new_build/reports/two_lane_readiness_{date}.json` directly (`lane_a_top3` per race) — this is New Build's live panel.
- `_build_no_rpr_race_map()` reads `velo_verdicts.full_analysis.predictions[].sqpe_no_rpr_shadow_prob` per runner (Supabase) — the No-RPR panel, with the confirmed tie-break bug.
- `_build_truth_summary()`/`_build_dashboard_truth_panel()` read observability JSON, `two_lane_readiness`, `sigma_memory_summary.json`, `router_shadow_audit_latest.csv`, `doctrine_scorecard_latest.json`, `sidecar_stack_latest.json` — none of these are the canonical scorecard.

## 2. Which panels should switch to `canonical_model_scorecards`
- New Build panel (currently `lane_a_top3` direct read) — switch to a query on `canonical_model_scorecards WHERE model_name='NEW_BUILD_LANE_A_MODEL' AND dashboard_visible=true`, so the dashboard and the canonical proof are guaranteed to agree (no more "dashboard says X, report says Y").
- No-RPR panel — switch to `canonical_model_scorecards WHERE model_name='SQPE_NO_RPR_SHADOW'`, which already carries `tie_status` explicitly, closing the tie-break-bug gap at the source instead of leaving it to whichever function happens to sort last.

## 3. Which panels still need live runtime artifacts (not canonical scorecard)
- The truth-summary panel's freshness/health fields (observability status, Sigma pending/complete, persistence status) are operational health signals, not model-result claims — they should stay reading live runtime files.
- Tri-Lane / Deep Race Agent / Course Master governance overlays are not per-horse model picks (per `MODEL_RESULT_REPORTING_LAW` — they don't produce a rankable row), so they are out of scope for `canonical_model_scorecards` entirely.

## 4. Exact API endpoint to add next
`GET /api/canonical-scorecard?date=YYYY-MM-DD` — reads `canonical_model_scorecards` for the date (Supabase, read-only), returns the same 23-column shape as the CSV. This becomes the single source the dashboard queries for any model-comparison claim; `/api/governed-card` continues to serve the existing operational panels unchanged in this phase.

## 5. Risks
- Supabase `canonical_model_scorecards` will be empty until an operator explicitly authorizes `--execute` on `persist_canonical_model_scorecard.py` for each date — the new endpoint must degrade gracefully (empty result, not an error) until backfilled.
- Rewriting the dashboard's existing panels to read from Supabase instead of local JSON changes latency/availability characteristics (network dependency vs local file read) — should be tested under normal operating conditions before switching the live New Build panel over, not done in this report-only phase.
- Not done in this mission: no dashboard code was modified. This is an audit only, per the mission's explicit scope.

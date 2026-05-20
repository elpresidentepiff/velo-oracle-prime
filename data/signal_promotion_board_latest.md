# VÉLØ Signal Promotion Board

Generated: 2026-05-15

## Summary

- This board ranks candidate signals by current role, evidence, and promotion readiness.
- It reads the unified evidence corpus only.
- It does **not** change live scoring, router logic, or staking.

## Board

| Signal | Status | Weight | n | matched n | SR | Frame | ROI | Recommendation | Reason |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| improvement_score / IMPROVE_HIGH | STORED_ONLY |  | 33 | 29 | 41.38 | 82.76 | -34.07 | HOLD | Unified corpus still shows a live-truth gap; hold pending corpus stabilization and ablation. |
| market_deception_score / MDS_HIGH | LIVE_WEIGHTED | 0.10 | 23 | 22 | 63.64 | 95.45 | -6.23 | KEEP_LIVE | Best live sidecar with clean evidence in the unified corpus. |
| place_prob / PLACE_PROB_HIGH | LIVE_WEIGHTED | 0.08 | 254 | 235 | 28.94 | 62.98 | -29.90 | KEEP_LIVE | Supportive live sidecar; useful for stability and frame support. |
| longshot_score | LIVE_WEIGHTED | 0.07_gated | 9 | 9 | 0.00 | 33.33 | -100.00 | KEEP_LIVE | Gated live component only for genuine longshot context. |
| router_v2_class4_shadow_pass | CANDIDATE_FOR_LIVE_REVIEW |  | 17 | 17 | 41.18 | 82.35 | 30.18 | PROMOTE_TO_PAPER_TEST | Strong early lane with n below full gate; keep accumulating. |
| router_v1_shadow_pass | SHADOW_ONLY |  | 27 | 27 | 37.04 | 85.19 | 11.52 | KEEP_SHADOW | Positive lane evidence, but still route-shadow only. |
| Racing API enrichment shadow score | SHADOW_ONLY |  | 5 | 5 | 40.00 | 60.00 | -13.40 | KEEP_SHADOW | Retrospective strength exists but leakage risk remains active. |
| B_LOW_VP_SUPPRESS / suppress flags | OPERATOR_VISIBLE |  | 212 | 196 | 14.29 | 37.24 | -12.30 | FREEZE | Confirmed drag zone; suppress overconfidence instead of promoting. |
| POWER_ANCHOR_MODE paper directives | PAPER_ONLY |  | 2 | 2 | 100.00 | 100.00 | 58.00 | PROMOTE_TO_PAPER_TEST | Paper evidence is positive but still too small for any live discussion. |
| Playbook G shadow | SHADOW_ONLY |  | 490 | 446 | 20.18 | 50.90 | -14.97 | KEEP_SHADOW | Shadow-only layer with no live probability impact. |
| Racing API connection shadow score | SHADOW_ONLY |  | 10 | 10 | 50.00 | 70.00 | 25.60 | KEEP_SHADOW | Leakage-flagged retrospective enrichment; no scoring impact allowed. |
| release_day_prob | STORED_ONLY |  | 0 | 0 |  |  |  | DO_NOT_PROMOTE | Disabled and not a current production driver. |
| comment_intel_score | STORED_ONLY |  | 0 | 0 |  |  |  | DO_NOT_PROMOTE | Disabled and not proven as a production driver. |
| router_v6_gold_seam_watchlist | SHADOW_ONLY |  | 5 | 5 | 60.00 | 100.00 | 115.00 | KEEP_SHADOW | Insufficient sample; no promotion path yet. |
| Racing API course shadow score | SHADOW_ONLY |  | 4 | 4 | 75.00 | 75.00 | 88.75 | KEEP_SHADOW | Retrospective signal, but leakage risk blocks promotion. |
| Racing API distance shadow score | SHADOW_ONLY |  | 6 | 6 | 33.33 | 33.33 | -27.83 | KEEP_SHADOW | Retrospective signal, but leakage risk blocks promotion. |
| WATCH_ONLY paper directives | PAPER_ONLY |  | 13 | 13 | 30.77 | 76.92 | -26.08 | KEEP_SHADOW | Watch-only paper directives are evidence context, not probability signals. |
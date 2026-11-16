# Champion Intent enriched challenger — wire audit (2026-11-16)

Status: **AUDITED / NOT WIRED / NO PRODUCTION CHANGE**. Branch is an operator review, not approval to promote or retrain Prime.

## Verified source-to-consumer graph

| Producer | Artifact / consumer | Result |
|---|---|---|
| Racing Post canonical capture | `current_card_passport_feed_<date>.jsonl` → `build_intent_shadow_scorecard.py` | CONNECTED in code; 2026-11-16 persisted scorecard |
| Historic intent builder | `current_card_intent_features_<date>.jsonl` → `build_intent_shadow_scorecard.py` | CONNECTED with median fallback; 74/222 2026-11-16 rows have intent history |
| Passport live features | `passport_live_features` → Champion Intent | CONNECTED with median fallback; 103/222 rows flagged passport found |
| Doctrine eight signals | `release_window_score, going_fit_score, distance_fit_score, quiet_run_score, trainer_timing_score, jockey_switch_intent, setup_run_flag, cash_run_flag` | NOT LIVE: all eight explicitly median-filled for all runners |
| FormFav UK shadow | `run_formfav_uk_enhanced_shadow.py` → `velo_report_artifacts.formfav_uk_shadow_features` | CAPTURED 2026-11-16; NOT CONSUMED by Champion Intent |
| Champion Intent | `run_full_raceday.py` → `build_intent_shadow_scorecard.py` → CSV | CONNECTED in orchestration code |
| Champion Intent result evaluation | `run_multimodel_sigma.py` → local CSV or `canonical_model_scorecards` fallback | CONNECTED in code; confirm actual per-model reconciled counts |
| Rich Context shadow packets | `rich_context_shadow_packets` | 153 packets 2026-11-16, status AWAITING_FROZEN_MODEL_FIT, probabilities null |
| Rich Context trained scorer v1 | `rich_context_challenger_scores` | 153 scores 2026-11-16; all production_influence=false |
| Rich Context v2 | `models/rich_context_challenger_v2/metadata.json` | FIT ARTIFACT EXISTS, but latest production-stored scores are v1; v2 explicitly excludes FormFav, Spotlight, connections passports |
| New Build readiness | `velo_report_artifacts.new_build_input_health` | DEGRADED: 103/153 GB/IE passport coverage (67.32%, below 70% gate) |
| Enriched Champion Intent | FormFav + passport + historical intent → independently trained frozen model → independent predictions → EOD Sigma | **NOT IMPLEMENTED / NOT WIRED** |

The 222 Champion Intent rows include additional jurisdictions; the 153 GB/IE runner denominator is a distinct coverage cohort. Do not conflate the denominators.

## Wiring contract — implement in this order

1. **Freeze original:** Keep `CHAMPION_INTENT_SHADOW` model, inputs, ranking and output unchanged. Its 2026-11-16 pre-race record (Splintered, 18:00 Wolverhampton, first-ranked; 126.0 decimal SP in Sigma) is the baseline, not a training target.
2. **Identity and chronology:** Join FormFav factual runner records to RP by race date, jurisdiction, track/race identity and normalized horse identity; reject ambiguous joins. Only accept records captured before scheduled off. Record `source_timestamp`, `capture_timestamp`, `join_status`, `missing_reason` and immutable input hash.
3. **Feature contract:** Explicitly whitelist factual `ff_*` fields (pace/style, class, track/distance/going, form and coverage/quality), RP Spotlight and historical intent. Exclude FormFav provider predictions, results, post-off fields and leakage. Train and score with the same versioned feature builder. Missing must be flagged, not silently treated as a positive signal.
4. **Fit only after history gate:** Build chronological pre-off training and holdout cohorts with adequate historical FormFav coverage. No fitting on 16 Nov outcomes to explain 16 Nov selections; that would be hindsight leakage. Until coverage passes, emit `BLOCKED_INSUFFICIENT_HISTORY` and continue factual packet capture.
5. **Independent shadow lane:** Version `CHAMPION_INTENT_ENRICHED_V1`, record `model_sha`, `code_sha`, `feature_schema_sha`, `input_sha`, source coverage, probability, rank and `production_influence=false`. Keep original scores beside enriched scores for the same runner and race.
6. **Wire full lifecycle:** Morning orchestration → durable Supabase shadow scorecard → dashboard as separate model → evening `run_multimodel_sigma.py` join by canonical race/horse IDs → winner/place outcomes and denominator → comparative calibration and ablation. EOD must fail closed on missing or zero joins; never silently report zero as a completed comparison.
7. **Council/learning gate:** `EVIDENCE_INCOMPLETE` or `PENDING_MANUAL` cannot result in `PASS_TO_LEARNING` or an open learning gate. Shadow learning and promotion remain blocked until independent verified gate tests pass.
8. **Splintered forensic replay:** Preserve original pre-off rank and full feature vector; report per-feature observed vs median-imputed values and model contribution using the frozen original model. Replay against enriched model only after independent chronological fit; do not claim the 125/1 winner was caused by FormFav.
9. **Proof tests:** Synthetic and real-date identity joins, pre-off timestamp boundary, provider prediction exclusion, model schema exact match, missingness flags, zero production influence, idempotent Supabase writes, morning/evening same SHA, zero-join tripwire, comparison of pre-race picks and settled results.
10. **Release gate:** No merge/deploy/promote without green tests, a reproducible backtest with date-split holdout, feature coverage report and a fresh non-destructive end-to-end shadow run.

## One-truth constraints

Canonical code/model: approved GitHub main SHA. Execution: Railway deployment SHA and service. Evidence: immutable Supabase prediction, capture, result, run and audit records. Dashboard: reconciled display only. Old docs, local snapshots, CSV exports and shadow provider data cannot override canonical truth.

## Open defects to reconcile in separate changes

- Council: 23 of 107 historical records were `EVIDENCE_INCOMPLETE` with `PASS_TO_LEARNING`; correct the gate and audit historical decisions without rewriting original evidence.
- Duplicate cron ownership: both `velo-rp-capture` and `velo-prime-scoring` have scoring-related schedules; prove owner guard then remove redundant scheduling.
- Canonical system contract: multiple competing `ONE_TRUTH`/harness docs and command entry points. Consolidate by superseding older docs, not deleting forensic history.
- Local-only model/passport work and outstanding PRs require branch/commit comparison; cannot infer laptop-only state from GitHub.

**No production code, model, Railway cron, Supabase data, staking or learning gate was modified by this audit.**

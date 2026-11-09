# VELO Decision and ACCA Research Implementation Plan

**Prepared:** 2026-09-29
**Mode:** PAPER/SIM research only
**Scope:** evaluation truth, canonical prices, Mission Control, dashboard, forward laboratory, conditional model research, meta-selection, and accumulators
**Prohibited:** live betting, staking, promotion, weight changes, gate bypasses, retrospective ticket substitution

## Objective

Turn Velo's many model outputs into a governed decision system that can prove, before racing, whether an individual selection or a pre-registered 2-9 leg accumulator has positive forward evidence. Preserve every model's raw opinion, but do not count correlated copies as independent evidence.

The plan distinguishes two questions:

1. **Oracle ceiling:** did some combination of model selections contain a winning 4-9 fold after results were known?
2. **Executable forward evidence:** did a finite rule select and freeze that exact ticket before the first leg, at captured prices and terms?

The oracle ceiling is useful research. Only the second question can support a decision policy.

## Phase 0 — Documentation and dependency discovery (complete)

### Authoritative contracts

- `docs/current/ONE_TRUTH.md`
- `THE_ONE_TRUTH.md`
- `docs/current/MODEL_RESULT_REPORTING_LAW.md`
- `docs/engineering/VELO_ACCA_LANE_PROTOCOL_V1.md`
- `docs/evidence/ACCA_LANE_V2_SHADOW_SPEC.md`

### Existing implementation anchors

- Canonical builder: `scripts/ops/build_canonical_model_scorecard.py`
- Canonical persistence: `scripts/ops/persist_canonical_model_scorecard.py`
- Canonical learning: `scripts/ops/build_canonical_learning_events.py`
- Subject settlement semantics: `src/velo/learning/result_source_selector.py`
- Rich provenance types: `src/velo/learning/learning_event_v2.py`
- EOD orchestration: `scripts/ops/run_full_raceday_eod.py`
- Mission Control: `scripts/ops/update_mission_control.py`
- Dashboard API/UI: `app/main.py`, `scripts/ops/new_build_dashboard_server.py`, `app/static/dashboard/index.html`
- Existing accumulator lane: `scripts/audit/acca_detector.py`, `scripts/audit/acca_results_audit.py`, `scripts/audit/acca_replay_audit.py`, `scripts/audit/acca_ablation_replay.py`
- Forward packet pattern: `scripts/ops/run_captain_velo_shadow.py`
- Honest overlap pattern: `scripts/ops/model_disagreement_audit.py`

### Mandatory pre-edit gate

Before changing any function or class, run GitNexus upstream impact analysis for that symbol. Warn on HIGH/CRITICAL risk. Before every commit, run GitNexus change detection and confirm that only intended flows changed.

## Phase 1 — Freeze the baseline and protect the dirty worktree

### Work

1. Record the current commit, status, relevant generated artifacts, and current Supabase canonical row counts.
2. Do not clean, reset, restore, or move existing runtime artifacts.
3. Verify the applied Supabase schema through `information_schema`; migration files alone are not proof.
4. Create a fixture manifest for 2026-09-26 through 2026-09-28 covering Captain packets, canonical cards, results, learning events, Council, Mission Control, and EOD reports.
5. Establish baseline outputs for Captain: selection count, settled count, NR/void count, captured return, SP return, CLV, overlap and disagreement.

### Verification

- Baseline hashes and counts are reproducible.
- No production model, weight, gate, browser profile or live state changes.
- Existing dirty files remain untouched.

## Phase 2 — Repair canonical settlement and price truth

### Work

1. Add an additive Supabase migration; do not edit historical create migrations.
2. Extend scorecard and event truth with typed fields aligned to `LearningEventV2` concepts:
   - `subject_outcome_status`
   - `subject_is_non_runner`
   - `settlement_status`
   - `stake_void`
   - `captured_odds_dec`
   - `odds_capture_ts`
   - `price_source`
   - `settled_sp_dec`
   - optional `bsp_dec`
   - `odds_timestamp_before_off`
   - result completeness/hash fields
3. Reuse `runner_outcome_status()` from `result_source_selector.py`; do not create competing NR rules.
4. Replace `sp_dec = settled SP or captured odds` with separate fields.
5. Add canonical learning classes for `NON_RUNNER_VOID`, `UNSETTLED_UNKNOWN`, and `TERMINAL_LOSS`.
6. Make tie semantics uniform. A ranked probability lane with an unresolved top tie is not an official unique pick.
7. Preserve the existing upsert identities and paginated Supabase reads.
8. Rebuild only reconstructable historical rows. Never fabricate missing captured prices or timestamps.

### Acceptance tests

- Captain NR is void, not a miss.
- Blank result is UNKNOWN, not NR and not a loss.
- F/PU/UR/BD/RO/DSQ are terminal losses for a starter, never voids.
- Captured 11.00 and settled 4.33 remain distinct typed values.
- A missing or post-off captured timestamp fails closed.
- Unresolved ties are excluded from official unique-pick metrics.
- Local row count/hash reconciles with Supabase for the date.

## Phase 3 — Make Mission Control genuinely final

### Work

1. Keep the existing post-Council Mission Control refresh because the nightly learner consumes it during admission.
2. After nightly learning, canonical rebuild/persist, canonical event persistence, nightly-event persistence and disagreement audit, invoke the existing `update_mission_control.py --date` command again.
3. Make this post-learning refresh mandatory.
4. Run Step 22 only after that refresh so Supabase receives the real final object.

### Acceptance tests

- EOD contains both pre-learning/post-Council and post-learning/final refreshes.
- Final Mission Control reports actual learning-event counts, admission outcome and persistence state.
- A failed final refresh prevents `DAY COMPLETE`.

## Phase 4 — Upgrade the canonical dashboard

### Work

1. Continue reading canonical Supabase endpoints only; no local-file fallback for canonical claims.
2. Extend the model-performance panel with:
   - selections, settled, void/NR and unresolved counts
   - wins, places/frames and strike rate
   - captured odds, SP, CLV/price ratio
   - stake, return, profit and ROI
   - cumulative forward-only window
   - model overlap and disagreement cohort
   - ex-big-price result
   - day-clustered/bootstrap uncertainty
   - maximum drawdown for forward tickets
3. Label production, shadow, proxy and selective-value lanes distinctly.
4. Cluster correlated model families. Never display four near-identical lanes as four independent votes.
5. Add a Captain panel showing all frozen selections and settlement, not only a generic rank-one row.
6. Add a post-learning state panel sourced from final Mission Control.

### Acceptance tests

- Monday Captain displays 2/6 settled, one void, not 2/7.
- Captured-price and SP P&L reconcile independently.
- No dashboard write calls exist.
- Missing captured price is displayed as unavailable, never substituted with SP.

## Phase 5 — Build the forward model laboratory

### Work

1. Produce one immutable pre-race packet per model/date from the latest complete strictly pre-off snapshot.
2. Store packet hash, commit/model version, source paths, timestamps and captured prices.
3. Evaluate every model with:
   - Brier score, log loss and calibration error
   - hit/frame rates
   - captured-price and SP ROI
   - CLV
   - drawdown and return concentration
   - leave-one-big-winner-out results
   - agreement/disagreement versus production and market favourite
4. Split retrospective, backfilled and genuinely forward evidence in every output.
5. Use day-block bootstrap intervals and report the number of days as well as races.

### Acceptance tests

- No evaluated row uses a snapshot at or after the off.
- No forward result can be overwritten by a later rerun.
- Every zero-selection day is retained.
- All results reproduce from frozen packet plus canonical result truth.

## Phase 6 — Conditional research and governed meta-selector

### Work

1. Build a feature matrix using only pre-race values: model probabilities/ranks, disagreement, market probability, captured odds, race type, field size, course, going, class, pace/shape, campaign state, and available trainer/jockey context.
2. Perform rolling/purged time splits. Train/tune on earlier dates and score later untouched dates.
3. Evaluate conditional regions without using the validation period to define them.
4. Compare simple transparent selectors first:
   - production only
   - Captain only
   - market favourite
   - production when models agree
   - Captain when its structural/market and price gates pass
   - explicit abstain
5. Only then test a calibrated meta-model. Penalise correlated inputs and retain an abstain outcome.
6. Freeze every candidate policy before forward scoring. No same-day adaptation.

### Acceptance tests

- No result, SP, post-off price or future date enters training features.
- Every reported policy has untouched forward dates.
- Performance includes uncertainty, drawdown and ex-big-winner sensitivity.
- No model weight or production decision changes during research.

## Phase 7 — Repair and extend the governed ACCA lane

### Existing lane defects to fix

- Legacy results audit treats PU/F/UR/RO/REF as NR/void.
- Result identity can depend only on horse name.
- No typed captured prices, timestamps, price terms, joint probability, EV or P&L.
- Combination score assumes independence and does not quantify correlation.
- Existing replay uses only seven old days and reuses them for comparison/tuning.
- No accumulator unit tests exist.
- No current forward ACCA packets exist.

### Two distinct outputs

#### A. Oracle-ceiling research

For each historical day, determine whether the union of pre-race model selections contained at least one winning 2-9 fold. Report:

- number of eligible races and candidates per race
- total combinatorial ticket count
- smallest winning fold
- number and percentage of winning tickets
- total outlay required to cover the winning ticket
- captured-price return where genuine prices exist
- net result from buying the complete search space

This proves opportunity coverage, not selectability.

#### B. Forward executable shadow tickets

Pre-register a finite set of templates, initially:

- 2-leg Banker
- 3-leg Banker
- 2-leg Banker + Glue
- 3-leg Banker + Glue
- separately labelled experimental 4, 5, 6, 7, 8 and 9 folds

Each daily packet must contain:

- generated timestamp and hash before the first leg
- exact rule/template/version
- unique race ID per leg
- selected horse/role/model provenance
- captured odds and timestamp per leg
- product price and predicted joint probability
- correlation flags and effective independent-leg count
- explicit `NO_ACCA` when no template qualifies
- fixed maximum ticket count per day
- PAPER/SIM/no-execution flags

### Settlement law

- Settle against canonical RP result identity by race ID and horse ID.
- True NR/WD voids a leg and reduces the fold according to the declared research rule.
- F/PU/UR/BD/RO/REF is a losing leg.
- Missing/incomplete/identity-conflicted results remain unresolved and fail closed.
- One horse from any race maximum.
- Never regenerate tickets after results.
- Preserve losing and zero-ticket days.

### Correlation and multiplicity

1. Cluster model families and cap repeated-family influence.
2. Measure leg dependence by model family, venue, race type, trainer/jockey and same-meeting exposure where data permits.
3. Report raw product probability and correlation-adjusted probability separately.
4. Apply holdout and multiple-testing correction because searching thousands of ticket rules manufactures apparent winners.
5. Compare against identical-card baselines: favourites, production-only, random weighted by market probability and simple top-probability folds.

### Promotion gates

- No promotion discussion before at least 30 forward race days and a predeclared minimum ticket count.
- Require positive captured-price ROI with a lower confidence bound that is not materially negative.
- Require acceptable drawdown and result not dependent on one winning ticket.
- Require stable performance after removing the largest return.
- Require sufficient effective independent legs, not merely nominal fold size.
- Operator decision remains mandatory. No execution path is added.

## Phase 8 — Persist research artifacts without contaminating learning

### Work

1. Add dedicated canonical research tables/artifacts for price observations, forward model evaluations and ACCA packets/settlements.
2. Keep raw predictions immutable and derived metrics reproducible.
3. Persist with idempotent keys including date, packet ID, template version and ticket ID.
4. Add dashboard read-only endpoints and a PAPER/SIM ACCA panel.
5. Do not feed accumulator outcomes into production weights or Playbook-G state during the research phase.

## Phase 9 — Verification, rollout and commits

### Test layers

1. Unit: settlement states, captured-price separation, tie rules, joint-price arithmetic, unique-race legs, correlation flags.
2. Fixture: 2026-09-26 through 2026-09-28 Captain and canonical truth.
3. Integration: morning packet → results → EOD → post-learning Mission Control → Supabase → dashboard.
4. Leakage: reject post-off timestamp, result/SP feature access and same-period tuning.
5. Property tests: ticket settlement across NR/terminal/unknown permutations and combination-size invariants.
6. Regression: existing governance, canonical, Mission Control and EOD suites.

### Commit sequence

1. `fix: canonical settlement and captured price truth`
2. `fix: final mission control refresh after learning`
3. `feat: canonical model evaluation dashboard`
4. `feat: forward model research laboratory`
5. `feat: governed meta-selector shadow`
6. `fix: accumulator settlement and identity truth`
7. `feat: forward accumulator research packets`
8. `feat: accumulator evaluation dashboard`

Run GitNexus change detection before every commit. Commit no runtime data, browser profiles, credentials, model binaries, live weights or unrelated dirty files.

## Definition of done

- Captain and every model have truthful settled/void/tie-aware forward metrics.
- Captured odds are canonical typed data, not prose.
- Mission Control and Supabase show the completed learning state.
- Dashboard reconciles to canonical truth and shows uncertainty/correlation.
- A meta-selector can be evaluated without future leakage and can abstain.
- Oracle ACCA coverage and forward frozen-ticket performance are reported separately.
- Every ACCA ticket is pre-race, finite, priced, identity-safe and PAPER/SIM.
- No live staking, execution, promotion, model-weight change or gate bypass exists.

# Wake Velo: Rich Context Challenger Plan V1

## Implementation status — 2026-11-08

The first fitted artifact is now a **shadow-only overlay**, not a production
model. Immutable `rich_context_shadow_packets` remain evidence; fitted
probabilities and ranks are written separately to
`rich_context_challenger_scores`, keyed by packet input hash and model version.

Dashboard contract `WAKE-VELO-DASH-04` reads that overlay only through an exact
`packet_input_sha256 -> input_sha256` join, reports the exact model version and
coverage, and refuses to display rows outside the PAPER/SIM boundary. It never
substitutes the Rich Context rank for Prime. Repeated scores from the same model
version are isolated to the newest coherent `scored_at` batch per race, with
older rows counted as superseded. Immutable packet rows, all selected-version
score rows, current-batch rows, linked current rows and superseded rows are
reported separately; coverage is linked-current/current-batch and never uses
the accumulated historical packet archive as its denominator. Mandatory
packet/score reads are bounded and
paginated; read failure, truncation or ambiguous batch identity suppresses the
entire overlay instead of presenting partial truth. Runner-label reads may
degrade labels only and are reported separately. Daily official-results settlement,
same-race evaluation and the predeclared forward promotion sample remain Phase 6
work; dashboard visibility is not evidence of promotion eligibility.

**Status:** execution contract; production promotion is not authorised
**Scope:** UK/IRE governed race-day path first; world jurisdictions remain separate
**Authority:** `docs/current/ONE_TRUTH.md`, `docs/current/RACE_DAY_RUNBOOK.md`, and `docs/current/FORBIDDEN_ACTIONS.md`
**Prime invariant:** existing production probabilities, ranks, weights, gates, and source policy must not change while this plan is in shadow evaluation

## Executive decisions

1. **Do not resubscribe to The Racing API now.** The governed RP capture and results path does not require it. Restoring credentials would revive stale entry points without fixing the disconnected historical extractor or the incompatible old `hrs_*` versus current numeric RP identity spaces.
2. **FormFav predictions never enrich Velo.** Provider selections, win/place probabilities, ranks, confidence, edge, fair probability, predicted order, recommendation badges, results, and post-off data remain in a separate benchmark lane only.
3. **FormFav factual and provider-derived context may be tested.** Factual identity/form/connections/conditions fields and separately labelled provider-derived pace/class/bias fields may enter an isolated challenger only when identity, source time, race-off time, provenance, and missingness are proven.
4. **Comment intelligence is rebuilt as a truthful challenger.** The current model is not an RP Spotlight language model; it consumes structured doctrine fields which are commonly defaulted. RP comments must be parsed before challenger scoring, with raw-source hash, parser version, timestamp, identity evidence, and explicit exclusions for verdict-like language.
5. **Historical extraction moves to canonical RP/Supabase identities.** The existing Racing API-backed extractor is not activated. A new provider queries time-safe canonical history and emits coverage rather than silently replacing absence with neutral evidence.
6. **Promotion is earned, not assumed.** Every feature family is evaluated on the same forward race universe using chronological freezes and post-settlement labels. Production remains unchanged until a governed promotion tribunal accepts statistically and operationally credible evidence.

## Verified starting state

- `scripts/ops/run_prime_today.py` calls `score_race_velo_prime()` before Spotlight parsing; Spotlight therefore cannot change Prime probabilities or rank.
- `app/services/velo_prime_service.py` calls `build_v17_feature_vector()`; `app/services/sqpe_v17_service.py` fills missing doctrine features from runner keys or neutral defaults and does not invoke `V17FeatureExtractor`.
- `app/services/v17_feature_extractor.py` calls the retired Racing API horse-results endpoint and silently defaults on failure. It must not be connected to governed scoring.
- `src/intelligence/velo_prime_ensemble.py` gives `comment_intel_score` zero weight and records it as disabled/stored-only. This agrees with `docs/current/ONE_TRUTH.md` and must remain true for production.
- `new_build_velo/current_card_feed.py` and `new_build_velo/paper_scorer.py` consume passport evidence in the New Build lane; Prime readiness does not mean Prime consumes those features.
- `src/velo/formfav_enrichment.py` deep-copies RP cards and the UK FormFav shadow does not read `formfav_predictions`. This separation is correct.
- `src/velo/formfav_cache_client.py` discards the source row timestamp after freshness checking. Current enrichment cannot prove each field existed before the relevant off time.
- `scripts/ops/formfav_readiness.py` incorrectly requires prediction coverage for a factual enrichment path.
- `app/main.py` -> `app/pipelines/score_daily_runner.py` -> `scripts/ops/run_cloud_raceday.py` exposes a stale Racing API scoring route, while the governed Railway RP cron is clean.
- `src/velo/racecard_loader.py` can silently fall back from missing RP evidence to Racing API in `auto` mode; `src/velo/source_truth_enforcer.py` and CI still permit that source, contradicting ONE_TRUTH.

## Target architecture

```text
Authenticated RP capture (canonical card)
       +
FormFav factual snapshot (allowlisted, pre-off, identity-matched)
       +
Canonical RP/Supabase history (strict as-of cutoff)
       +
RP Spotlight factual comment parse (pre-score, versioned)
       +
Passport/JTC context (provenance-controlled)
       |
       v
Rich Context feature manifest -> isolated challenger scorer
       |                              |
       |                              +-> immutable shadow packet
       |                              +-> Supabase challenger rows
       v
Production Prime runs independently and remains invariant
       |
Post-settlement canonical results
       v
Same-universe chronological ablations and promotion evidence
```

## Phase 0 — Evidence and contracts (complete)

### Sources

- `docs/current/ONE_TRUTH.md`
- `docs/current/RACE_DAY_RUNBOOK.md`
- `docs/current/FORBIDDEN_ACTIONS.md`
- `docs/engineering/FORMFAV_UK_ENHANCED_VELO_PLAN_V1.md`
- `docs/engineering/FORMFAV_PREMIUM_GLOBAL_READINESS_PLAN_V1.md`
- `docs/engineering/RP_VS_FORMFAV_DATA_FLOW_V1.md`
- `scripts/ops/run_prime_today.py`
- `app/services/velo_prime_service.py`
- `app/services/sqpe_v17_service.py`
- `app/services/v17_feature_extractor.py`
- `src/intelligence/velo_prime_ensemble.py`
- `src/velo/formfav_*.py`
- `src/velo/racecard_loader.py`
- `src/velo/source_truth_enforcer.py`

### Exit evidence

- Live call graph, inactive features, source contradictions, FormFav temporal gaps, and legacy API entry points have been identified.
- The implementation boundary is explicit: shadow-only changes first; no production weight or gate changes.

## Phase 1 — Seal stale Racing API live paths

### Objective

Make every governed UK/IRE entry point fail closed on missing RP evidence and prevent accidental resurrection of retired API scoring.

This is the **first runtime phase**. No new provenance, historical, comment or challenger runtime may be connected until these live-path contradictions are sealed and verified.

### Implementation anchors

- Redirect `app/pipelines/score_daily_runner.py` from `scripts/ops/run_cloud_raceday.py` to the existing governed RP cloud executor while preserving trigger/run identity and terminal `pipeline_runs` semantics.
- Update the `/api/trigger/score-daily` contract in `app/main.py` and its tests.
- Remove the Racing API fallback from production `auto` logic in `src/velo/racecard_loader.py` and production CLI choices in `scripts/ops/run_prime_today.py`.
- Block all API loader aliases in the production contract in `src/velo/source_truth_enforcer.py`.
- Replace Racing API checks in `scripts/ops/preflight_10am_check.py` and `src/preflight.py` with RP session/artifact integrity, Supabase, and factual FormFav readiness checks.
- Correct `.github/workflows/ci.yml` assertions so CI proves API sources are blocked.
- Quarantine rather than blindly delete optional/legacy dependencies in `workers/velo_vox/*`, `workers/ingestion_scheduler.py`, `scripts/ops/run_international_sigma.py`, `new_build_velo/result_fetcher.py`, and the `--source api` branch in `scripts/ops/run_results_sigma.py`.

### Verification

- Route test proves `/api/trigger/score-daily` cannot import or invoke `run_cloud_raceday.py`.
- Source-truth tests prove `api`, `racing_api`, and equivalent aliases fail closed.
- Missing RP artifacts produce a truthful blocked terminal row, never an API-backed score.
- Railway configuration audit confirms all active UK/IRE service commands point to governed RP entry points and deployed commit SHAs are recorded.
- Repository network-call census finds no reachable Racing API call from the governed UK/IRE graph.

### Anti-pattern checks

- Do not delete provenance columns, migrations, archived payloads, or static alias caches.
- Do not repurpose legacy environment-variable names for a new provider.
- Do not let research or Vox adapters share the production source allowlist.
- Do not treat a passing CI build as proof of deployed Railway commands.

### Rollback

Rollback only the entry-point redirect if governed RP invocation itself regresses. Never restore silent API fallback; block the trigger and report the failure instead.

## Phase 2 — Freeze the Rich Context feature and provenance contract

### Objective

Create one versioned contract that accepts only explicitly permitted inputs, rejects provider predictions recursively, and makes every feature independently auditable.

### Mandatory Supabase design gate before provenance transport

Before changing `formfav_cache_client.py`, enrichment transport, persistence code, or migrations:

1. introspect the **deployed** Supabase tables, columns, constraints, indexes, triggers, RLS enablement and policies for every relevant `formfav_*`, racecard, runner, artifact and pipeline table;
2. record the inspection as reviewable evidence without printing credentials or personal data;
3. design an additive, append-only immutable capture/snapshot and challenger-manifest schema, including retention, idempotency, indexes, RLS, service-role access and rollback;
4. obtain the explicit operator approval required by `docs/current/FORBIDDEN_ACTIONS.md`, rule `NO_UNAPPROVED_SCHEMA_MUTATION`, before applying any migration;
5. apply the reviewed additive migration separately from runtime wiring and verify the deployed schema, indexes and policies after application.

Existing mutable `formfav_runner_form` rows, whose logical rows are overwritten on refresh and whose source timestamps are dropped during reconstruction, are **evaluation-ineligible**. They may support current-day diagnostics/readiness, but they must not be represented as immutable forward training evidence. No provenance transport work may claim training-grade status until the approved immutable snapshot/manifest store exists.

### Implementation anchors

- Add `src/velo/rich_context_feature_contract.py`.
- Amend `src/velo/formfav_cache_client.py` to carry source row time and immutable source identifiers forward.
- Amend `src/velo/formfav_enrichment.py` to attach race and runner provenance and identity-match evidence under `_formfav`.
- Amend `src/velo/formfav_uk_features.py` to emit contract metadata and remove badges from trainable vectors.
- Split factual readiness from provider benchmark readiness in `scripts/ops/formfav_readiness.py`.
- Add focused tests beside `tests/test_formfav_shadow_integration.py` and `tests/test_formfav_cache_client.py`.

### Required manifest per runner

- `feature_schema_version` and `challenger_version`;
- canonical race and horse identity;
- provider race key, runner number/name, and source row identifier;
- race-match and runner-match methods;
- source capture time and canonical UTC off time;
- `captured_before_off` and temporal eligibility verdict;
- raw payload hash and derived vector hash;
- field-family source, raw/derived classification, denominator, and missingness;
- family coverage, conflicts, quality tier, and training eligibility;
- recursive banned-field scan result.

### Allowed families

**Raw factual candidates:** runner number, scratched status, jockey, trainer, weight, claim, draw, age, sex, pedigree, raw form string, structured past starts, factual starts/wins/places splits, track, jurisdiction, scheduled start, timezone, race conditions, weather, field size, prize, distance, and independently timestamped pre-off quotes.

**Provider-derived context, isolated by family:** running style, early speed, settling position, pace scenario, pace pressure, class ratings/range/trend/fit, draw advantage, and bias strength.

### Banned recursively

- win/place probability, `modelRank`, selected/top horse, confidence, recommendation, predicted order;
- `edge`, provider fair price, `fairProbability`, price rank, prediction model outputs or versions as features;
- positive/negative/neutral badges and decorator counts;
- results, placings, margins, SP, post-off prices, result status;
- any field captured at or after off time;
- any ambiguous identity or row without a provable source timestamp.

### Verification

- Unit tests inject banned keys at multiple nesting levels and prove rejection.
- Golden fixtures prove allowed factual inputs survive unchanged with complete provenance.
- Temporal-boundary tests cover before, equal-to, after, missing, and timezone-conversion cases.
- Existing Prime scoring fixture is byte/rank invariant with the challenger enabled or disabled.
- Factual readiness retains the established **>=80% factual coverage gate** and passes without FormFav prediction rows; benchmark/prediction readiness reports independently and cannot stop factual enrichment or RP/Prime scoring.

### Anti-pattern checks

- No negative-only blacklist without a positive allowlist.
- No `updated_at` treated as historical capture proof unless the persisted row is immutable.
- No missing feature converted to a favourable or neutral value without a missingness flag.
- No provider-derived analytic labelled as a raw fact.
- No prediction coverage allowed to gate RP/Prime scoring.

### Rollback

Disable the challenger feature-manifest call and retain captured raw factual rows. Production is unaffected because it never reads this vector.

## Phase 3 — Build the canonical historical context provider

### Objective

Replace the disconnected Racing API extractor with a time-safe, identity-controlled RP/Supabase/passport provider for the shadow challenger.

### Implementation anchors

- Add a new provider adjacent to `app/services/v17_feature_extractor.py`; do not modify the legacy extractor into appearing canonical.
- Query canonical `racing_horse_runs` and passport evidence using the current numeric RP identity.
- Reuse reviewed identity logic from `new_build_velo/passport_lookup.py` and provenance fields from `new_build_velo/current_card_feed.py`.
- Define an explicit identity bridge for old `hrs_*` history only when exact mapping is independently proven.
- Emit source row IDs, as-of cutoff, identity method, history depth, coverage, conflicts, and missingness with every derived feature.
- Keep JTC-D and any connection analytics shadow-only unless their own governing contract permits more.

### Feature families

- horse recency and layoff pattern;
- course, distance, going/surface, code and class history;
- field-size, pace-position and handicap-context history where factual inputs exist;
- trainer recent form and course record;
- jockey recent form, course record and horse/jockey pairing;
- jockey change and trainer intent proxies;
- passport strength/context already available to New Build;
- explicit missing-history and identity-quality signals.

### Verification

- As-of tests prove no run on or after the race cutoff can enter the vector.
- Identity tests cover exact numeric RP ID, proven bridge, name collision, suffix/country ambiguity, and unresolved identity.
- SQL/query plans are reviewed for Supabase performance; pagination cannot truncate history silently.
- Sampled derived features are independently recomputed from source rows.
- Coverage report is produced by date, course, code, runner, and feature family.
- Failure to resolve identity yields ineligible/missing, never a guessed merge.

### Anti-pattern checks

- No horse-name-only join without the explicit identity contract.
- No current/future result leakage.
- No silent neutral defaults.
- No production scorer import of the legacy Racing API extractor.
- No overwrite of historical source provenance.

### Rollback

Disable the historical provider family in the challenger manifest. Frozen source snapshots and coverage diagnostics remain available for repair.

## Phase 4 — Build truthful pre-score comment intelligence

### Objective

Turn RP Spotlight prose into versioned factual/context features before challenger scoring, without importing tipster verdicts or outcome-like language.

### Implementation anchors

- Move comment parsing for the shadow lane before shadow scoring in `scripts/ops/run_prime_today.py`; leave production Prime call order and inputs unchanged.
- Reuse or wrap `workers/spotlight_parser.py` / `workers/spotlight_parser_v2.py` behind a versioned Rich Context parser.
- Persist raw comment hash, RP capture time, canonical runner identity, parser version, parse status, extracted spans/categories, missingness, and exclusions.
- Treat the existing `models/specialist/comment_intelligence_model` as legacy structured doctrine, not proof of an NLP model.

### Initial permitted categories

- factual trip/traffic adversity;
- equipment change when explicitly stated;
- return from layoff or run-frequency context;
- distance/surface/going/course evidence stated as past fact;
- class movement and race-shape context stated as fact;
- running style and likely position only when classified as derived context;
- trainer/jockey changes already identity-matched elsewhere.

### Excluded comment evidence

- RP verdict, tip, confidence, stars, prediction, recommended bet, likely winner wording;
- hindsight/results language;
- unsupported sentiment score used as a shortcut for factual extraction;
- text captured after off or without immutable source proof.

### Verification

- Labelled fixtures test extraction precision, negation, uncertainty, horse-reference resolution, and banned verdict removal.
- Parser-version reproducibility: identical input and version produce identical vector/hash.
- Comment-family output has meaningful variance and coverage; a constant-output detector fails the challenger build.
- Prime output invariance test proves the pre-score shadow parser cannot alter production inputs.

### Anti-pattern checks

- Do not call the legacy structured specialist an NLP model.
- Do not collapse prose into one opaque positive sentiment number.
- Do not treat “could”, “may”, “likely” or tipster opinion as fact.
- Do not use post-race comments in a pre-race vector.

### Rollback

Disable only the comment family and continue baseline plus other challenger families. Preserve raw hashes, parser diagnostics, and excluded spans.

## Phase 5 — Implement the isolated Rich Context challenger

### Objective

Score the enriched vector in a separate paper/shadow lane with production-invariant operation and durable evidence.

### Mandatory model and training protocol freeze

The following protocol must be reviewed, versioned and frozen **before** implementing or fitting the challenger. No model choice or hyperparameter may be selected after inspecting the untouched forward results.

1. **Baseline:** frozen production Prime probability/rank snapshot on the exact same eligible runners and races. A market-only reference and the isolated FormFav prediction benchmark may be reported, but neither supplies challenger features.
2. **Initial model class:** a deliberately simple, auditable regularised probabilistic ranker/classifier capable of handling explicit missingness. The exact estimator, objective, regularisation, class/race weighting and random seed must be declared in the protocol. A more complex model is a later separately versioned experiment, not an informal replacement.
3. **Universe:** declare jurisdictions, codes, race types, date bounds, runner eligibility, scratch policy, minimum identity/temporal quality, and result-settlement requirements. Every ablation must use the identical eligible race/runner IDs; family-specific missingness remains an input/coverage fact rather than silently changing the universe.
4. **Chronological split:** use an earlier chronological training window, a later chronological validation window for the one-time protocol/model selection, and a still-later untouched forward holdout. After protocol freeze, fresh daily shadow evidence begins strictly after the holdout/freeze boundary. Exact dates and hashes must be recorded before fitting.
5. **Calibration:** declare the calibration method and fit it only on the designated chronological calibration/validation portion. Calibration is never refit on the untouched forward holdout. Report both raw and calibrated Brier/log-loss/reliability evidence.
6. **Versioning:** persist dataset-manifest hash, feature schema, eligibility contract, estimator/library version, code SHA, training cutoff, split IDs, seed, hyperparameters, calibration version and model artifact hash.
7. **Hyperparameter freeze:** declare the bounded search space and selection metric before validation. Select once using training/validation only; freeze the winning configuration before touching holdout results.
8. **Identical retraining for ablations:** baseline-enriched and every feature-family ablation use the same model class, split IDs, seeds, fitting procedure, hyperparameter-selection rule and calibration procedure. Only the declared feature family changes. If a family changes eligible coverage, report that separately and do not use the reduced universe for the primary comparison.
9. **No production warm-start:** production probabilities may be evaluated as the baseline or included only as an explicitly declared fixed baseline covariate in a separately named experiment. They must not be silently blended into the challenger target.
10. **Predeclared success criteria:** predictive lift, calibration tolerance, coverage floor, stability slices, uncertainty, and price sensitivity are fixed before holdout evaluation. Failure remains a valid result.

### Implementation anchors

- Add a dedicated scorer/service and versioned configuration; do not add weights to `src/intelligence/velo_prime_ensemble.py`.
- Invoke it from `scripts/ops/run_prime_today.py` only after RP source and identity validation.
- Persist a separate artifact and Supabase rows with challenger probability, rank, feature-family coverage, input/vector hash, scorer version, eligibility, and reason codes.
- Extend `scripts/ops/persist_daily_artifacts.py` with additive challenger persistence and idempotent upsert keys.
- Add dashboard visibility as explicitly **SHADOW / NO PRODUCTION INFLUENCE**, never substituting missing Prime data.

### Required lanes

1. production Prime baseline snapshot;
2. historical facts only;
3. comment facts only;
4. FormFav raw factual only;
5. FormFav provider-derived pace only;
6. provider-derived class only;
7. track/draw/bias only;
8. connections/passports only;
9. market facts only;
10. full Rich Context combination;
11. FormFav prediction-only benchmark, including any provider fair price/fair probability, stored separately and never combined.

### Verification

- Challenger on/off produces identical Prime rows, ranks, hashes, and dashboard Prime representation.
- Persistence is idempotent, date-scoped, schema-versioned, and survives process restart.
- Missing optional families degrade challenger coverage truthfully without fabricating values.
- Dashboard/API display reads challenger rows only from their own artifact/table.
- Railway dry-run and paper deployment record deployed SHA and schema version.

### Anti-pattern checks

- No monkey-patching Prime vectors.
- No reuse of a production model name for a challenger.
- No stale challenger row displayed as current.
- No cross-date fallback.
- No betting/execution bridge or Telegram path.

### Rollback

Disable challenger invocation and dashboard section through its own feature flag/configuration. Production remains live because the challenger is additive and non-gating.

## Phase 6 — Freeze, settle and evaluate feature families

### Objective

Prove whether each family improves forward prediction and price performance without leakage, race-universe changes, or longshot distortion.

### Implementation anchors

- Add `scripts/research/build_rich_context_challenger_corpus.py`.
- Add `scripts/research/evaluate_rich_context_feature_families.py`.
- Freeze every pre-race packet before results are available.
- Join canonical results only after verified settlement.
- Use the exact same eligible race universe for baseline and each ablation; separately report coverage loss.

### Required metrics

- win, top-2, top-3 and top-4 where the settled place contract permits it;
- log loss, Brier score, calibration, rank correlation and top-k recall;
- captured-price win/place ROI, not hindsight prices;
- bootstrap confidence intervals;
- sensitivity with the largest long-priced winners removed;
- performance by course, jurisdiction, code, surface, class, distance, field size, handicap status, price band, and feature-coverage tier;
- identity exclusions, temporal exclusions, unresolved results, and missingness by family.

### Evaluation sequence

1. historical reconstruction is diagnostic only;
2. rolling chronological train/validation windows;
3. untouched forward holdout;
4. daily fresh shadow accumulation;
5. minimum sample and stability thresholds defined before results are inspected;
6. independent rerun from frozen manifests and canonical results.

### Verification

- Dataset hash, code SHA, schema/scorer versions, cutoffs, race universe and exclusions are recorded.
- Leakage audit proves no post-off/result columns are present.
- Baseline and ablations share identical eligible row IDs.
- Results are reproducible from immutable manifests.
- A no-signal/constant-feature control does not show artificial lift.

### Anti-pattern checks

- No promotion from in-sample or reconstructed historical performance.
- No changing thresholds after seeing outcomes.
- No accumulator claims from marginal place rates without joint-probability and price evaluation.
- No reporting ROI without uncertainty and longshot sensitivity.
- No suppressing coverage loss to improve headline metrics.

### Rollback

Research scripts and tables are non-production. Invalid corpora are marked superseded with reason and retained for provenance; they are not rewritten into passing evidence.

## Phase 7 — Governed promotion tribunal

### Objective

Allow a feature family to influence production only after evidence, operational reliability and rollback controls are independently accepted.

### Required promotion packet

- forward-only metrics and confidence intervals;
- calibration and price-performance evidence;
- family coverage and exclusion impact;
- leakage, identity and temporal audits;
- deployed-versus-tested lineage;
- feature semantics and source licences;
- failure modes and monitoring;
- shadow stability across multiple courses/regimes;
- Council decision and Mission Control status;
- exact proposed production delta and rollback commit/configuration.

### Verification

- Independent reviewer reproduces the packet.
- Governed tests prove source, identity and time contracts.
- Canary/shadow comparison is specified before any production change.
- A rollback rehearsal succeeds.

### Anti-pattern checks

- No wholesale “full enrichment” promotion; families are promoted individually.
- No weight change hidden inside data plumbing.
- No gate bypass or manual PASS.
- No promotion because a dashboard looks better.

## Phase 8 — Railway, Supabase, GitHub and operational closure

### Objective

Ensure the feature pipeline is cloud-native, reproducible, observable, and not dependent on the laptop.

### Railway

- Record every active service, command, branch, deployed SHA, schedule, retry policy and output destination.
- Morning sequence: RP capture -> factual FormFav snapshot -> governed Prime -> Rich Context shadow -> persistence/dashboard.
- Evening sequence remains canonical results -> Sigma -> multi-model ingestion -> Mission Control -> Council -> mandated final Mission Control refresh -> learning gates.
- Challenger failure is non-gating for Prime but must create a durable failed/partial terminal record with exact reason.

### Supabase

- Inspect deployed schema, constraints, indexes and RLS before additive migrations.
- Store immutable raw-capture references and append-only challenger manifests.
- Use idempotent keys including race date, canonical race/runner identity, challenger version, feature schema version and freeze ID.
- Preserve original source labels for all legacy API records.

### GitHub

- One focused branch/PR per phase or coherent dependency group.
- No unrelated dashboard/runtime artifacts in commits.
- CI covers source blocking, banned-field recursion, temporal cutoffs, identity, Prime invariance, persistence idempotence, leakage and replay reproducibility.
- Merge SHA must be reconciled to Railway deployed SHA before operational closure.

### Operational verification

- Runbook receives exact morning/EOD checks and recovery behavior.
- Alerts distinguish Prime failure, challenger failure, stale FormFav, missing RP capture, persistence failure and evaluation failure.
- Daily report states race/runner coverage for every family and never says “enriched” without quantified evidence.

### Anti-pattern checks

- No laptop-only canonical artifacts.
- No credentials printed, replaced or committed.
- No mutable “latest” row used as historical truth.
- No code merge claimed as deployment.
- No dashboard presence claimed as model consumption.

## Delivery sequence and dependency gates

| Order | Deliverable | Depends on | Gate to continue |
|---:|---|---|---|
| 1 | Racing API live-path seal | Phase 0 | governed route, source-truth/CI, preflight and fail-closed tests pass |
| 2 | Deployed Supabase introspection and operator-approved immutable schema | 1 | deployed columns/constraints/indexes/RLS recorded; additive migration explicitly approved, applied and verified |
| 3 | Feature/provenance contract and transport | 2 | banned-field, >=80% factual readiness, time and Prime-invariance tests pass |
| 4 | Canonical historical provider | 3 | identity, as-of, coverage and query audits pass |
| 5 | Comment parser | 3 | labelled precision, exclusion and variance tests pass |
| 6 | Frozen challenger training protocol and implementation | 3, 4, 5 | split/model/calibration/hyperparameters predeclared; isolated persistence and Prime invariance pass |
| 7 | Corpus and identical-protocol ablations | 6 | immutable freeze, same-universe and leakage audits pass |
| 8 | Untouched holdout and fresh forward evidence | 7 | predeclared sample/stability thresholds met |
| 9 | Promotion proposal | 8 | independent tribunal approval only |

## Definition of done

“Velo is awake” does **not** mean more fields exist in a JSON file. It means:

- the governed UK/IRE source path cannot silently use Racing API;
- every challenger input has identity, source, time, hash, family and missingness provenance;
- FormFav predictions are mechanically unable to enter Velo’s factual vector;
- historical facts are computed from canonical as-of evidence rather than silent defaults;
- RP comments are parsed before shadow scoring without tipster verdict leakage;
- Prime remains unchanged while a separate challenger produces durable daily evidence;
- each feature family has a same-universe chronological ablation and fresh forward record;
- Railway runs the pipeline independently of the laptop;
- Supabase holds immutable evidence and terminal outcomes;
- GitHub code, Railway deployed SHA and Supabase schema are reconciled;
- any future production change is small, explicit, independently reproducible and reversible.

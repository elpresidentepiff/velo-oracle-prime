# V17 Feature Extractor Wiring Audit V1

## Question
Does `V17FeatureExtractor` currently run in live scoring?

## Answer
No.

## Repo Proof
### Extractor
[C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\services\v17_feature_extractor.py](C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\services\v17_feature_extractor.py)

- can make a live Racing API call to:
  - `GET /horses/{horse_id}/results`
- uses:
  - `RACING_API_USERNAME`
  - `RACING_API_PASSWORD`
  - `RACING_API_BASE_URL`
- has no request limiter

### Live scoring path
[C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\services\velo_prime_service.py](C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\services\velo_prime_service.py)

- `score_race_velo_prime()` imports `DEFAULTS` from the extractor module
- `_build_live_features()` seeds doctrine features from `DEFAULTS`
- I did not find a live `V17FeatureExtractor()` instantiation
- I did not find a live `.extract()` call in the scoring path

### Canonical API entrypoint proof
[C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\main.py](C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\main.py)

- `/api/v1/predict/race` calls `score_race_velo_prime()`
- this is the canonical live path used by the production prediction API

### Non-canonical richer path
[C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\intelligence\chains\prediction_chain.py](C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\intelligence\chains\prediction_chain.py)

- this file does instantiate `V17FeatureExtractor()`
- this file does call `.extract()`
- but it is not the same runtime as `score_race_velo_prime()`
- do not confuse existence of this path with proof that the canonical scorer is using live doctrine/history enrichment

### Secondary fallback proof
[C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\services\model_manager.py](C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix\app\services\model_manager.py)

- `_build_v17_feature_vector()` fills doctrine fields from `DEFAULTS` when those runner fields are absent
- so even the SQPE feature-vector builder preserves the same neutral fallback behavior

## What Happens Today
Live scoring appears to do this:
- build base runner/race features
- fill doctrine fields with neutral defaults
- score SQPE + specialist models + ensemble

So the extractor exists, but the horse-history enrichment path is not active in the canonical live scoring path.

That means the current gap is broader than “historical archive repair.”
It is also a live feature-contract truth gap in the production scorer.

## Why This Matters
If the extractor were wired naively, it could issue one horse-history request per runner. That would be unsafe under the `3 req/sec` constraint and would create a lot of latency and request volume.

## Safe Wiring Plan
1. Do not let the extractor create ad-hoc live sessions.
2. Inject the canonical throttled wrapper.
3. Prefetch horse results through a queue before runner scoring begins.
4. Cache by `horse_id`.
5. Record misses and fetch failures in `api_coverage_audit`.
6. Fall back to defaults only when the miss is explicit and audited.

## Canonical Scorer Repair Plan

### Objective
Repair the canonical live scorer so `score_race_velo_prime()` can consume real doctrine/history enrichment through the governed Racing API control plane, without silently mutating production behavior.

### Constraints
- default behavior must remain unchanged at first
- no unthrottled per-runner API fanout
- no hidden fallback that looks like live enrichment when it is not
- no scoring promotion until shadow evidence proves the path is safe

### Required design
1. Add a scorer-side feature flag for doctrine/history enrichment.
2. Keep the default mode `OFF` until shadow validation passes.
3. Inject the canonical throttled `RacingAPIClient` instead of letting the extractor own sessions.
4. Prefetch by race, not ad-hoc by runner, using a bounded queue and shared cache.
5. Write explicit per-runner provenance fields:
   - `doctrine_source = live_enriched | defaulted | unavailable`
   - `doctrine_fetch_attempted = true/false`
   - `doctrine_fetch_block_reason`
6. Emit coverage/audit events for:
   - endpoint blocked
   - timeout
   - cache hit
   - cache miss
   - fallback to defaults

### Rollout stages
#### Stage 0 — Truth locked
- completed by this audit
- production truth says the canonical scorer defaults doctrine/history features today

#### Stage 1 — Shadow enrichment only
- run enrichment behind flag
- do not alter live probability or ranking
- attach audit/provenance only
- prove request volume, latency, and coverage

#### Stage 2 — Scorer-side shadow compare
- compute enriched doctrine fields alongside default doctrine fields
- compare:
  - field coverage
  - probability deltas
  - ranking deltas
  - endpoint hit rate
- still no live mutation

#### Stage 3 — Controlled promotion review
- only after shadow evidence proves:
  - limiter safety
  - acceptable latency
  - adequate coverage
  - no hidden leakage
  - explicit governance approval

### First real repair target
The first repair target is not HFS training.
The first repair target is:

- the canonical `score_race_velo_prime()` feature contract
- plus explicit truth around when doctrine/history fields are defaulted

Do not discuss archive parity or Playbook G readiness as if the live scorer contract is already whole.

## Conclusion
`V17FeatureExtractor` is present, but it is not yet a safe or active part of the canonical live scoring path.

Verified correction:

- canonical live scoring currently defaults doctrine/history features unless another upstream path pre-fills them
- the richer extractor-backed chain exists, but is non-canonical for current live truth

The right next move is still not to wire it in blindly. The right move is:

1. keep this truth explicit in control-plane docs
2. repair the canonical live feature contract behind a governed, throttled path
3. only then discuss historical/HFS parity and training readiness

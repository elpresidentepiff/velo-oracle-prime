# Current VÉLØ — Full Context Upgrade Plan

**Status:** authorised research-and-shadow upgrade; no live Prime-weight change in this plan.
**Date:** 2026-11-22
**Objective:** make every permitted, time-safe factual source visible, attributable and testable by VÉLØ, then prove whether an enriched challenger beats the frozen Prime baseline on future races.

## Non-negotiable boundaries

1. Preserve the current Prime profile (`SQPE_IMPROVEMENT_MDS_V1`) as the frozen benchmark until an explicit promotion gate is passed.
2. Never use FormFav/provider predictions, tips, or provider confidence as a VÉLØ feature. Factual fields only.
3. Never train or score from a fact whose source time, race/runner identity, schema version, or provenance is unknown.
4. Persist enriched scores separately from the frozen Prime packet. No packet mutation and no retroactive pre-off evidence.
5. A dashboard label must distinguish `CONSUMED`, `SHADOW_CONSUMED`, `CAPTURED_ONLY`, `EVIDENCE_ONLY`, and `MISSING`.
6. All comparisons use the identical race/runner universe, explicit decision cutoff, chronological split and certified settlement contract.
7. A lane can change Prime only after the existing promotion policy and an operator decision; no automatic merge of probabilities.

## The implementation sequence

### Phase 0 — Truth registry and coverage contract

Create one versioned registry for every current source and model family:

| Required field | Meaning |
|---|---|
| `family` | e.g. RP Spotlight, FormFav pace, passport, market snapshot |
| `source` / `schema_version` | data origin and parser contract |
| `available_before_cutoff` | whether the factual evidence was genuinely available pre-off |
| `coverage` / `identity_status` | known usable runners/races and exact identity quality |
| `usage_state` | consumed by Prime, challenger, captured-only, evidence-only, missing |
| `model_versions` | score-producing consumers, if any |
| `training_eligible` | false unless all provenance requirements are met |

**Verification:** one date-level manifest must reconcile to the frozen packet, source snapshots and displayed dashboard counts. Missing is a valid outcome, never silently imputed.

### Phase 1 — Full factual packet, not full live blending

Extend the existing Rich Context packet only through its existing source-specific adapters. It must include, where available:

- Racing Post: factual card, Spotlight/comment source spans, form and race context;
- FormFav Premium: raw factual runner, pace, class, bias, conditions, connections and market observations; never provider predictions;
- VÉLØ history: prior career/form records;
- passports: trainer/jockey/course/distance and deployment context;
- market: named point-in-time snapshots, not a later SP presented as pre-off.

For every field, preserve raw reference, capture UTC, availability classification and extractor version.

**Verification:** packet-contract tests prove no FormFav prediction key can enter a feature vector; packet completeness/freshness and identity rates are emitted per source family.

### Phase 2 — Separate shadow lanes and factual ablations

Build only separately persisted shadow scores:

1. baseline-only;
2. baseline + canonical history;
3. + RP factual narrative extraction;
4. + FormFav factual runner/class/pace/bias blocks;
5. + passports/connections;
6. + time-safe market state;
7. full factual challenger.

This is an ablation ladder, not a model soup. Each lane has an immutable feature manifest and its own model/version identifier.

**Verification:** all lanes score the same eligible runner universe, have no live Prime influence, and write only to append-only challenger tables.

### Phase 3 — Honest evaluation and market residual research

Use chronological, frozen windows and compare:

- Fundamental / market-blind VÉLØ;
- market-only baseline at the identical cutoff;
- existing Prime;
- each factual challenger;
- a residual/disagreement model only after point-in-time market data is complete.

Required reporting: coverage, identity failures, log loss, Brier score, calibration, top-1/top-3, result-position distribution, settled-price ROI with price-source labels, confidence intervals and forward-only sample count.

**Verification:** same-race comparison tests; no SP-derived feature in a decision-time experiment unless capture timestamp proves availability.

### Phase 4 — Truthful dashboard and operator desk

Expose on the dashboard for every race:

- Prime baseline pick and probability;
- each shadow challenger pick/probability/rank;
- exact score change versus Prime;
- family coverage and missing reasons;
- factual evidence cards with source/time;
- explicit `SHADOW — NOT USED BY PRIME` state;
- later, certified performance by model/version and exact selected universe.

**Verification:** API and browser-level tests assert that captured-only information cannot be presented as score-consuming, and dashboard totals reconcile to Supabase source tables.

### Phase 5 — Promotion review, never an automatic merge

A factual family or full challenger can be proposed for production only when it has:

- reproducible dataset and transform manifests;
- >=80% identity coverage on its intended universe;
- chronological holdout improvement on the same race universe;
- at least 500 forward races under the current promotion protocol;
- calibration that does not degrade;
- uncertainty and longshot sensitivity analysis;
- independent operator review and an immediate rollback path.

## Immediate first experiment

The first valid experiment is **not** to combine all named model probabilities. It is to produce a `FULL_FACTUAL_CONTEXT_SHADOW_V1` packet/scorecard that truthfully records which family was present for each runner. It starts with observation and coverage, then moves to fitting only when enough forward packets exist.

This directly answers: “What did Prime say, what did fully enriched VÉLØ say, and exactly which new facts caused the difference?”

## Explicitly prohibited shortcuts

- averaging all named model scores;
- using FormFav predictions as a feature;
- backfilling post-off information as though it were pre-off;
- training across sidecars with unresolved IDs/provenance;
- displaying a score without its usage state;
- letting a short sequence of winners or accumulator hindsight promote a lane;
- changing live Prime weights before the challenger clears the documented gate.

# SYSTEM_MAP.md — VÉLØ Oracle Prime Architecture

High-level map of how data, scoring, safety gates, and review layers connect.
Component names and file paths below are verified against the current repo tree
(`main` @ this branch's parent commit) — see `docs/current/ONE_TRUTH.md` for the
authoritative live/shadow status of each.

## System flow

```
Race data (Racing Post HTML capture)
        │  scripts/ops/racing_post_account_collector.py
        ▼
Racecard ingestion + validation
        │  parse_racing_post_racecard_capture.py → validate_rp_injection.py
        ▼
RPDC build (horse-career memory)          Horse Passport (career features)
        │  build_rpdc_daily.py            │  new_build_horse_passports.py,
        │                                 │  new_build_passport_features.py
        ▼                                 ▼
Scoring / signal layer
        │  run_prime_today.py → src/intelligence/velo_prime_ensemble.py
        │  (live: SQPE_IMPROVEMENT_MDS_V1 profile)
        │  shadow lanes: New Build two-lane, No-RPR, Champion Intent Shadow
        ▼
VP Gatekeeper (engagement-intensity gate, NOT a scoring change)
        │  docs/current/VP_GATEKEEPER_PROMOTION_V1.md
        │  build_vp_opportunity_panel.py → GREEN/AMBER/RED
        ▼
Persistence
        │  Supabase velo_verdicts (system of record)
        │  + canonical_model_scorecards / canonical_learning_events
        │    (build_canonical_model_scorecard.py, build_canonical_learning_events.py)
        ▼
Passport / Sigma / VFU review
        │  run_results_sigma.py (results reconciliation, LOCKED Telegram format)
        │  VFU loop: autopsy → Pattern Prosecutor → Sigma Master Ledger
        ▼
Pattern Tribunal
        │  Sigma Pattern Tribunal (VFU-12 lineage) — prosecutes pattern candidates,
        │  produces human review queue, promotes to dry-run watchlist only
        ▼
Dry-run doctrine decision (operator gate)
        │  no live doctrine/model promoted without explicit operator sign-off
        ▼
docs/artifacts updated
        │  data/reports/*, dashboard JSON, docs/current/ONE_TRUTH.md sign-off log
```

## Component index

| Component | Role | Key files |
|---|---|---|
| **VP Gatekeeper** | Report-only engagement-intensity classifier (GREEN/AMBER/RED). Does not change scoring, weights, staking, or Supabase/Telegram output. | `docs/current/VP_GATEKEEPER_PROMOTION_V1.md`, `scripts/ops/build_vp_opportunity_panel.py` |
| **Horse Passport** | Career-level feature bank per horse (course/distance/trainer-jockey history, intent features). Feeds New Build lanes and Champion Intent Shadow. | `scripts/ops/new_build_horse_passports.py`, `new_build_passport_features.py`, `new_build_horse_passport_spine.py`, `docs/archive/HORSE_PASSPORT_FORENSIC_EXTENSION_V1.md` |
| **RPDC** | Horse-career memory + deployment context, distinct from Passport. PDF intelligence must never overwrite RPDC fields (hard law). | `scripts/ops/build_rpdc_daily.py`, `runner_release_candidates` (Supabase) |
| **Sigma Master Ledger** | Era-separated reconciliation dataset (6,019 rows per VFU-11), quarantines unsafe older data, feeds Pattern Tribunal. | VFU-11 (`docs/current/VFU_INDEX.md`), `scripts/ops/run_results_sigma.py` |
| **Pattern Tribunal** | Prosecutes recurring failure/success patterns from the Sigma ledger; promotes candidates only to a dry-run watchlist pending operator review. | VFU-05 (Pattern Prosecutor), VFU-12 (Sigma Pattern Tribunal) — `data/reports/vfu_pattern_prosecutor_*` |
| **VFU loop** | Doctrine → autopsy → pattern detection → identity integrity → time-safety review, VFU-01 through VFU-21. | `docs/current/VFU_INDEX.md`, `docs/current/VFU_FAILURE_TAXONOMY_V1.md`, `docs/current/VFU_RACE_AUTOPSY_SCHEMA_V1.md` |
| **Governed safety runner** | Chains Worktree Safety → Task Contract preflight → Side-Effect Sentinel → command execution → Task Contract audit. Mandatory orchestration layer per `ONE_TRUTH.md` step 1. | `scripts/ops/governed_task_runner.py`, `docs/current/GOVERNED_TASK_RUNNER.md` |
| **Side-effect sentinel** | Runtime safety gate blocking commands that risk Supabase writes, Telegram sends, model promotion, or live-scoring mutation. | `scripts/ops/side_effect_sentinel.py`, `docs/current/SIDE_EFFECT_SENTINEL.md` |
| **Task contracts** | Machine-readable JSON scope boundaries (`allowed_paths`, `forbidden_paths`, `forbidden_keywords`, `classification_required`) enforced per mission. | `ops/task_contracts/*.json`, `scripts/ops/task_contract_runner.py`, `docs/current/TASK_CONTRACT_RUNNER.md` |
| **Reports** | Human/machine-readable mission outputs (per-day, per-VFU, per-model). | `data/reports/*.{md,csv,json}` — see `docs/current/ARTIFACT_REGISTRY.md` |
| **Tests** | Regression/safety proof, including the Little Lady Rock (race 922118) hash-guarded regression anchor. | `tests/*.py` (144 test files as of this writing) |
| **Artifacts** | Durable evidence files: verdicts JSON, sigma results, canonical scorecards/events, dashboard state. | `docs/current/ARTIFACT_REGISTRY.md` |

## Dashboard consumer layer

`scripts/ops/new_build_dashboard_server.py` (FastAPI, read-only, no Supabase writes)
serves the operator-facing view. Endpoints as of this writing:

`/`, `/dashboard`, `/sidecar_stack_latest.json`, `/api/governed-card`,
`/api/dashboard/truth-summary`, `/api/dashboard-truth`, `/api/doctrine-scorecard`,
`/api/old-velo-verdicts`, `/api/canonical-scorecard`, `/api/canonical-learning-events`,
`/api/canonical-race-truth`, `/api/model-suggestions`, `/api/model-suggestions-race`,
`/api/health`.

Per the CANONICAL MODEL TRUTH SPINE law (`ONE_TRUTH.md`), the dashboard must read
`canonical_model_scorecards` / `canonical_learning_events` for model/result/learning
truth, and must not invent model truth from ad-hoc local JSON. Any panel that is
runtime/local/non-canonical (e.g. the Model Suggestions summary panel, Champion
Intent Shadow lane) must be explicitly labelled as such — see
`docs/current/MODEL_RESULT_REPORTING_LAW.md`.

## Live vs shadow at a glance

See `docs/current/LIVE_VS_DRY_RUN.md` for the full status vocabulary, and
`docs/current/ONE_TRUTH.md` §"What is LIVE" / §"What is SHADOW" for the current
authoritative list of which components are in which state.

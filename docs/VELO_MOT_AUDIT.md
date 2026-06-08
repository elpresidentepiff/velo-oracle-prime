# VELO Oracle Prime MOT Audit

Audit date: 2026-06-07  
Audited clean commit: `14ea7848827679a6687ebb0b70f155d07da85ad2`  
Audit branch: `codex/prime-mot-20260607`

## Executive Summary

**Verdict: NOT AUDIT-READY.**

Prime can produce race verdicts, Sigma results, and learning artifacts, but its production
service is unavailable and its operational truth chain was broken. On 2026-06-07,
Mission Control reported both learning and promotion gates `OPEN` while the canonical
daily run watchdog reported `VERDICTS_WITHOUT_PIPELINE_TRUTH`.

This audit repaired the two code defects that caused that false-green state:

1. `scripts/ops/run_prime_today.py::_open_pipeline_run` now actually inserts the
   `pipeline_runs` truth row. The insert had been commented out.
2. `scripts/ops/update_mission_control.py::build_mission_control` now blocks learning
   and promotion unless daily run truth is `AUTOMATED_RUN_OK`.

It also removed hardcoded API keys from the orphaned prediction router and repaired an
undefined `settings` reference that was failing CI lint.

The live deployment remains broken and unverified after repair because Railway returns
HTTP `502` and Railway logs are inaccessible without authentication.

## Current System Map

```text
RP PDFs / Racing API
  -> collectors and RP parsers
  -> current-card / merged-card builders
  -> scripts/ops/run_prime_today.py
  -> app/services/velo_prime_service.py
  -> local verdict JSON + Supabase velo_verdicts
  -> results parsers
  -> scripts/ops/run_results_sigma.py
  -> Sigma artifacts / sigma_audits
  -> nightly learning and shadow evidence
  -> Mission Control / Council gates

FastAPI app.main
  -> Railway Nixpacks start command
  -> /health and /api/v1/build-fingerprint
```

## Real End-to-End Evidence

The 2026-06-07 local artifacts prove a partial flow:

| Stage | Evidence | Status |
|---|---|---|
| Scoring output | `data/velo_prime_verdicts_2026_06_07.json`, 30 verdicts | DEGRADED |
| Result reconciliation | `data/sigma_results/sigma_results_2026_06_07.json`, 28 evaluated, 2 true non-runners | PASS |
| Closure | Sigma unresolved rows = 0 | PASS |
| Learning sidecar | `data/nightly_eod_learning_status_2026_06_07.json`, 30 updates, duplicates blocked | PASS |
| Pipeline run truth | `data/velo_daily_run_truth_2026_06_07.md` says `VERDICTS_WITHOUT_PIPELINE_TRUTH` | FAIL |
| Mission Control | Existing June 7 artifact opened both gates despite failed run truth | FAIL |
| Production API | `/health` and `/api/v1/build-fingerprint` return HTTP 502 | FAIL |

Verdicts existing does **not** prove an automated production run. The pipeline-run
record, trigger source, deployed commit, cron execution, and service health are absent
or failed.

## Subsystem Status

| Subsystem | Status | Evidence |
|---|---|---|
| Repository integrity | FAIL | Original worktree has 1,105 dirty paths; audit used a separate clean worktree |
| Dependency reproducibility | DEGRADED | Production requirements include broad ranges; clean import warns `feast` missing |
| Documented entrypoints | DEGRADED | All 21 documented scripts return exit 0 for `--help`; real external execution is unproven |
| Ingestion | UNPROVEN | No clean-checkout end-to-end run against production sources/secrets |
| Normalization | DEGRADED | Modules and entrypoints exist; full flow not proven in this audit |
| Feature generation | FAIL | Full test collection breaks on stale `compute_market_intelligence` import |
| Model plane | FAIL | Clean checkout lacks three model artifacts asserted by `tests/test_phase4_full.py` |
| Daily scoring | DEGRADED | June 7 verdicts exist, but their pipeline truth is absent |
| Persistence | DEGRADED | Commented-out pipeline-run insert repaired; live post-deploy proof still UNPROVEN |
| Sigma / closure | DEGRADED | June 7 local Sigma is complete, but historical continuity and production trigger remain unproven |
| Learning loop | DEGRADED | June 7 sidecar is idempotent; false-green admission gate repaired |
| Mission Control / Council | DEGRADED | False-green fixed in code; council manual verification remains incomplete |
| API | FAIL | Production endpoints return HTTP 502 |
| Deployment / cron | FAIL | Repeated `smoke-prod` failures; Railway logs unavailable |
| CI / tests | FAIL | CI fails; full pytest stops during collection; app lint has 49 errors |
| Observability | DEGRADED | Watchdog caught missing truth, but Mission Control ignored it before repair |
| GitNexus architecture evidence | UNPROVEN | Graph indexes commit `619f25a`, not audited commit; refresh command failed |
| Oracle of Odds challenger | DEGRADED | 29 tests pass and smoke pipeline passes, but only sample-scale training is proven |

## Ranked Failure Register

### P0-01: Production service does not respond

- Symptom: Railway `/health` and build fingerprint return HTTP 502.
- Evidence: direct `curl`; repeated GitHub `smoke-prod` failures.
- Impact: live API and health truth are unavailable.
- Fix: inspect Railway deployment logs, repair startup, redeploy, require successful
  health and fingerprint checks.
- Status: **BLOCKED / UNPROVEN** because `railway logs` requires authentication.
- Discovery: runtime test + GitHub Actions.

### P0-02: Pipeline truth row was never inserted

- Root cause: the database insert in `_open_pipeline_run` was commented out while the
  function still returned a generated run ID.
- Impact: verdicts could exist without a durable automated-run record.
- Fix applied: restored `db.table("pipeline_runs").insert(row).execute()`.
- Proof: `tests/test_pipeline_run_truth.py::test_open_pipeline_run_persists_truth_row`
  now passes.
- Discovery: runtime test + direct inspection.

### P0-03: Mission Control could open learning and promotion on failed run truth

- Symptom: June 7 Mission Control said `OPEN`; watchdog said
  `VERDICTS_WITHOUT_PIPELINE_TRUTH`.
- Root cause: Mission Control did not consume daily run truth.
- Impact: unproven data could enter learning or promotion decisions.
- Fix applied: both gates block unless run truth equals `AUTOMATED_RUN_OK`.
- Proof: two new tests pass; synthetic missing-truth run returns both gates `BLOCKED`.
- Discovery: artifact comparison + direct inspection + tests.

### P1-01: Clean-checkout test suite cannot collect

- Symptom: `pytest -q` stops importing `compute_market_intelligence`.
- Root cause: `tests/test_hfs_feature_builder_v1.py` targets a removed service contract.
- Impact: repository-wide regressions cannot be measured.
- Exact remediation: reconcile the HFS test and service contract, then require full
  pytest in CI.
- Discovery: runtime test.

### P1-02: Claimed model and 1.7M dataset artifacts are absent

- Symptom: five Phase 4 tests fail in a clean checkout.
- Missing: SQPE v14, Longshot v6, Overlay v5, and
  `storage/velo-datasets/racing_full_1_7m.csv`.
- Impact: historical claims and model reproducibility are not independently provable.
- Exact remediation: publish immutable manifests/checksums and retrieval/build steps;
  do not claim 1.7M until proven.
- Discovery: runtime test + direct inspection.

### P1-03: CI does not prove Prime

- Symptom: CI test job only runs `workers/ingestion_spine`; current CI is failing lint.
- Impact: green tests would not prove the production scoring/Sigma path.
- Exact remediation: add Prime truth-gate tests, import smoke, full-suite collection,
  and deployment smoke as required checks.
- Discovery: workflow inspection + GitHub Actions.

### P1-04: Prediction router carried hardcoded credentials

- Scope: router is not mounted by `app.main`, so live exploitability is unproven.
- Impact: future mounting would activate known credentials.
- Fix applied: fail closed on configured `API_KEY` using constant-time comparison.
- Discovery: call-chain inspection + direct inspection.

### P2-01: GitNexus graph is stale

- Evidence: `.gitnexus/meta.json` indexes `619f25a`; audited clean commit is `14ea784`.
- Impact: disconnected/orphan claims cannot be trusted from the graph.
- Remediation: repair GitNexus CLI, refresh graph, and rerun impact/disconnection checks.
- Discovery: GitNexus metadata + failed refresh command.

### P2-02: Duplicate deployment truth

- Evidence: `railway.toml` selects Nixpacks and documents a server-side Railway cron,
  while GitHub Actions also schedules scoring and Docker deployment material exists.
- Impact: ownership and startup behavior can drift.
- Remediation: declare one production start path and one scheduler of record.
- Discovery: configuration inspection.

## Fixes Applied

- Restored durable `pipeline_runs` insertion.
- Added Mission Control run-truth gate and regression tests.
- Removed hardcoded prediction API credentials.
- Fixed missing `settings` import used by CORS configuration.
- Updated the legacy API-key test to use an environment-configured key.

## Remaining Risks

1. Production remains down.
2. The full clean-checkout suite remains broken.
3. Railway logs, cron truth, and deployed commit are UNPROVEN.
4. Supabase post-repair persistence is UNPROVEN until deployed and queried.
5. GitNexus findings are stale until the graph is refreshed.
6. Original Prime worktree cleanliness is an audit blocker.
7. Oracle of Odds is not yet trained on a production-sized settled-race corpus.

## Evidence Appendix

| Command | Result |
|---|---|
| `git rev-parse HEAD` | `14ea7848827679a6687ebb0b70f155d07da85ad2` |
| Original `git status --porcelain` count | 1,105 dirty paths |
| `curl .../health` | HTTP 502 |
| `curl .../api/v1/build-fingerprint` | HTTP 502 |
| `gh run list --limit 8` | latest `smoke-prod` FAIL, latest `ci` FAIL, `gx-validate` PASS |
| `python -c "import app.main"` | PASS with missing-`feast` degradation warning |
| `python -m pytest -q` | collection ERROR: removed `compute_market_intelligence` |
| Focused truth/security pytest | 22 passed |
| Legacy Phase 4 pytest | 5 failures: missing models/dataset |
| `python -m ruff check app --statistics` | 49 errors |
| Synthetic Mission Control missing truth | learning BLOCKED, promotion BLOCKED |
| Oracle of Odds `pytest -q` | 29 passed |
| Oracle of Odds smoke | PASS, 1 race, 2 verdicts, 2 closed |


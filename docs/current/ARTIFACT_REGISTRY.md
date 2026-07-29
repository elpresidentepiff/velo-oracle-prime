# ARTIFACT_REGISTRY.md — Output Index

Makes VÉLØ's outputs discoverable. Most artifact directories under `data/` are
gitignored runtime state (regenerated locally, not committed) except where a
specific file has been force-added as evidence (see `CSV force-add precedent`
below). Counts below are a snapshot of this worktree at doc-spine creation time —
re-`ls` the directory for current counts rather than trusting this file's numbers
as live.

| Artifact path | Created by | Purpose | Status | Safe for promotion | Notes |
|---|---|---|---|---|---|
| `data/reports/*.md` / `*.csv` / `*.json` (352/91/356 files at snapshot time) | Various `scripts/ops/build_*.py` and `scripts/audit/*.py` | Per-mission evidence reports (VFU autopsies, model comparisons, Sigma summaries, operator packets) | Mixed — mostly `DRY_RUN`/`REPORT_ONLY` | No — reports are evidence, not promotion-grade proof by themselves | Gitignored by default; specific CSVs force-added when they're the canonical evidence artifact for a PR (e.g. `canonical_model_scorecard_2026_07_05.csv`, `canonical_model_scorecard_2026_07_06_runtime.csv`) |
| `data/sigma_results/sigma_results_{date}.{json,md}` | `scripts/ops/run_results_sigma.py` | Nightly results reconciliation, LOCKED Telegram-format report | Result-reconciliation truth (per `ONE_TRUTH.md`) | Only as reconciliation evidence, not model-rank truth on its own | Never regenerate with a modified format; never use `--source api` |
| `data/mission_control/{date}_mission_control.json` + `latest.json` | `scripts/ops/update_mission_control.py` | Daily gate/source-truth summary | Operational truth pointer | N/A | KNOWN DEFECT: `source_truth` field defaults CLEAN — cross-check the observability packet directly, don't trust this file alone (`ONE_TRUTH.md` Stage 14) |
| `data/velo_run_observability_{date}_{hash}.json` | `run_prime_today.py` | Per-run observability packet (feature health, source truth) | Authoritative source-truth input | N/A | Mission Control derives `source_truth` from this file only — missing/malformed = `UNKNOWN` |
| `data/velo_prime_verdicts_{date}.json` | `run_prime_today.py` (live) or `build_report_only_legacy_verdicts_*.py` (report-only variant) | Local backup of live/report-only verdicts | LIVE (former) / REPORT_ONLY (latter) | Live file only, if persisted via the real pipeline | Report-only variant must be labelled distinctly — see `docs/current/MODEL_RESULT_REPORTING_LAW.md` law 8 |
| `data/training/sigma_local_corpus_latest.parquet`, `sigma_2k_training_dataset_latest.parquet` | `scripts/audit/build_sigma_local_corpus.py` and related | Training/analysis corpora | Evidence corpus | Only via explicit retrain + operator gate | Re-run after any new sigma dates to extend |
| `data/current/*_latest.json` (e.g. `worktree_safety_latest.json`, `task_contract_latest.json`, `side_effect_sentinel_latest.json`, `governed_task_latest.json`) | Governed Task Runner chain | Machine-readable safety-gate state | Procedural safety record | N/A | Empty/absent in a fresh worktree until the governed runner chain has actually executed here |
| `data/model_comparison_ledger.csv` | `scripts/ops/run_multimodel_sigma.py` | Append-only Old VELO / No-RPR / New Build comparison ledger | Evidence | No | Append-only — never rewritten |
| `data/reports/vcp_03_burn_in_log.md` | `scripts/ops/build_vcp03_burn_in_log.py` | VCP-03 Ten-Day Coherence Burn-In daily log | DRY_RUN | No — gates VCP-04 | Check current day count before assuming burn-in complete |
| `ops/task_contracts/*.json` | Manual, per mission | Machine-readable scope contract for a mission | Governance artifact | N/A | `DOCS-01.json` is this mission's own contract |
| `tests/*.py` (144 files at snapshot time) | Various missions | Regression/safety proof | Test suite | N/A | Includes the Little Lady Rock (race 922118, 2026-07-05) SHA256 hash-guarded regression anchor |
| `app/static/dashboard/index.html` + dashboard JSON under `app/static/dashboard/` | `publish_daily_predictions_to_dashboard.py`, manual dashboard edits | Operator-facing dashboard | LIVE display (of dry-run/report-only/shadow data) | N/A | Must read canonical endpoints per CANONICAL MODEL TRUTH SPINE law; non-canonical panels must be explicitly labelled |
| `docs/current/*.md` | This mission (DOCS-01) and prior governance missions | Documentation spine | Governance | N/A | `ONE_TRUTH.md` remains the single winning truth file if any conflict arises |

## CSV force-add precedent

`data/**/*.csv` is gitignored by default. Specific canonical report CSVs are
force-committed (`git add -f`) only when they are meaningful evidence artifacts
tied to a merged PR — e.g. `canonical_model_scorecard_2026_07_05.csv` and its
2026-07-06 runtime counterpart. Follow this precedent rather than force-adding
every CSV a mission happens to produce.

## How to extend this registry

When a mission produces a new class of durable artifact (not a one-off report),
add a row here in the same PR that introduces it. Do not let this registry drift
silently out of date — the Archivist role in `docs/current/AGENTS.md` owns this.

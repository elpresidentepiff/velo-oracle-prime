# Evo²-inspired VÉLØ Challenger Lab — Phase 1

Issue: #167. Status: research-only; no promotion or production integration.

## Confirmed architecture (18 October 2026)
- Production probabilities: `src/intelligence/velo_prime_ensemble.py` (includes G shadow-mode logic).
- Sigma orchestration: `app/pipelines/sigma_runner.py` invokes `scripts/ops/run_results_sigma.py` and records a lane ledger.
- Results reconciliation: `scripts/ops/run_results_sigma.py` processes verdicts, API outcomes, Sigma classification and persistence.
- CPU shadow gate: `scripts/build_cpu_shadow_gate_v2.py`; clean post-fix cohort begins 2026-05-21; requires >=300 clean runners, no flatlines/identity failures or contaminated runs, and explicit operator decision.
- Historical source references in README to root-level `run_results_sigma.py` and `build_shadow_model_forward_gate.py` must not be used as implementation paths.

## Minimum experimental contract
**Proposer:** emits a structured, immutable candidate record: candidate ID, parent baseline SHA, hypothesis, evidence snapshot IDs, allowed configuration delta, parameter-search budget, and expected failure modes. No live deployment authority.

**Evaluator:** independent process loads frozen prediction snapshots and as-of outcomes. Split by race date before feature selection, tuning or calibration; prohibit same race/runner in both training and holdout. Require timestamped pre-race feature/price provenance; skip missing/invalid events rather than filling from post-race values.

**Reflector:** reads ONLY completed evaluation records and generates typed feedback: failure category, sample sizes, per-cohort metrics, confidence intervals, suspected leakage, and whether candidate should be rejected. It cannot alter evidence or modify production probabilities.

**Promotion:** preserve the existing CPU Gate V2's >=300-clean-runner threshold, contamination/identity/flatline exclusions, and manual decision. This is necessary but not sufficient: candidate must also beat the pre-registered baseline out of sample with robust cohort calibration and no material degradation.

## Metrics
Use proper scoring rules (Brier + log loss, with clipping), reliability diagrams/calibration error, win/place segmentation, race-level grouping, bootstrap confidence intervals grouped by race/date, coverage, odds timestamp freshness, simulated return after declared fees/slippage and cost per evaluation. Report each metric separately; never optimise a single P/L outcome.

## Safety boundaries
- Offline, read-only, deterministic by default; no scheduled calls, hidden API spend or production writes.
- Do not import `scripts/ops/run_results_sigma.py` in the experiment package if import-time credentials or external effects are possible.
- Do not read training truth into the Proposer; pre-register hypotheses before evaluation; use fresh forward-time holdouts for final decisions.
- No model-weight mutation, external trading, live wagers, automatic threshold changes or auto-promotion.
- Strict budget/timeouts; immutable JSON artifacts with SHA256 hashes and provenance; redact tokens.
- Validate license/reproducibility of https://arxiv.org/abs/2610.13025 before incorporating third-party code.

## Work packages
1. Inventory source schemas, run IDs, prediction timestamps, result schemas, existing CI/tests and the complete Gate V2 logic.
2. Add a pure-Python/NumPy-free offline experiment contract with typed candidate/observation/result records and deterministic Brier/log-loss computations.
3. Write fixture tests for valid input, duplicate runners, incomplete outcomes, timestamp leakage, probability bounds and insufficient clean samples.
4. Add a CLI to compare frozen candidate vs baseline and emit machine-readable review artifacts. Keep it disconnected from deployment code.
5. Integrate as OPTIONAL shadow-only experiment; create PR with test output and explicit rollback, then request human review.

## Exit criteria
A reviewed PR demonstrates replayable metrics on controlled fixtures, detects intentionally contaminated data, and cannot affect deployed probabilities by default. Evidence of increased racing prediction accuracy must be established separately on held-out forward data; nothing in this document claims such a gain.

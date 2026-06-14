# VELO MOT Runbook

Run this before releases, audits, or investment reviews.

## 1. Establish the Audited Commit

```bash
git status --short
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
```

Audit only a clean worktree. Record every exception.

## 2. Prove Clean-Checkout Runtime

```bash
python -m pip install -r requirements_production.txt
python -c "import app.main; print('import PASS')"
python -m pytest -q --tb=short
python -m ruff check app scripts/ops
```

Any collection error is a FAIL, not a skipped test.

## 3. Prove Truth Gates

```bash
python -m pytest \
  tests/test_pipeline_run_truth.py \
  tests/test_mission_control_pipeline_truth_gate.py \
  tests/test_p0_security.py -q
```

Required:

- opening a scoring run persists a `pipeline_runs` row;
- missing or non-automated run truth blocks learning and promotion;
- authentication fails closed.

## 4. Prove Production

```bash
curl -f https://velo-oracle-production.up.railway.app/health
curl -f https://velo-oracle-production.up.railway.app/api/v1/build-fingerprint
gh run list --limit 10
railway logs
```

Record deployed commit, trigger source, start/finish times, races/runners processed,
and the matching Supabase `pipeline_runs` row. If logs or secrets are unavailable,
mark the result `UNPROVEN`.

## 5. Prove Daily Closure

For the target date, require:

- verdict count reconciles to expected races;
- Sigma coverage explains every verdict as evaluated, non-runner, or explicit failure;
- unresolved count is zero or explained;
- learning is idempotent;
- Mission Control consumes the same daily run truth;
- no promotion gate opens on missing/failed truth.

## 6. Refresh Architecture Evidence

Refresh GitNexus after the audited commit is checked out. Compare its entrypoints,
orphans, and impact paths with direct `rg` inspection. GitNexus is not a runtime
dependency.

## Release Gate

Release only when:

1. production health and fingerprint pass;
2. full pytest collects and passes;
3. CI passes required Prime tests;
4. the daily pipeline truth row exists and matches artifacts;
5. Sigma and learning close without unexplained rows;
6. Mission Control and Council do not contradict canonical truth.


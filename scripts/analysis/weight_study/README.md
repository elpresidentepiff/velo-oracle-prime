# Weight study (2026-09-13)

Read-only. Pulls live per-runner components from Supabase `velo_verdicts.full_analysis.predictions`,
joins results, keeps only verdicts written before the off, and tests alternative blends of the
live components with rolling out-of-sample months. Report: `docs/research/WEIGHT_STUDY_2026_09_13.md`.

```bash
D=data/research/weight_study; mkdir -p $D
OUT=$D/runner_components.parquet PYTHONPATH=. venv/bin/python scripts/analysis/weight_study/pull_runner_components.py
SPD=$D PYTHONPATH=. venv/bin/python scripts/analysis/weight_study/pull_results.py
SPD=$D venv/bin/python scripts/analysis/weight_study/build_study.py      # needs data/results* locally for May-Jul fallback joins
venv/bin/python scripts/analysis/weight_study/grid.py $D                 # 1,771 blends x 4 rolling test months
```
`sim.py` reproduces the live ranking (98.4% top-pick agreement overall, 100% Jun-Sep).

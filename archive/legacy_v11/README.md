# archive/legacy_v11 — Archived 2026-03-22

These files were part of the v11 VÉLØ signal engine (NaiveBayes, KMeans clustering,
game theory scoring). They have been confirmed dead and moved here.

## Files

| File | Original path | Reason archived |
|---|---|---|
| `v11_signal_engines.py` | `app/ml/v11_signal_engines.py` | No live importers. NaiveBayes/KMeans replaced by SQPE v17 + specialist models. |
| `stability_clusters.py` | `app/ml/stability_clusters.py` | One guarded import in `top4_ranker.py` (condition never fires — `stability_profile` key not written by current pipeline). Removed 2026-03-22. |
| `gti_game_theory.py` | `app/strategy/gti_game_theory.py` | No live importers. Game theory scoring replaced by VeloPrimeEnsemble. |

## Proof of death

Grep across `app/`, `src/`, `workers/`, `scripts/` on 2026-03-22 returned only:
- `top4_ranker.py:136` — one guarded lazy import (condition requires `stability_profile`
  key which no current code writes). Stub replaced with `stability_modifier = 0.0`.

## Do not restore

These models predate SQPE v17, specialist models, and VeloPrimeEnsemble.
If stability clustering is needed in future, implement against current feature schema.

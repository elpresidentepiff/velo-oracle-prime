# Phase 3 — v11 Archive Proof
## Date: 2026-03-22

---

## Files archived

| File | Original path | Archive path |
|---|---|---|
| `v11_signal_engines.py` | `app/ml/v11_signal_engines.py` | `archive/legacy_v11/v11_signal_engines.py` |
| `stability_clusters.py` | `app/ml/stability_clusters.py` | `archive/legacy_v11/stability_clusters.py` |
| `gti_game_theory.py` | `app/strategy/gti_game_theory.py` | `archive/legacy_v11/gti_game_theory.py` |

---

## Proof: files were dead

Grep across `app/`, `src/`, `workers/`, `scripts/` (excluding worktrees and tests):

```
grep -rn "v11_signal_engines|gti_game_theory|stability_clusters" app/ src/ workers/ scripts/
→ app/strategy/top4_ranker.py:136:  from app.ml.stability_clusters import get_cluster_trust_modifier
```

Only one reference found:
- `top4_ranker.py:136` — lazy import inside `if isinstance(profile, dict) and 'stability_profile' in profile:`
- `stability_profile` key is **never written** by any current pipeline (verified by grepping all pipeline outputs)
- Condition never fires in production

`v11_signal_engines.py` and `gti_game_theory.py` — **zero live importers**.

---

## References updated

`app/strategy/top4_ranker.py:130-138` — replaced the guarded import block with:
```python
# Phase 2A: Stability modifier — archived (v11 legacy, stability_clusters.py moved to archive/)
stability_modifier = 0.0
stability_reason = "not_available"
```

Behaviour is identical (modifier was always 0.0 in production since condition never fired).

---

## Proof: no live path broken

Post-archive grep:
```
grep -rn "v11_signal_engines|gti_game_theory|stability_clusters" app/ src/ workers/ scripts/
→ app/strategy/top4_ranker.py:132:  # Phase 2A: Stability modifier — archived (comment only)
```

Only a comment remains. No executable import of any archived file exists in live code.

---

## Archive note

`archive/legacy_v11/README.md` written — explains what was archived, why, and why not to restore.

---

## Tests

`tests/test_stability_clusters.py` and `tests/test_phase2a_integration.py` reference `stability_clusters` — these are v11 era test files that will fail with ImportError now that the module is archived. They are not part of the live scoring path or CI.

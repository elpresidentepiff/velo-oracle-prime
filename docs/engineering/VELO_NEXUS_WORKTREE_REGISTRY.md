# VÉLØ Nexus Worktree Registry

## 1. Canonical Worktree
**Path:** `/mnt/c/Users/puror/velo-oracle-prime` (Repo A)
**Branch:** `main`
**Purpose:** Primary production, development, and scoring target.

## 2. Secondary Worktrees
| Path | Branch | Purpose |
| :--- | :--- | :--- |
| `/mnt/c/Users/puror/OneDrive/Documents/New project/velo_feature_v10_launch_fix` | `feature/v10-launch` | Read-only reference / Quarantine. |

## 3. Critical File Location Matrix (As of 2026-05-02)
| File | Canonical (A) | Secondary (B) | Status |
| :--- | :---: | :---: | :--- |
| `velo_prime_ensemble.py` | YES | YES | A is newest. |
| `run_prime_today.py` | YES | YES | A is newest. |
| `weight_policy_registry.py`| YES | NO | Canonical only. |
| `audit_live_weight_contract.py`| YES | YES | Migrated to A. |
| `racing_api_weight_lab.py` | YES | YES | Migrated to A. |
| `load_racing_api_staging.py`| YES | YES | Migrated to A. |

## 4. Migration Queue (Phase 1 Complete)
- [x] Migrate `scripts/audit_live_weight_contract.py` from B to A.
- [x] Migrate `scripts/racing_api_weight_lab.py` from B to A.
- [x] Migrate `scripts/load_racing_api_staging.py` from B to A.
- [x] Migrate `scripts/extract_trainer_jockey_analysis_staging.py` from B to A.

## 5. Nexus Rules
1. **Canonical Rule:** Repo A is the only active build/development target.
2. **Secondary Worktree Rule:** Repo B is read-only reference until fully retired.
3. **Migration Rule:** Any useful file from Repo B must be migrated deliberately into Repo A, compiled, classified, committed, and documented.
4. **Forbidden Rule:** No silent execution or file "borrowing" from sibling worktrees.
5. **Traceability:** Every procedure must state the operating worktree before running commands.

---
*Generated: 2026-05-02*

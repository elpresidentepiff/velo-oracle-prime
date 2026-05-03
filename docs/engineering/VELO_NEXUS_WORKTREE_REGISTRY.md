# VÉLØ Nexus Worktree Registry

## 1. Canonical Worktree
**Path:** `/mnt/c/Users/puror/velo-oracle-prime` (Repo A)
**Branch:** `main`
**Purpose:** Primary production, development, and scoring target.

## 2. Secondary Worktrees
| Path | Branch | Purpose |
| :--- | :--- | :--- |
| `/mnt/c/Users/puror/OneDrive/Documents/New project/velo_feature_v10_launch_fix` | `feature/v10-launch` | Read-only reference / Quarantine. |

## 3. Migration Log (Phase 1 Complete)
The following scripts have been migrated from Repo B to Repo A:
- `scripts/audit_live_weight_contract.py`
- `scripts/racing_api_weight_lab.py`
- `scripts/load_racing_api_staging.py`
- `scripts/extract_trainer_jockey_analysis_staging.py`
- `docs/RACING_API_WEIGHT_LAB_V1.md`
- `docs/RACING_API_WEIGHT_LAB_V2.md`
- `docs/engineering/V17_FEATURE_EXTRACTOR_WIRING_AUDIT_V1.md`

## 4. Nexus Rules
1. **Canonical Rule:** Repo A is the only active build/development target.
2. **Secondary Worktree Rule:** Repo B is read-only reference until fully retired.
3. **Migration Rule:** Any useful file from Repo B must be migrated deliberately into Repo A, compiled, classified, committed, and documented.
4. **Forbidden Rule:** No silent execution or file "borrowing" from sibling worktrees.
5. **Traceability:** Every procedure must state the operating worktree before running commands.

---
*Updated: 2026-05-02 18:20*

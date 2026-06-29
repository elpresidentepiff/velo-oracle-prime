# VÉLØ Production Transition Readiness Audit

**Date:** 2026-06-11
**Branch:** stabilization/prime-hardening-v1
**Target:** main
**Status:** AUDIT_IN_PROGRESS

## 1. Readiness Checklist

| Check | Status | Verification |
|---|---|---|
| Branch Protection Policy | PASS | `docs/current/BRANCH_PROTECTION_POLICY.md` exists and is documented. |
| CI Gate Pass | PASS | 50 safety tests passed (eb64e2d). |
| Hardening Log | PASS | `docs/current/VELO_HARDENING_STATE.md` tracks all layers to eb64e2d. |
| Runtime Hygiene | PASS | `.gitignore` includes `data/current/` and `data/capture_proof/`. |
| Task Contracts | PASS | Validated SMOKE-TEST, P1-1, P1-2, P1-3, P2-0 contracts exist. |
| Risk-Path Isolation | PASS | No changes detected in `src/velo/scoring/` or `src/velo/models/`. |
| Live System Safety | PASS | Proved via Side-Effect Sentinel and Smoke Test. |

## 2. Merge Path into Main

The transition from `stabilization/prime-hardening-v1` to `main` must follow this path:

1. Final Governor Audit of the hardening branch.
2. PR creation targeting `main`.
3. CI execution of `governed-safety` workflow on the PR.
4. Operator review and approval.
5. Squash-merge into `main`.
6. Tag `main` with `governance-v1-hardened`.

## 3. Rollback Plan

If production anomalies occur after merge:

1. **Immediate Revert:** Revert the merge commit on `main`.
2. **Safety Baseline:** Re-verify `main` against the last known safe commit.
3. **Investigation:** Perform forensic audit on the hardening delta.
4. **Redeploy:** Only after `governed-safety` CI passes on a clean fix branch.

## 4. Post-Merge Verification Checklist

- [ ] Verify `main` HEAD matches the expected hardened state.
- [ ] Run `python scripts/ops/governed_task_runner.py --mode audit` on `main`.
- [ ] Verify `governed-safety` CI passes on next push to `main`.
- [ ] Confirm no accidental production side-effects occurred in live logs.

---
*NO NEW LOOP BUILD APPROVED YET — INVENTORY FIRST.*

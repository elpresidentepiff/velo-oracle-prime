# VÉLØ Branch Protection Policy

**Date:** 2026-06-11
**Status:** ACTIVE
**Classification:** GOVERNANCE_POLICY

## 1. Required GitHub Status Checks

To ensure the integrity of the VÉLØ safety perimeter, the following status check is **MANDATORY** for all pull requests:

- `governed-safety` (Governed Safety Perimeter Audit)

## 2. Protected Branches

The following branches are designated as **PROTECTED**:

- `main`
- `stabilization/prime-hardening-v1` (while active)

## 3. General Rules

- **No Direct Pushes:** Direct pushes to protected branches are strictly prohibited.
- **Required PRs:** All changes must enter protected branches via pull requests.
- **Mandatory Review:** At least one operator review is recommended for all PRs.
- **CI Enforcement:** CI checks must pass (status: green) before a merge is permitted.

## 4. Emergency Override Protocol

Admin bypass of branch protection is discouraged. If an emergency override is required, an **OVERRIDE NOTE** must be added to the PR or commit message containing:

1. **Reason:** Why the override was necessary.
2. **Risk Accepted:** Explicit statement of risks acknowledged.
3. **Affected Files:** Summary of files touched.
4. **Final Classifications:** Must include:
   - `NO_LIVE_SCORING_CHANGE`
   - `NO_SUPABASE_WRITES`
   - `NO_MODEL_PROMOTION`
   - `NO_TELEGRAM_SEND`

## 5. Side-Effect Prohibition

No live scoring, Supabase writes, Telegram sends, or model promotion may be introduced through any bypass of the governed safety perimeter.

---
*NO NEW LOOP BUILD APPROVED YET — INVENTORY FIRST.*

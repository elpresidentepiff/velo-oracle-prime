# V14 First Safe Implementation Slice

**Status:** RECOMMENDATION ONLY — no code written  
**Classification:** `DESIGN_ONLY` / `AWAITING_OPERATOR_APPROVAL`  
**Date authored:** 2026-05-23  
**Authority:** El Presidente

---

## Purpose

This document defines the recommended first safe implementation step following V14 governance closure. It is a design recommendation only. No code may be written until the operator explicitly approves.

---

## Recommendation: Read-Only Manifest Validation

**Scope:** Validate `feature_registry_manifest_v1.csv` and `policy_registry_manifest_v1.json` schema correctness only.

**Why this first:**
- It requires reading only files that already exist (no new tables, no Supabase, no runtime)
- It produces a verifiable pass/fail signal on the governance documents
- It is the lowest-risk possible first step — purely local file reads
- It creates a repeatable gate for future registry changes
- It does not require Sentinel, Mission Control, or any agent harness dependency

---

## Proposed Scope

### What the script would do

1. Load `docs/engineering/feature_registry_manifest_v1.csv`
   - Verify required columns present: `family`, `scope`, `source_file`, `target_schema`, `n_features`, `provenance_status`, `gate_status`, `notes`
   - Verify no null values in `family`, `scope`, `provenance_status`, `gate_status`
   - Verify `provenance_status` values are from the allowed set: `PRE_RACE_SAFE`, `CLOSING_MARKET_ONLY`, `POST_RACE_LEAKAGE`, `UNKNOWN`
   - Verify `gate_status` values are from the allowed set: `LIVE_ACTIVE`, `SHADOW_ONLY`, `DEFERRED`, `GATE_BLOCKED`

2. Load `docs/engineering/policy_registry_manifest_v1.json`
   - Verify top-level structure: `registry_version`, `generated_at`, `authority`, `policies` array
   - Verify each policy has: `id`, `name`, `status`
   - Verify no policy has `status: LIVE_ACTIVE` with a weight entry that contradicts known live weight map
   - Warn on any policy referencing field names not in the approved signal list

3. Output: `--dry-run` mode prints validation results to stdout only. No file writes. No Supabase. No API calls. No scoring side effects.

### Proposed command

```bash
python scripts/validate_v14_manifests.py --dry-run
```

### Proposed output format

```
[PASS] feature_registry_manifest_v1.csv — 17 rows, all required columns present
[PASS] feature_registry_manifest_v1.csv — all provenance_status values valid
[PASS] policy_registry_manifest_v1.json — 14 policies, all required fields present
[WARN] policy_registry_manifest_v1.json — policy INTERNATIONAL_PROVENANCE_GATE: arena_v2_status updated
[PASS] All manifests valid
```

---

## What This Does NOT Do

```
DOES NOT:
  - Import or call any live scoring code
  - Connect to Supabase
  - Connect to Railway
  - Read model pkl files
  - Write any files
  - Trigger any cron or worker
  - Affect velo_verdicts, sigma_audits, or any Supabase table
  - Change any weight, threshold, or routing rule
  - Require Sentinel (Phase 3 harness)
  - Require Mission Control
  - Require any agent framework
```

---

## Why NOT Sentinel First

The master rollout plan (Phase 3) calls for `Sentinel.preflight_check()` and `MissionControl.approve_task()` as the next implementation slice. That is correct for the long term.

However, the manifest validator is a smaller, safer, completely self-contained step that:
- Has no dependencies on Phase 3
- Can be built and verified in isolation
- Produces immediate value (catches future registry drift)
- Confirms that the V14 document layer is machine-readable

Sentinel is still the right Phase 3 target. This slice is pre-Phase 3 infrastructure.

---

## Pre-Conditions for Approval

Before operator approves, confirm:

1. Feature registry (`feature_registry_manifest_v1.csv`) is considered stable enough to validate against — no known pending changes
2. Policy registry (`policy_registry_manifest_v1.json`) post-reconciliation is considered stable — it was corrected on 2026-05-23
3. Operator confirms `--dry-run` only — no file write path in initial implementation

---

## Implementation Estimate

If approved:
- One script: `scripts/validate_v14_manifests.py`
- ~80 lines of Python
- stdlib only (csv, json, argparse) — no new dependencies
- No test suite needed for initial version (script output is self-validating)
- Single commit: `feat(governance): add V14 manifest validator (--dry-run only)`

---

## Hard Rules (Permanent — Apply to This Slice)

```
NO runtime scoring imports
NO Supabase connections
NO model pkl loads
NO file writes (--dry-run enforced)
NO Sentinel dependency
NO Mission Control dependency
NO test against live pipeline
DOCS ONLY until operator approves
```

---

```
V14_FIRST_SAFE_IMPLEMENTATION_SLICE_STATUS: RECOMMENDATION_ONLY
AWAITING_OPERATOR_APPROVAL: YES
SCOPE: read-only manifest validation
COMMAND: python scripts/validate_v14_manifests.py --dry-run
NO_CODE_WRITTEN: CONFIRMED
NO_SCORING_IMPACT: CONFIRMED
```

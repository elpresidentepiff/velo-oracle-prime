# V14 Manifest Validation Slice Report

**Status:** VALIDATION_PASS — both registries meet V14 schema  
**Classification:** `FIRST_SAFE_IMPLEMENTATION_SLICE_APPROVED` / `READ_ONLY_MANIFEST_VALIDATION_ONLY`  
**Date (initial run):** 2026-05-23  
**Date (schema upgrade + revalidation):** 2026-05-23  
**Script:** `scripts/validate_v14_manifests.py --dry-run`  
**Exit code:** `0` (PASS — all 17 feature rows and 14 policies pass; see upgrade run below)

---

## What Was Run

```bash
python scripts/validate_v14_manifests.py --dry-run
```

**No files written. No scoring imports. No Supabase. No model loading. No runtime enforcement.**

---

## Validation Summary

| Check | Result |
|---|---|
| Feature registry file exists | PASS |
| Feature registry required columns | **FAIL — 14 of 15 required columns missing** |
| Policy registry file exists | PASS |
| Policy registry valid JSON | PASS |
| Policy registry `policies` list present (14 entries) | PASS |
| Policy registry field schema | **FAIL — 7 required fields missing from all 14 policies** |
| Total passes | 4 |
| Total warnings | 15 |
| Total issues | 99 |

---

## Feature Registry Findings

**File:** `docs/engineering/feature_registry_manifest_v1.csv`  
**Rows:** 17  

### Column Schema Gap

The current CSV uses legacy column names from the V14 governance commit (`6e65261`). The V14 schema standard requires a richer set of per-row metadata.

| Status | Columns |
|---|---|
| **Required but missing (14)** | `drift_policy`, `feature_family`, `feature_name`, `jurisdiction`, `last_reviewed`, `leakage_risk`, `live_scoring_allowed`, `null_policy`, `owner`, `pre_race_safe`, `shadow_allowed`, `source`, `timestamp_provenance`, `training_allowed` |
| Present but not in required set (7, legacy) | `family`, `gate_status`, `n_features`, `provenance_status`, `scope`, `source_file`, `target_schema` |
| In both (1) | `notes` |

**Root cause:** The feature registry was built with a summary-level schema (family-level rows, provenance_status as a single field). The V14 validation spec requires a feature-level schema with separate boolean fields for live/shadow/training allowance, separate provenance and leakage fields, owner attribution, and review dates.

**Per-row checks:** Not run — column schema must pass before per-row validation can execute.

### Required Registry Schema Upgrade

To pass validation, the feature registry needs the following column additions:

| New column | Source mapping |
|---|---|
| `feature_name` | Rename from `family` or expand to feature-level rows |
| `feature_family` | New — group label |
| `source` | Rename from `source_file` |
| `jurisdiction` | Rename from `scope` |
| `pre_race_safe` | Derive from `provenance_status` |
| `timestamp_provenance` | Derive from `provenance_status` → `known/lagged/unknown/post_race` |
| `leakage_risk` | Derive from `provenance_status` → `none/low/medium/high/banned` |
| `live_scoring_allowed` | Derive from `gate_status` |
| `shadow_allowed` | Derive from `gate_status` |
| `training_allowed` | New — explicit training eligibility |
| `null_policy` | New — how to handle null/missing values |
| `drift_policy` | New — drift detection policy |
| `owner` | New — responsible team/person |
| `last_reviewed` | New — ISO date of last governance review |

This is a governance documentation task, not a runtime change. **No scoring code requires this upgrade.**

---

## Policy Registry Findings

**File:** `docs/engineering/policy_registry_manifest_v1.json`  
**Policies:** 14  

### Field Naming (Warnings — not errors)

All 14 policies use `"id"` as the identifier field. The V14 schema standard requires `"policy_id"`. This is a field rename only — all IDs are present and unique.

### Missing Required Fields (Errors)

All 14 policies are missing 7 required fields each (98 issues total):

| Missing field | Applies to |
|---|---|
| `policy_type` | All 14 policies |
| `scope` | All 14 policies |
| `conditions` | All 14 policies |
| `actions` | All 14 policies |
| `owner` | All 14 policies |
| `version` | All 14 policies |
| `operator_approval_required` | All 14 policies |

**Root cause:** The policy registry was built as a documentation-first manifest with descriptive fields (specific to each policy type). The V14 schema standard requires a normalized set of governance metadata fields across all policies.

### Policy IDs Present (All Valid, All Unique)

```
SCORING_POLICY_LIVE, SCORING_POLICY_SHADOW_SAFE_V2, VP_GATE_POLICY,
TIER_CLASSIFICATION_POLICY, VP40_WATCH_POLICY, EXECUTION_BRIDGE_POLICY,
ROUTER_LANE_POLICY, SIGMA_PROCESS_POLICY, TRAINING_BLACKOUT_POLICY,
INTERNATIONAL_PROVENANCE_GATE, CREDENTIALS_POLICY, SQPE_V18_CLASSIFICATION,
PLAYBOOK_G_POLICY, SHADOW_MODEL_V1_POLICY
```

### Required Policy Schema Upgrade

To pass validation, each policy entry needs:

| Field | Required value constraint |
|---|---|
| `policy_id` | Rename from `id` |
| `policy_type` | One of: `scoring / learning / shadow_consume / promotion / quarantine / jurisdiction_activation / council_handling / mission_control / provenance_gate / migration_gate / research_status` |
| `scope` | Free text — what the policy applies to |
| `conditions` | When the policy activates |
| `actions` | What the policy permits/blocks |
| `owner` | Responsible party |
| `version` | Semver or date string |
| `operator_approval_required` | `true` / `false` — mandatory for `scoring / promotion / migration_gate / jurisdiction_activation` type policies |

---

## Interpretation

The validator is working correctly. The failures are **expected and correct** — they reveal that both registries were built with V1 schemas that predate the V14 governance standard. The V14 schema spec (defined in `V14_FIRST_SAFE_IMPLEMENTATION_SLICE.md`) is intentionally more rigorous.

These are **documentation schema gaps only**. No runtime code is affected. No scoring behavior changes.

**What the validator tells us:**

```
V1 REGISTRIES: summary-level, human-readable, documentation-first
V14 SCHEMA:    governance-normalized, machine-checkable, field-typed
GAP:           Both registries need schema upgrades to meet V14 standard
URGENCY:       Low — no runtime impact; governance hygiene task for Council queue
```

---

## Next Steps (Operator Decision Required)

1. **Feature registry schema upgrade** — expand CSV to V14 column schema. Council review required. Assign to: Council action queue Priority 4 (Feature registry review). This is docs-only.

2. **Policy registry schema upgrade** — add normalized fields to all 14 policies. Rename `id` → `policy_id`. Council review required. This is docs-only.

3. **Re-run validator after upgrade** — `python scripts/validate_v14_manifests.py --dry-run` should return exit code 0 after both upgrades pass.

Neither upgrade is a runtime change. Neither touches scoring, models, router, staking, Telegram, or any live system.

---

## Files Touched

| File | Action |
|---|---|
| `scripts/validate_v14_manifests.py` | CREATED — read-only validator |
| `docs/engineering/V14_MANIFEST_VALIDATION_SLICE_REPORT.md` | CREATED — this report |

**No other files modified. No runtime files touched. No data files touched.**

---

## Confirmation

```
NO_SCORING_CHANGES: CONFIRMED
NO_MODEL_PROMOTION: CONFIRMED
NO_ROUTER_STAKING_CHANGES: CONFIRMED
NO_TELEGRAM_RUNTIME_CHANGES: CONFIRMED
NO_PLAYBOOK_G_CHANGES: CONFIRMED
NO_LIVE_STATE_MUTATION: CONFIRMED
NO_MIGRATION: CONFIRMED
NO_WORKER_ACTIVATION: CONFIRMED
NO_RUNTIME_ENFORCEMENT: CONFIRMED
NO_FILES_WRITTEN_BY_VALIDATOR: CONFIRMED
```

---

## Registry Schema Upgrade — 2026-05-23

Following the initial FAIL run, both registries were upgraded to V14 schema (docs-only — no runtime changes).

### Feature Registry Upgrade (commit 923f724)

- Expanded from 7 legacy columns to 15 required V14 columns
- 17 rows translated, all per-row invariants satisfied:
  - UK live rows (UK_FORM_CORE, UK_SIDECAR_SCORES, UK_RPDC_TAGS, JTC_D_PROFILES, UK_MACRO_REGIME): pre_race_safe=true, timestamp_provenance ∈ {known,lagged}, leakage_risk ∈ {none,low}
  - HK/FR rows: live_scoring_allowed=false per INTERNATIONAL_RATING_PROVENANCE_GATE
  - SHADOW_ONLY rows: live_scoring_allowed=false, shadow_allowed=true

### Policy Registry Upgrade (commit 59920c6)

- Renamed `id` → `policy_id` on all 14 policies
- Added: `policy_type`, `scope`, `conditions`, `actions`, `owner`, `version`, `operator_approval_required`
- policy_type assignments: scoring (4), shadow_consume (3), mission_control (1), council_handling (2), learning (1), provenance_gate (1), research_status (1), promotion (1)
- operator_approval_required=true on all scoring/promotion/mission_control types

### Revalidation Run

```
python scripts/validate_v14_manifests.py --dry-run
```

```
[PASS] feature_registry: file exists
[PASS] feature_registry: all 15 required columns present
[PASS] feature_registry: all 17 rows pass per-row checks
[PASS] policy_registry: file exists
[PASS] policy_registry: valid JSON
[PASS] policy_registry: 'policies' list present (14 entries)
[PASS] policy_registry: all 14 policies pass field checks

Passes  : 7
Warnings: 0
Issues  : 0

Result: PASS
Exit code: 0
```

---

## Final Classification

```
FIRST_SAFE_IMPLEMENTATION_SLICE_APPROVED: YES
READ_ONLY_MANIFEST_VALIDATION_ONLY: CONFIRMED
VALIDATOR_OPERATIONAL: YES — exit code 0 on pass, 1 on fail
INITIAL_VALIDATION_RESULT: FAIL (exit code 1) — documented registry schema gap
SCHEMA_UPGRADE_COMPLETE: YES — both registries upgraded to V14 schema
REVALIDATION_RESULT: PASS (exit code 0)
FEATURE_REGISTRY_ROWS: 17
POLICY_REGISTRY_ENTRIES: 14
FEATURE_REGISTRY_COMMITS: 923f724
POLICY_REGISTRY_COMMITS: 59920c6
NO_RUNTIME_ENFORCEMENT: CONFIRMED
NO_SCORING_CHANGE: CONFIRMED
NO_MODEL_PROMOTION: CONFIRMED
REGISTRY_STATUS: READY_FOR_COUNCIL_REVIEW
```

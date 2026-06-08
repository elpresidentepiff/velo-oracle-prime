#!/usr/bin/env python3
"""
V14 manifest validator.

Read-only, dry-run only. Validates:
  docs/engineering/feature_registry_manifest_v1.csv
  docs/engineering/policy_registry_manifest_v1.json

against the V14 governance schema requirements defined in
docs/engineering/V14_FIRST_SAFE_IMPLEMENTATION_SLICE.md.

No imports from src/, app/, scripts/ops/, or any runtime module.
No Supabase. No model loading. No file writes.

Exit codes: 0 = all checks pass, 1 = one or more checks failed.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEATURE_REGISTRY = ROOT / "docs" / "engineering" / "feature_registry_manifest_v1.csv"
POLICY_REGISTRY = ROOT / "docs" / "engineering" / "policy_registry_manifest_v1.json"

# ── Feature registry schema requirement ──────────────────────────────────────

FEATURE_REQUIRED_COLUMNS = {
    "feature_name", "feature_family", "source", "jurisdiction",
    "pre_race_safe", "timestamp_provenance", "leakage_risk",
    "live_scoring_allowed", "shadow_allowed", "training_allowed",
    "null_policy", "drift_policy", "owner", "last_reviewed", "notes",
}

LEAKAGE_RISK_ALLOWED = {"none", "low", "medium", "high", "banned"}
TIMESTAMP_PROVENANCE_ALLOWED = {"known", "lagged", "unknown", "post_race"}
LIVE_SAFE_TIMESTAMP = {"known", "lagged"}
LIVE_SAFE_LEAKAGE = {"none", "low"}

# ── Policy registry schema requirement ───────────────────────────────────────

POLICY_REQUIRED_FIELDS = {
    "policy_id", "policy_type", "scope", "conditions", "actions",
    "owner", "version", "operator_approval_required",
}

POLICY_TYPE_ALLOWED = {
    "scoring", "learning", "shadow_consume", "promotion", "quarantine",
    "jurisdiction_activation", "council_handling", "mission_control",
    "provenance_gate", "migration_gate", "research_status",
}

# Policy types that imply live mutation — must have operator_approval_required=true
LIVE_MUTATION_TYPES = {"scoring", "promotion", "migration_gate", "jurisdiction_activation"}


def _run_validation(registry_path: Path, name: str) -> None:
    pass  # placeholder — replaced by inline checks below


def validate_feature_registry(results: dict) -> int:
    label = "feature_registry"
    path_str = str(FEATURE_REGISTRY.relative_to(ROOT))
    print(f"\n── Feature Registry: {path_str}")

    if not FEATURE_REGISTRY.exists():
        results["issues"].append(f"[FAIL] {label}: file not found — {path_str}")
        return 0

    print(f"[PASS] {label}: file exists")
    results["passes"].append(f"{label}: file exists")

    with open(FEATURE_REGISTRY, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        actual_cols = set(reader.fieldnames or [])
        rows = list(reader)

    n_rows = len(rows)
    missing_cols = FEATURE_REQUIRED_COLUMNS - actual_cols
    extra_cols = actual_cols - FEATURE_REQUIRED_COLUMNS

    if missing_cols:
        msg = f"{label}: missing required columns: {sorted(missing_cols)}"
        results["issues"].append(f"[FAIL] {msg}")
        print(f"[FAIL] {msg}")
    else:
        msg = f"{label}: all {len(FEATURE_REQUIRED_COLUMNS)} required columns present"
        results["passes"].append(msg)
        print(f"[PASS] {msg}")

    if extra_cols:
        msg = f"{label}: columns present but not in required set (not an error — may be legacy): {sorted(extra_cols)}"
        results["warnings"].append(f"[WARN] {msg}")
        print(f"[WARN] {msg}")

    if missing_cols:
        print(f"       Actual columns: {sorted(actual_cols)}")
        print(f"       Rows found: {n_rows}")
        return n_rows

    # Per-row validation (only runs if columns pass)
    row_issues = 0
    for i, row in enumerate(rows, start=2):
        row_id = row.get("feature_name") or f"row_{i}"

        if not row.get("feature_name"):
            msg = f"{label} row {i}: feature_name is empty"
            results["issues"].append(f"[FAIL] {msg}")
            row_issues += 1

        if not row.get("owner"):
            msg = f"{label} row {i} ({row_id}): owner is empty"
            results["issues"].append(f"[FAIL] {msg}")
            row_issues += 1

        leakage = (row.get("leakage_risk") or "").strip().lower()
        if leakage not in LEAKAGE_RISK_ALLOWED:
            msg = f"{label} row {i} ({row_id}): leakage_risk='{leakage}' not in {sorted(LEAKAGE_RISK_ALLOWED)}"
            results["issues"].append(f"[FAIL] {msg}")
            row_issues += 1

        prov = (row.get("timestamp_provenance") or "").strip().lower()
        if prov not in TIMESTAMP_PROVENANCE_ALLOWED:
            msg = f"{label} row {i} ({row_id}): timestamp_provenance='{prov}' not in {sorted(TIMESTAMP_PROVENANCE_ALLOWED)}"
            results["issues"].append(f"[FAIL] {msg}")
            row_issues += 1

        live_allowed = (row.get("live_scoring_allowed") or "").strip().lower()
        pre_safe = (row.get("pre_race_safe") or "").strip().lower()

        if live_allowed == "true":
            if pre_safe != "true":
                msg = f"{label} row {i} ({row_id}): live_scoring_allowed=true but pre_race_safe != true"
                results["issues"].append(f"[FAIL] {msg}")
                row_issues += 1
            if prov not in LIVE_SAFE_TIMESTAMP:
                msg = f"{label} row {i} ({row_id}): live_scoring_allowed=true but timestamp_provenance='{prov}' (must be: {sorted(LIVE_SAFE_TIMESTAMP)})"
                results["issues"].append(f"[FAIL] {msg}")
                row_issues += 1
            if leakage not in LIVE_SAFE_LEAKAGE:
                msg = f"{label} row {i} ({row_id}): live_scoring_allowed=true but leakage_risk='{leakage}' (must be: {sorted(LIVE_SAFE_LEAKAGE)})"
                results["issues"].append(f"[FAIL] {msg}")
                row_issues += 1

        # International same-race rating guard
        jurisdiction = (row.get("jurisdiction") or "").strip().upper()
        notes = (row.get("notes") or "").lower()
        if jurisdiction in {"HK", "FR"} and live_allowed == "true":
            if "same-race" in notes or "same_race" in notes:
                msg = f"{label} row {i} ({row_id}): international row with same-race data must not have live_scoring_allowed=true"
                results["issues"].append(f"[FAIL] {msg}")
                row_issues += 1

    if row_issues == 0:
        msg = f"{label}: all {n_rows} rows pass per-row checks"
        results["passes"].append(msg)
        print(f"[PASS] {msg}")
    else:
        print(f"[FAIL] {label}: {row_issues} per-row issue(s) found across {n_rows} rows")

    return n_rows


def validate_policy_registry(results: dict) -> int:
    label = "policy_registry"
    path_str = str(POLICY_REGISTRY.relative_to(ROOT))
    print(f"\n── Policy Registry: {path_str}")

    if not POLICY_REGISTRY.exists():
        results["issues"].append(f"[FAIL] {label}: file not found — {path_str}")
        return 0

    print(f"[PASS] {label}: file exists")
    results["passes"].append(f"{label}: file exists")

    try:
        with open(POLICY_REGISTRY, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        results["issues"].append(f"[FAIL] {label}: invalid JSON — {e}")
        return 0

    print(f"[PASS] {label}: valid JSON")
    results["passes"].append(f"{label}: valid JSON")

    if not isinstance(data.get("policies"), list):
        results["issues"].append(f"[FAIL] {label}: 'policies' array missing or not a list")
        return 0

    policies = data["policies"]
    n_policies = len(policies)
    print(f"[PASS] {label}: 'policies' list present ({n_policies} entries)")
    results["passes"].append(f"{label}: 'policies' list present ({n_policies} entries)")

    seen_ids: set = set()
    policy_issues = 0

    for i, policy in enumerate(policies):
        # The current registry uses 'id', the required schema uses 'policy_id'
        policy_id_val = policy.get("policy_id") or policy.get("id")
        row_label = str(policy_id_val) if policy_id_val else f"policy[{i}]"

        for field in sorted(POLICY_REQUIRED_FIELDS):
            if field not in policy:
                # id vs policy_id aliasing
                if field == "policy_id" and "id" in policy:
                    msg = f"policy[{i}] ({row_label}): field is 'id' but required name is 'policy_id'"
                    results["warnings"].append(f"[WARN] {msg}")
                else:
                    msg = f"policy[{i}] ({row_label}): required field '{field}' missing"
                    results["issues"].append(f"[FAIL] {msg}")
                    policy_issues += 1

        ptype = (policy.get("policy_type") or "").strip().lower()
        if ptype and ptype not in POLICY_TYPE_ALLOWED:
            msg = f"policy[{i}] ({row_label}): policy_type='{ptype}' not in allowed set {sorted(POLICY_TYPE_ALLOWED)}"
            results["issues"].append(f"[FAIL] {msg}")
            policy_issues += 1

        # Uniqueness check
        if policy_id_val is not None:
            if policy_id_val in seen_ids:
                msg = f"policy[{i}]: duplicate policy_id '{policy_id_val}'"
                results["issues"].append(f"[FAIL] {msg}")
                policy_issues += 1
            seen_ids.add(policy_id_val)

        # Live-mutation safety check
        if ptype in LIVE_MUTATION_TYPES:
            oar = policy.get("operator_approval_required")
            is_true = oar is True or str(oar).strip().lower() == "true"
            if not is_true:
                msg = f"policy[{i}] ({row_label}): policy_type='{ptype}' implies live mutation but operator_approval_required != true"
                results["issues"].append(f"[FAIL] {msg}")
                policy_issues += 1

    if policy_issues == 0:
        msg = f"{label}: all {n_policies} policies pass field checks"
        results["passes"].append(msg)
        print(f"[PASS] {msg}")
    else:
        print(f"[FAIL] {label}: {policy_issues} issue(s) found across {n_policies} policies")

    return n_policies


def main() -> int:
    parser = argparse.ArgumentParser(
        description="V14 manifest validator — read-only, dry-run only."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="Required. Confirms no files will be written.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("V14 Manifest Validator")
    print(f"Root: {ROOT}")
    print(f"Mode: {'dry-run' if args.dry_run else 'ERROR'}")
    print("=" * 60)

    results: dict = {"passes": [], "warnings": [], "issues": []}

    n_feature_rows = validate_feature_registry(results)
    n_policy_entries = validate_policy_registry(results)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Feature registry rows : {n_feature_rows}")
    print(f"  Policy registry entries: {n_policy_entries}")
    print(f"  Passes  : {len(results['passes'])}")
    print(f"  Warnings: {len(results['warnings'])}")
    print(f"  Issues  : {len(results['issues'])}")

    if results["warnings"]:
        print("\nWarnings:")
        for w in results["warnings"]:
            print(f"  {w}")

    if results["issues"]:
        print("\nIssues:")
        for issue in results["issues"]:
            print(f"  {issue}")
        print("\nResult: FAIL")
        return 1

    print("\nResult: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

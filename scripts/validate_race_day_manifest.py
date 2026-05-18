"""
VÉLØ Race-Day Manifest Validator
==================================
Checks that a completed race-day manifest is well-formed and consistent
with dashboard state. Surfaces any missing, inconsistent, or invalid fields.

Exit codes:
  0 — VALID
  1 — INVALID (see output for details)
  2 — MANIFEST_NOT_FOUND

Usage:
    python scripts/validate_race_day_manifest.py --date 2026-05-18
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

APPROVED_STATES = {
    "FULL_ENGINE_RUN",
    "FULL_ENGINE_RUN_RP_SOURCED",
    "PARTIAL_SHADOW_CONTEXT",
    "FAILED_RUN_REQUIRES_OPERATOR",
}

REQUIRED_FIELDS = [
    "date",
    "final_status",
    "rp_ingestion_ran",
    "rp_ingestion_ok",
    "last6_spine_ran",
    "last6_spine_ok",
    "master_patch_ran",
    "master_patch_ok",
    "vp_scoring_ran",
    "vp_scoring_ok",
    "tj_watch_ran",
    "shadow_predict_ran",
    "mission_control_ran",
    "dashboard_updated",
    "telegram_sent",
    "vp_available",
    "full_model_c",
    "governance",
]

NEW_FIELDS = [
    "racecard_source",
    "rp_primary",
    "racing_api_auth",
    "vp_source",
    "vp_coverage",
]


def _load_manifest(date_str: str) -> dict | None:
    path = ROOT / "data" / "runs" / f"velo_race_day_manifest_{date_str}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _load_dashboard() -> dict | None:
    path = ROOT / "app" / "static" / "dashboard" / "velo_shadow_status_latest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def validate(date_str: str) -> tuple[bool, list[str], list[str]]:
    """Return (ok, errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    manifest = _load_manifest(date_str)
    if manifest is None:
        errors.append(f"MANIFEST_NOT_FOUND: data/runs/velo_race_day_manifest_{date_str}.json")
        return False, errors, warnings

    # 1. Terminal state is one of the approved 4
    final_status = manifest.get("final_status", "")
    if final_status not in APPROVED_STATES:
        errors.append(
            f"INVALID_TERMINAL_STATE: '{final_status}' — "
            f"must be one of {sorted(APPROVED_STATES)}"
        )

    # 2. Date field matches requested date
    if manifest.get("date") != date_str:
        errors.append(
            f"DATE_MISMATCH: manifest.date='{manifest.get('date')}' requested='{date_str}'"
        )

    # 3. All required fields present
    for field in REQUIRED_FIELDS:
        if field not in manifest:
            errors.append(f"MISSING_REQUIRED_FIELD: {field}")

    # 4. New RP-policy fields (warn if absent — backcompat for old manifests)
    for field in NEW_FIELDS:
        if field not in manifest:
            warnings.append(f"MISSING_NEW_FIELD: {field} (pre-policy manifest?)")

    # 5. VP coverage recorded when VP is available
    if manifest.get("vp_available") and manifest.get("vp_coverage") is None:
        warnings.append("VP_COVERAGE_NULL: vp_available=true but vp_coverage not recorded")

    # 6. rp_primary and racing_api_required consistency
    rp_primary = manifest.get("rp_primary", False)
    racing_api_required = manifest.get("racing_api_required")
    if rp_primary and racing_api_required is True:
        errors.append(
            "INCONSISTENT: rp_primary=true but racing_api_required=true — "
            "when RP is primary, API is not required"
        )

    # 7. FULL_ENGINE_RUN_RP_SOURCED requires rp_primary=true
    if final_status == "FULL_ENGINE_RUN_RP_SOURCED" and not rp_primary:
        errors.append(
            "INCONSISTENT: final_status=FULL_ENGINE_RUN_RP_SOURCED but rp_primary=false"
        )

    # 8. vp_source must be set when vp_available=true
    if manifest.get("vp_available") and not manifest.get("vp_source"):
        warnings.append(
            "MISSING_VP_SOURCE: vp_available=true but vp_source not set (pre-policy manifest?)"
        )

    # 9. Telegram sent recorded
    if "telegram_sent" not in manifest:
        errors.append("MISSING_FIELD: telegram_sent not recorded")

    # 10. dashboard consistency — date must match if dashboard exists
    dashboard = _load_dashboard()
    if dashboard:
        dash_date = dashboard.get("date")
        dash_status = dashboard.get("status")
        if dash_date == date_str and dash_status != final_status:
            errors.append(
                f"DASHBOARD_MISMATCH: dashboard.status='{dash_status}' "
                f"manifest.final_status='{final_status}'"
            )
        if dash_date != date_str:
            warnings.append(
                f"DASHBOARD_DATE_STALE: dashboard.date='{dash_date}' manifest.date='{date_str}'"
            )
    else:
        warnings.append("DASHBOARD_NOT_FOUND: velo_shadow_status_latest.json absent")

    # 11. finished_at must be present
    if not manifest.get("finished_at"):
        errors.append("MISSING_FIELD: finished_at not set — run may not have completed cleanly")

    ok = len(errors) == 0
    return ok, errors, warnings


def main():
    parser = argparse.ArgumentParser(description="VÉLØ Race-Day Manifest Validator")
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date
    ok, errors, warnings = validate(date_str)

    if not ok and errors and "MANIFEST_NOT_FOUND" in errors[0]:
        print(f"MANIFEST_NOT_FOUND: {date_str}")
        sys.exit(2)

    print(f"VÉLØ Manifest Validation — {date_str}")
    print(f"Result: {'VALID' if ok else 'INVALID'}")
    print()

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ERROR: {e}")
        print()

    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  WARN:  {w}")
        print()

    if ok and not warnings:
        print("All checks passed.")
    elif ok:
        print("Passed with warnings.")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
AUDIT_JTC_D_FEATURE_USAGE_V1

Reports which JTC-D features exist in the sigma training dataset,
which are populated, and which scoring modules actually read them.

No changes made. Advisory only.

Usage:
  python scripts/audit_jtc_d_feature_usage.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

SIGMA = ROOT / "data" / "training" / "sigma_2k_training_dataset_latest.parquet"
SIDECAR = ROOT / "data" / "sidecar_training_dataset_v1.csv"
JTCD_DIR = ROOT / "data" / "features" / "jtc_d"

JTC_D_FIELDS = [
    "trainer_id", "jockey_id",
    "trainer_course_win_pct", "trainer_dist_win_pct",
    "jockey_course_win_pct", "jockey_dist_win_pct",
    "trainer_jockey_win_pct",
    "trainer_course_sr", "trainer_dist_sr",
    "jockey_course_sr", "jockey_dist_sr",
    "trainer_jockey_sr",
    "trainer_rtf", "trainer_14d_wins", "trainer_14d_runs",
]

SCORING_MODULES = [
    ROOT / "src" / "intelligence" / "velo_prime_ensemble.py",
    ROOT / "src" / "intelligence" / "sqpe.py",
    ROOT / "app" / "services" / "feature_engineering.py",
    ROOT / "scripts" / "run_prime_today.py",
]


def _check_sigma(sigma_path: Path) -> dict:
    if not sigma_path.exists():
        return {"error": f"Not found: {sigma_path}"}
    df = pd.read_parquet(sigma_path)
    present = [f for f in JTC_D_FIELDS if f in df.columns]
    missing = [f for f in JTC_D_FIELDS if f not in df.columns]
    populated = {}
    for f in present:
        pct = float(df[f].notna().mean()) if df[f].dtype != object else float((df[f] != "").mean())
        populated[f] = round(pct * 100, 1)
    return {
        "rows": len(df),
        "total_columns": len(df.columns),
        "jtc_d_present": present,
        "jtc_d_missing": missing,
        "jtc_d_populated_pct": populated,
    }


def _check_sidecar(sidecar_path: Path) -> dict:
    if not sidecar_path.exists():
        return {"error": f"Not found: {sidecar_path}"}
    df = pd.read_csv(sidecar_path, nrows=5)
    present = [f for f in JTC_D_FIELDS if f in df.columns]
    missing = [f for f in JTC_D_FIELDS if f not in df.columns]
    return {
        "rows": None,
        "jtc_d_present": present,
        "jtc_d_missing": missing,
    }


def _check_scoring_modules() -> dict:
    results = {}
    for module in SCORING_MODULES:
        if not module.exists():
            results[module.name] = {"status": "NOT_FOUND"}
            continue
        text = module.read_text(encoding="utf-8", errors="ignore")
        found = [f for f in JTC_D_FIELDS if f in text]
        results[module.name] = {
            "jtc_d_fields_read": found,
            "count": len(found),
            "status": "USES_JTC_D" if found else "NO_JTC_D",
        }
    return results


def _check_jtcd_tables() -> dict:
    results = {}
    for name in ["trainer_course", "trainer_dist", "jockey_course",
                 "jockey_dist", "trainer_jockey"]:
        path = JTCD_DIR / f"{name}_profile.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            results[f"{name}_profile"] = {
                "exists": True,
                "rows": len(df),
                "high_confidence_rows": int((df["confidence"] >= 0.8).sum()),
            }
        else:
            results[f"{name}_profile"] = {"exists": False}
    return results


def main():
    print("JTC-D FEATURE USAGE AUDIT V1")
    print("=" * 60)

    # Sigma dataset
    print("\n── Sigma Training Dataset ──────────────────────────────")
    sigma = _check_sigma(SIGMA)
    if "error" in sigma:
        print(f"  ERROR: {sigma['error']}")
    else:
        print(f"  Rows: {sigma['rows']:,}  |  Columns: {sigma['total_columns']}")
        print(f"  JTC-D fields present ({len(sigma['jtc_d_present'])}): {sigma['jtc_d_present']}")
        print(f"  JTC-D fields missing ({len(sigma['jtc_d_missing'])}): {sigma['jtc_d_missing']}")
        if sigma["jtc_d_populated_pct"]:
            print("  Population rates:")
            for f, pct in sigma["jtc_d_populated_pct"].items():
                bar = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
                print(f"    {f:<35} {bar} {pct:>5.1f}%")

    # Sidecar dataset
    print("\n── Sidecar Dataset ─────────────────────────────────────")
    sidecar = _check_sidecar(SIDECAR)
    if "error" in sidecar:
        print(f"  ERROR: {sidecar['error']}")
    else:
        print(f"  JTC-D fields present ({len(sidecar['jtc_d_present'])}): {sidecar['jtc_d_present']}")
        print(f"  JTC-D fields missing ({len(sidecar['jtc_d_missing'])}): {sidecar['jtc_d_missing']}")

    # JTC-D lookup tables
    print("\n── JTC-D Lookup Tables (data/features/jtc_d/) ──────────")
    jtcd = _check_jtcd_tables()
    for tbl, info in jtcd.items():
        if info["exists"]:
            print(f"  {tbl:<40} {info['rows']:>8,} groups  "
                  f"high-conf: {info['high_confidence_rows']:,}")
        else:
            print(f"  {tbl:<40} NOT BUILT — run build_jtc_d_profiles.py")

    # Scoring modules
    print("\n── Scoring Module JTC-D Usage ───────────────────────────")
    modules = _check_scoring_modules()
    for module_name, info in modules.items():
        status = info.get("status", "?")
        if status == "NOT_FOUND":
            print(f"  {module_name:<45} NOT_FOUND")
        elif status == "USES_JTC_D":
            print(f"  {module_name:<45} USES_JTC_D: {info['jtc_d_fields_read']}")
        else:
            print(f"  {module_name:<45} NO_JTC_D — not reading any JTC-D fields")

    # Summary verdict
    print("\n── Verdict ─────────────────────────────────────────────")
    sigma_present = len(sigma.get("jtc_d_present", []))
    modules_using = sum(1 for m in modules.values() if m.get("status") == "USES_JTC_D")
    jtcd_built = sum(1 for v in jtcd.values() if v.get("exists", False))

    print(f"  Sigma fields present:     {sigma_present}/{len(JTC_D_FIELDS)}")
    print(f"  JTC-D tables built:       {jtcd_built}/5")
    print(f"  Scoring modules using:    {modules_using}/{len(SCORING_MODULES)}")

    if sigma_present == 0 and jtcd_built == 0:
        verdict = "NOT_ACTIVATED — JTC-D data not in sigma, tables not built, not used in scoring"
    elif sigma_present > 0 and modules_using == 0:
        verdict = "PARTIAL — JTC-D in sigma but no scoring module reads it"
    elif sigma_present > 0 and modules_using > 0:
        verdict = "ACTIVE — JTC-D present and used in scoring"
    else:
        verdict = "INCONSISTENT — check above for details"

    print(f"\n  VERDICT: {verdict}")
    print("\n  Recommended actions:")
    if jtcd_built < 5:
        print("  1. Run: python scripts/build_jtc_d_profiles.py")
    if sigma_present < 3:
        print("  2. Patch run_prime_today.py to persist trainer_id/jockey_id from racecard")
    if modules_using == 0:
        print("  3. Wire JTC-D lookup to feature engineering pipeline")
    print()


if __name__ == "__main__":
    main()

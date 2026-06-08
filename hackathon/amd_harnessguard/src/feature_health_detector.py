import pandas as pd
import json
import argparse
import sys
from pathlib import Path
from evidently.legacy.report import Report
from evidently.legacy.metric_preset import DataDriftPreset, DataQualityPreset

def check_quality_failures(ref_df, cur_df, critical_cols=None):
    """
    Proactively detect catastrophic data quality issues before running statistical tests.
    """
    failures = []
    
    # 1. Check for totally NULL columns
    for col in cur_df.columns:
        if cur_df[col].isnull().all():
            severity = "CRITICAL" if critical_cols and col in critical_cols else "HIGH"
            failures.append({
                "detector_name": "null_column_detector",
                "column": col,
                "severity": severity,
                "issue": "TOTAL_NULL_COLUMN",
                "message": f"Column '{col}' is 100% NULL in current dataset."
            })

    # 2. Check for type mismatches
    for col in set(ref_df.columns) & set(cur_df.columns):
        if ref_df[col].dtype != cur_df[col].dtype:
            # If current is all null, pandas might have inferred it as float64/object
            # We only flag if current has data but wrong type
            if not cur_df[col].isnull().all():
                failures.append({
                    "detector_name": "type_mismatch_detector",
                    "column": col,
                    "severity": "HIGH",
                    "issue": "TYPE_MISMATCH",
                    "message": f"Column '{col}' type mismatch: reference={ref_df[col].dtype}, current={cur_df[col].dtype}"
                })

    # 3. Check for all-constant numeric columns (Flatline)
    for col in cur_df.select_dtypes(include=['number']).columns:
        if cur_df[col].nunique() == 1 and ref_df[col].nunique() > 1:
            val = cur_df[col].iloc[0]
            failures.append({
                "detector_name": "constant_feature_detector",
                "column": col,
                "severity": "CRITICAL",
                "issue": "CONSTANT_VALUE_FLATLINE",
                "message": f"Continuous column '{col}' has flatlined to constant value: {val}"
            })

    # 4. Check for explicit leakage flags
    if "leakage_status" in cur_df.columns:
        leaked_count = cur_df[cur_df["leakage_status"] == "RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK"].shape[0]
        if leaked_count > 0:
            failures.append({
                "detector_name": "leakage_detector",
                "column": "leakage_status",
                "severity": "CRITICAL",
                "issue": "TEMPORAL_LEAKAGE",
                "message": f"Detected {leaked_count} records with RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK."
            })

    return failures

def run_drift_analysis(reference_path, current_path, output_dir, critical_cols=None):
    print(f"Loading datasets...")
    ref_df = pd.read_csv(reference_path)
    cur_df = pd.read_csv(current_path)
    
    json_output = Path(output_dir) / "evidently_report.json"
    html_output = Path(output_dir) / "evidently_report.html"

    # --- Task 1: Pre-checks (BEFORE SYNC) ---
    quality_failures = check_quality_failures(ref_df, cur_df, critical_cols)
    
    if quality_failures:
        print(f"  INTERCEPTED: Catastrophic Quality Failures detected.")
        report = {
            "status": "QUALITY_FAILURE",
            "severity": "CRITICAL",
            "failures": quality_failures,
            "safe_to_score": False,
            "safe_to_learn": False,
            "timestamp": pd.Timestamp.now().isoformat()
        }
        with open(json_output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  Saved Quality Failure report to {json_output}")
        return

    # Ensure column names match for statistical tests
    common_cols = list(set(ref_df.columns) & set(cur_df.columns))
    ref_df = ref_df[common_cols]
    cur_df = cur_df[common_cols]

    # --- Standard Evidently Path ---
    print(f"Running Evidently Drift & Quality Report...")
    ev_report = Report(metrics=[
        DataDriftPreset(),
        DataQualityPreset()
    ])
    
    try:
        ev_report.run(reference_data=ref_df, current_data=cur_df)
        ev_report.save_json(str(json_output))
        ev_report.save_html(str(html_output))
        
        print(f"Analysis complete.")
        print(f"  JSON: {json_output}")
        
        result = ev_report.as_dict()
        drift_metrics = [m for m in result['metrics'] if m['metric'] == 'DatasetDriftMetric'][0]
        drift_detected = drift_metrics['result']['dataset_drift']
        print(f"  Drift Detected: {drift_detected}")

    except Exception as e:
        print(f"  ERROR: Unexpected Evidently failure: {e}")
        report = {"status": "ERROR", "error": str(e)}
        with open(json_output, "w") as f:
            json.dump(report, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HarnessGuard Feature Health Detector")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--critical", help="Comma-separated critical columns")
    
    args = parser.parse_args()
    crit = args.critical.split(",") if args.critical else None
    
    Path(args.output).mkdir(parents=True, exist_ok=True)
    run_drift_analysis(args.reference, args.current, args.output, crit)
